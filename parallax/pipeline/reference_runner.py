"""Run hash-recorded maintained reference systems in offline containers."""

from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import stat
import subprocess
import time
import uuid
from typing import Any

from pipeline.contracts import (
    ROOT,
    canonical_json,
    ensure_finite,
    load_json,
    sha256_file,
    validate_json_schema_instance,
    validate_run_id,
    write_json,
)
from pipeline.reference_scene import generate_colmap_scene


ADAPTER = "colmap-sfm"
IMAGE = "surflo-pathway-classical:1"
PINNED_COLMAP_VERSION = "3.9.1"
PINNED_COLMAP_PACKAGE_VERSION = "3.9.1-2build2"
PINNED_INSULA_MANIFEST = {
    "schema_version": "1",
    "kind": "classical-geometry",
    "ubuntu": "24.04",
    "colmap": PINNED_COLMAP_PACKAGE_VERSION,
    "network_policy": "build-and-fetch-only",
}
REFERENCE_IMPLEMENTATION = (
    "pipeline/cli.py", "pipeline/contracts.py", "pipeline/reference_runner.py", "pipeline/reference_scene.py",
    "insulas/classical/Dockerfile", "reference-result.schema.json", "shared-scene.json", "reference-adapters.json",
)
REQUIRED_DATABASE_TABLES = {
    "cameras", "images", "keypoints", "descriptors", "matches", "two_view_geometries",
}


def _hash_tree(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        mode = path.lstat().st_mode
        relative = path.relative_to(root).as_posix()
        if stat.S_ISLNK(mode):
            raise ValueError(f"symlink artifact is forbidden: {relative}")
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ValueError(f"non-regular artifact is forbidden: {relative}")
        if path.name != "result.json":
            hashes[relative] = sha256_file(path)
    return hashes


def _data_lines(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("#")]


def _parse_colmap_text(model: Path) -> dict[str, float | int]:
    camera_lines = [line for line in _data_lines(model / "cameras.txt") if line]
    if not camera_lines:
        raise ValueError("COLMAP produced no cameras")
    camera_ids: set[int] = set()
    model_parameter_counts = {"SIMPLE_PINHOLE": 3, "PINHOLE": 4, "SIMPLE_RADIAL": 4, "RADIAL": 5}
    for line in camera_lines:
        fields = line.split()
        if len(fields) < 5 or fields[1] not in model_parameter_counts:
            raise ValueError("malformed COLMAP camera record")
        try:
            camera_id, width, height = int(fields[0]), int(fields[2]), int(fields[3])
            parameters = [float(value) for value in fields[4:]]
        except ValueError as error:
            raise ValueError("malformed COLMAP camera record") from error
        if (
            camera_id <= 0 or camera_id in camera_ids or width <= 0 or height <= 0
            or len(parameters) != model_parameter_counts[fields[1]]
            or any(not math.isfinite(value) for value in parameters)
        ):
            raise ValueError("malformed COLMAP camera record")
        camera_ids.add(camera_id)

    image_lines = _data_lines(model / "images.txt")
    if not image_lines or len(image_lines) % 2:
        raise ValueError("malformed COLMAP image record pairing")
    image_ids: set[int] = set()
    poses: list[str] = []
    for index in range(0, len(image_lines), 2):
        pose = image_lines[index]
        observations = image_lines[index + 1]
        fields = pose.split()
        if len(fields) < 10:
            raise ValueError("malformed COLMAP image record")
        try:
            image_id = int(fields[0])
            transform = [float(value) for value in fields[1:8]]
            camera_id = int(fields[8])
        except ValueError as error:
            raise ValueError("malformed COLMAP image record") from error
        quaternion_norm = math.sqrt(sum(value * value for value in transform[:4]))
        if (
            image_id <= 0 or image_id in image_ids or camera_id not in camera_ids
            or any(not math.isfinite(value) for value in transform) or quaternion_norm == 0.0
            or not fields[9]
        ):
            raise ValueError("malformed COLMAP image record")
        observation_fields = observations.split()
        if len(observation_fields) % 3:
            raise ValueError("malformed COLMAP image observation record")
        for observation_index in range(0, len(observation_fields), 3):
            try:
                x = float(observation_fields[observation_index])
                y = float(observation_fields[observation_index + 1])
                int(observation_fields[observation_index + 2])
            except ValueError as error:
                raise ValueError("malformed COLMAP image observation record") from error
            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError("malformed COLMAP image observation record")
        image_ids.add(image_id)
        poses.append(pose)

    point_lines = [line for line in _data_lines(model / "points3D.txt") if line]
    point_ids: set[int] = set()
    errors: list[float] = []
    for line in point_lines:
        fields = line.split()
        if len(fields) < 10 or (len(fields) - 8) % 2:
            raise ValueError("malformed COLMAP point record")
        try:
            point_id = int(fields[0])
            position = [float(value) for value in fields[1:4]]
            color = [int(value) for value in fields[4:7]]
            error = float(fields[7])
            track = [int(value) for value in fields[8:]]
        except ValueError as parse_error:
            raise ValueError("malformed COLMAP point record") from parse_error
        if (
            point_id <= 0 or point_id in point_ids or any(not math.isfinite(value) for value in position)
            or any(value < 0 or value > 255 for value in color)
            or not math.isfinite(error) or error < 0.0
            or any(track[index] not in image_ids for index in range(0, len(track), 2))
            or any(track[index] < 0 for index in range(1, len(track), 2))
        ):
            raise ValueError("malformed COLMAP point record")
        point_ids.add(point_id)
        errors.append(error)
    if not errors:
        raise ValueError("COLMAP produced no sparse points")
    metrics = {
        "registered_images": len(poses),
        "sparse_points": len(point_lines),
        "mean_reprojection_error_px": float(sum(errors) / len(errors)),
    }
    ensure_finite(metrics, "COLMAP metrics")
    return metrics


def _format_shell_number(value: Any, name: str) -> str:
    if isinstance(value, bool):
        raise ValueError(f"invalid numeric scene value: {name}")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid numeric scene value: {name}") from error
    if not math.isfinite(number):
        raise ValueError(f"invalid numeric scene value: {name}")
    return format(number, ".17g")


def _container_script(manifest: dict[str, Any], profile: str) -> str:
    intrinsics = manifest["intrinsics"]
    minimum_matches = 8 if profile == "smoke" else 12
    parameters = ",".join(_format_shell_number(intrinsics[key], key) for key in ("fx", "fy", "cx", "cy"))
    return f"""set -euo pipefail
export QT_QPA_PLATFORM=offscreen
mkdir -p /work/output/sparse /work/output/text
colmap -h >/tmp/colmap-help.txt 2>&1
awk 'NF {{print; exit}}' /tmp/colmap-help.txt > /work/output/colmap-version.txt
dpkg-query -W -f='${{Version}}\\n' colmap > /work/output/package-version.txt
cp /etc/surflo-pathway-insula /work/output/insula-manifest.txt
colmap feature_extractor \\
  --database_path /work/output/database.db \\
  --image_path /work/input/images \\
  --ImageReader.camera_model PINHOLE \\
  --ImageReader.single_camera 1 \\
  --ImageReader.camera_params {parameters} \\
  --SiftExtraction.use_gpu 0
colmap exhaustive_matcher \\
  --database_path /work/output/database.db \\
  --SiftMatching.use_gpu 0
colmap mapper \\
  --database_path /work/output/database.db \\
  --image_path /work/input/images \\
  --output_path /work/output/sparse \\
  --Mapper.min_num_matches {minimum_matches} \\
  --Mapper.init_min_num_inliers 20 \\
  --Mapper.ba_refine_focal_length 0 \\
  --Mapper.ba_refine_principal_point 0 \\
  --Mapper.ba_refine_extra_params 0
test -d /work/output/sparse/0
colmap model_converter \\
  --input_path /work/output/sparse/0 \\
  --output_path /work/output/text \\
  --output_type TXT
colmap model_converter \\
  --input_path /work/output/sparse/0 \\
  --output_path /work/output/sparse.ply \\
  --output_type PLY
cp /work/output/text/cameras.txt /work/output/text/images.txt /work/output/text/points3D.txt /work/output/sparse/0/
"""


def _inspect_image(engine: str, image: str = IMAGE) -> str:
    if shutil.which(engine) is None:
        raise ValueError(f"container engine not found: {engine}")
    completed = subprocess.run(
        [engine, "image", "inspect", "--format", "{{.Id}}", image],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError(f"classical Insula is not built: {image}; run `run.sh build` first")
    image_id = completed.stdout.strip()
    if not image_id:
        raise ValueError(f"container image inspection returned no immutable ID: {image}")
    return image_id


def _require_regular_file(run_dir: Path, relative: str) -> Path:
    path = run_dir / relative
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as error:
        raise ValueError(f"missing required reference artifact: {relative}") from error
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise ValueError(f"required reference artifact is not a regular file: {relative}")
    if path.stat().st_size == 0:
        raise ValueError(f"required reference artifact is empty: {relative}")
    return path


def _validated_resource_summary(
    run_dir: Path,
    result: dict[str, Any],
    *,
    label: str,
    expected_keys: set[str],
    positive_keys: tuple[str, ...],
    nonnegative_keys: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Bind reported resources to the persisted summary and validate its shape."""
    summary = load_json(_require_regular_file(run_dir, "output/resource-summary.json"))
    if result.get("resources") != summary:
        raise ValueError(f"{label} result resource summary mismatch")

    def real_number(name: str) -> bool:
        return isinstance(summary.get(name), (int, float)) and not isinstance(
            summary.get(name), bool
        )

    if (
        set(summary) != expected_keys
        or any(not real_number(name) or float(summary[name]) <= 0.0 for name in positive_keys)
        or any(
            not real_number(name) or float(summary[name]) < 0.0
            for name in nonnegative_keys
        )
        or not isinstance(summary.get("peak_gpu_compute_memory_bytes"), int)
        or isinstance(summary.get("peak_gpu_compute_memory_bytes"), bool)
        or summary["peak_gpu_compute_memory_bytes"] < 0
        or summary.get("gpu_measurement_status") not in {"measured", "unavailable"}
        or (summary["peak_gpu_compute_memory_bytes"] > 0)
        != (summary["gpu_measurement_status"] == "measured")
        or not isinstance(summary.get("gpu_host_index"), int)
        or isinstance(summary.get("gpu_host_index"), bool)
        or summary["gpu_host_index"] < 0
        or not isinstance(summary.get("gpu_hardware"), list)
        or any(
            not isinstance(summary.get(name), str) or not summary[name]
            for name in ("gpu_memory_scope", "gpu_selection", "host")
        )
    ):
        raise ValueError(f"{label} resource summary contract mismatch")
    ensure_finite(summary, f"{label} resource summary")
    return summary


def _parse_key_value_manifest(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or "=" not in line:
            raise ValueError("malformed classical Insula manifest")
        key, value = line.split("=", 1)
        if not key or key in parsed:
            raise ValueError("malformed classical Insula manifest")
        parsed[key] = value
    return parsed


def _validate_sqlite_database(path: Path) -> None:
    try:
        # `mode=ro` alone still creates WAL/SHM sidecars for a database whose
        # persistent journal mode is WAL.  Validation runs after provenance is
        # sealed, so even empty sidecars would mutate the artifact tree.
        connection = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            tables = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
        finally:
            connection.close()
    except sqlite3.DatabaseError as error:
        raise ValueError("invalid COLMAP SQLite database") from error
    if integrity != ("ok",):
        raise ValueError("invalid COLMAP SQLite database integrity")
    missing = REQUIRED_DATABASE_TABLES - tables
    if missing:
        raise ValueError(f"COLMAP SQLite database missing tables: {sorted(missing)}")


def _ply_vertex_count(path: Path) -> int:
    with path.open("rb") as stream:
        header = bytearray()
        while len(header) <= 65536:
            line = stream.readline()
            if not line:
                break
            header.extend(line)
            if line.strip() == b"end_header":
                break
    try:
        lines = header.decode("ascii").splitlines()
    except UnicodeDecodeError as error:
        raise ValueError("malformed PLY header") from error
    if not lines or lines[0] != "ply" or not any(line.startswith("format ") for line in lines):
        raise ValueError("malformed PLY header")
    if not lines or lines[-1] != "end_header":
        raise ValueError("malformed PLY header")
    vertex_lines = [line for line in lines if line.startswith("element vertex ")]
    if len(vertex_lines) != 1:
        raise ValueError("malformed PLY vertex declaration")
    try:
        count = int(vertex_lines[0].split()[2])
    except (IndexError, ValueError) as error:
        raise ValueError("malformed PLY vertex declaration") from error
    if count < 0:
        raise ValueError("malformed PLY vertex declaration")
    return count


def _validate_required_artifacts(run_dir: Path, metrics: dict[str, Any]) -> None:
    manifest_path = _require_regular_file(run_dir, "input/scene-manifest.json")
    manifest = load_json(manifest_path)
    for frame in manifest.get("frames", []):
        _require_regular_file(run_dir, f"input/images/{frame['name']}")
    required = (
        "adapter.log",
        "report.md",
        "output/database.db",
        "output/colmap-version.txt",
        "output/package-version.txt",
        "output/insula-manifest.txt",
        "output/sparse.ply",
        "output/sparse/0/cameras.bin",
        "output/sparse/0/images.bin",
        "output/sparse/0/points3D.bin",
        "output/sparse/0/cameras.txt",
        "output/sparse/0/images.txt",
        "output/sparse/0/points3D.txt",
    )
    paths = {relative: _require_regular_file(run_dir, relative) for relative in required}
    _validate_sqlite_database(paths["output/database.db"])
    if _ply_vertex_count(paths["output/sparse.ply"]) != metrics["sparse_points"]:
        raise ValueError("PLY vertex count mismatch")
    if _parse_key_value_manifest(paths["output/insula-manifest.txt"]) != PINNED_INSULA_MANIFEST:
        raise ValueError("classical Insula manifest mismatch")


def _adapter_record() -> dict[str, Any]:
    return next(
        item for item in load_json(ROOT / "reference-adapters.json")["adapters"]
        if item["id"] == "colmap-sfm-reference"
    )


def validate_reference_result(run_dir: Path, expected_adapter: str | None = None) -> dict[str, Any]:
    result_path = run_dir / "result.json"
    if not result_path.is_file():
        raise ValueError(f"missing reference result: {result_path}")
    result = load_json(result_path)
    validate_json_schema_instance(result, load_json(ROOT / "reference-result.schema.json"), "reference-result")
    ensure_finite(result, "reference-result")
    if result.get("schema_version") != 1 or result.get("status") != "complete":
        raise ValueError("reference result is not a complete schema-v1 record")
    if expected_adapter is not None and result.get("adapter") != expected_adapter:
        raise ValueError(f"expected adapter {expected_adapter}, got {result.get('adapter')}")
    if result.get("network_mode") != "offline":
        raise ValueError("reference execution must be offline")
    if result.get("module_ids") != ["05"]:
        raise ValueError("module scope mismatch: COLMAP SfM belongs to module 05")
    if result["tool"].get("name") != "COLMAP" or result["tool"].get("container_image") != IMAGE:
        raise ValueError("tool identity mismatch")
    runtime = result["resources"].get("runtime_seconds")
    if isinstance(runtime, bool) or not isinstance(runtime, (int, float)) or runtime < 0:
        raise ValueError("runtime must be a finite non-negative number")
    provenance = result.get("provenance", {})
    actual_config = hashlib.sha256(canonical_json(provenance.get("config"))).hexdigest()
    if provenance.get("config_sha256") != actual_config:
        raise ValueError("config hash mismatch")
    config = provenance["config"]
    validate_run_id(config.get("run_id", ""))
    if (
        config.get("adapter") != result["adapter"]
        or config.get("profile") != result["profile"]
        or config.get("module_ids") != result["module_ids"]
        or config.get("image") != result["tool"]["container_image"]
        or config.get("image_id") != result["tool"]["container_image_id"]
        or config.get("scene_contract_sha256") != sha256_file(ROOT / "shared-scene.json")
    ):
        raise ValueError("reference config binding mismatch")
    actual_implementation = {name: sha256_file(ROOT / name) for name in REFERENCE_IMPLEMENTATION}
    if provenance.get("implementation_sha256") != actual_implementation:
        raise ValueError("implementation hash mismatch")
    actual = _hash_tree(run_dir)
    if actual != provenance.get("artifacts_sha256"):
        raise ValueError("artifact hash mismatch")
    metrics = _parse_colmap_text(run_dir / "output" / "sparse" / "0")
    if metrics != result.get("metrics"):
        raise ValueError("COLMAP metric mismatch")
    _validate_required_artifacts(run_dir, metrics)
    version = (run_dir / "output" / "colmap-version.txt").read_text(encoding="utf-8").strip()
    package_version = (run_dir / "output" / "package-version.txt").read_text(encoding="utf-8").strip()
    if result["tool"]["version"] != version or PINNED_COLMAP_VERSION not in version.split():
        raise ValueError("tool version mismatch")
    if result["tool"]["package_version"] != package_version or package_version != PINNED_COLMAP_PACKAGE_VERSION:
        raise ValueError("tool package version mismatch")
    acceptance = _adapter_record()["acceptance"][result["profile"]]
    if result.get("acceptance") != acceptance or config.get("acceptance") != acceptance:
        raise ValueError("acceptance mismatch")
    if (
        metrics["registered_images"] < acceptance["registered_images_min"]
        or metrics["sparse_points"] < acceptance["sparse_points_min"]
        or metrics["mean_reprojection_error_px"] > acceptance["mean_reprojection_error_px_max"]
    ):
        raise ValueError("COLMAP reconstruction is below the locked acceptance threshold")
    return result


def validate_landed_reference_result(run_dir: Path, adapter: str) -> dict[str, Any]:
    """Dispatch validation for any maintained adapter exposed by ``run.sh``."""
    if adapter == "foundation-geometry":
        from pipeline.foundation_geometry_reference_runner import (
            validate_foundation_geometry_reference_result,
        )

        return validate_foundation_geometry_reference_result(run_dir)
    if adapter == "splatfacto":
        from pipeline.splatfacto_reference_runner import validate_splatfacto_reference_result

        return validate_splatfacto_reference_result(run_dir)
    if adapter == "nerfacto":
        from pipeline.nerfacto_reference_runner import validate_nerfacto_reference_result

        return validate_nerfacto_reference_result(run_dir)
    if adapter == "neus-facto":
        from pipeline.neus_reference_runner import validate_neus_reference_result

        return validate_neus_reference_result(run_dir)
    if adapter == "depth-anything-v2":
        from pipeline.depth_reference_runner import validate_depth_reference_result

        return validate_depth_reference_result(run_dir)
    if adapter == "orb-slam":
        from pipeline.slam_reference_runner import validate_slam_reference_result

        return validate_slam_reference_result(run_dir)
    if adapter == "colmap-mvs":
        from pipeline.mvs_reference_runner import validate_mvs_reference_result

        return validate_mvs_reference_result(run_dir)
    if adapter == ADAPTER:
        return validate_reference_result(run_dir, adapter)
    raise ValueError(f"unknown landed reference adapter: {adapter}")


def _secure_directory(root: Path, name: str) -> Path:
    path = root / name
    if os.path.lexists(path):
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
            raise ValueError(f"cache descendant must be a real directory: {path}")
    else:
        path.mkdir()
    try:
        path.resolve(strict=True).relative_to(root)
    except ValueError as error:
        raise ValueError(f"cache descendant escapes cache root: {path}") from error
    return path


def run_reference(cache_root: Path, adapter: str, profile: str, run_id: str) -> Path:
    validate_run_id(run_id)
    if adapter == "foundation-geometry":
        from pipeline.foundation_geometry_reference_runner import run_foundation_geometry_reference

        return run_foundation_geometry_reference(cache_root, profile, run_id)
    if adapter == "splatfacto":
        from pipeline.splatfacto_reference_runner import run_splatfacto_reference

        return run_splatfacto_reference(cache_root, profile, run_id)
    if adapter == "nerfacto":
        from pipeline.nerfacto_reference_runner import run_nerfacto_reference

        return run_nerfacto_reference(cache_root, profile, run_id)
    if adapter == "neus-facto":
        from pipeline.neus_reference_runner import run_neus_reference

        return run_neus_reference(cache_root, profile, run_id)
    if adapter == "depth-anything-v2":
        from pipeline.depth_reference_runner import run_depth_reference

        return run_depth_reference(cache_root, profile, run_id)
    if adapter == "orb-slam":
        from pipeline.slam_reference_runner import run_slam_reference

        return run_slam_reference(cache_root, profile, run_id)
    if adapter == "colmap-mvs":
        from pipeline.mvs_reference_runner import run_mvs_reference

        return run_mvs_reference(cache_root, profile, run_id)
    if adapter != ADAPTER:
        raise ValueError(f"unknown landed reference adapter: {adapter}")
    if profile not in {"smoke", "full"}:
        raise ValueError(f"unknown profile: {profile}")
    engine = os.environ.get("SURFLO_PATHWAY_CONTAINER_ENGINE", "docker")
    image_id = _inspect_image(engine)
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_root = cache_root.resolve(strict=True)
    runs_root = _secure_directory(cache_root, "reference-runs")
    staging_root = _secure_directory(cache_root, "reference-staging")
    final_parent = runs_root / run_id
    final = final_parent / adapter
    if os.path.lexists(final_parent):
        raise FileExistsError(f"reference run already exists: {final}")
    staging = staging_root / f"{run_id}.{adapter}.{uuid.uuid4().hex}"
    staging.mkdir()
    started = time.perf_counter()
    try:
        scene = load_json(ROOT / "shared-scene.json")
        manifest = generate_colmap_scene(staging / "input", scene, profile)
        command = [
            engine, "run", "--rm", "--network", "none", "--pull=never",
            "--user", f"{os.getuid()}:{os.getgid()}",
            "-v", f"{staging.resolve()}:/work",
            image_id, "bash", "-lc", _container_script(manifest, profile),
        ]
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
        (staging / "adapter.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            raise ValueError(f"COLMAP adapter failed ({completed.returncode}): {completed.stderr.strip()}")
        metrics = _parse_colmap_text(staging / "output" / "sparse" / "0")
        version = (staging / "output" / "colmap-version.txt").read_text(encoding="utf-8").strip()
        if PINNED_COLMAP_VERSION not in version.split():
            raise ValueError(f"COLMAP version mismatch: expected {PINNED_COLMAP_VERSION}, got {version!r}")
        package_version = (staging / "output" / "package-version.txt").read_text(encoding="utf-8").strip()
        if package_version != PINNED_COLMAP_PACKAGE_VERSION:
            raise ValueError(
                f"COLMAP package version mismatch: expected {PINNED_COLMAP_PACKAGE_VERSION}, got {package_version!r}"
            )
        (staging / "report.md").write_text(
            "# COLMAP SfM reference\n\n"
            f"Registered images: {metrics['registered_images']}; sparse points: {metrics['sparse_points']}; "
            f"mean reprojection error: {metrics['mean_reprojection_error_px']:.4f} px.\n",
            encoding="utf-8",
        )
        acceptance = _adapter_record()["acceptance"][profile]
        config = {
            "adapter": adapter,
            "profile": profile,
            "run_id": run_id,
            "module_ids": ["05"],
            "image": IMAGE,
            "image_id": image_id,
            "scene_contract_sha256": sha256_file(ROOT / "shared-scene.json"),
            "acceptance": acceptance,
        }
        result = {
            "schema_version": 1,
            "adapter": adapter,
            "module_ids": ["05"],
            "profile": profile,
            "status": "complete",
            "network_mode": "offline",
            "metrics": metrics,
            "acceptance": acceptance,
            "tool": {
                "name": "COLMAP",
                "version": version,
                "package_version": package_version,
                "container_image": IMAGE,
                "container_image_id": image_id,
            },
            "resources": {"runtime_seconds": time.perf_counter() - started, "host": platform.platform()},
            "provenance": {
                "config": config,
                "config_sha256": hashlib.sha256(canonical_json(config)).hexdigest(),
                "implementation_sha256": {name: sha256_file(ROOT / name) for name in REFERENCE_IMPLEMENTATION},
                "artifacts_sha256": _hash_tree(staging),
            },
        }
        ensure_finite(result, "reference-result")
        write_json(staging / "result.json", result)
        validate_reference_result(staging, adapter)
        final_parent.mkdir()
        os.replace(staging, final)
        return final
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
