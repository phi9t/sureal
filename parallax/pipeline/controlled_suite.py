"""Bind full-profile labs to the validated Blender/Cycles controlled episode."""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
from typing import Any

import numpy as np

from pipeline.contracts import ROOT, canonical_json, load_json, sha256_file


ASSET_ID = "controlled-suite"
COMPATIBLE_MODULES = (
    "01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11",
    "12", "13", "14", "15",
)
_FileFingerprint = tuple[str, int, int, int, int, int]
_VALIDATION_CACHE: dict[
    Path, tuple[tuple[_FileFingerprint, ...], dict[str, Any]]
] = {}


def controlled_suite_record() -> dict[str, Any]:
    records = {
        item["id"]: item for item in load_json(ROOT / "assets.lock.json")["assets"]
    }
    record = records.get(ASSET_ID)
    source = ROOT / "../experiments/photoreal-scenes/recipe.json"
    if (
        not isinstance(record, dict)
        or record.get("mode") != "generated"
        or record.get("source") != "../experiments/photoreal-scenes/recipe.json"
        or record.get("sha256") != sha256_file(source)
        or record.get("episode_id") != "phase-a-v1"
        or record.get("episode_manifest_sha256")
        != "9df5874db09c15b08b708a7164531fea681a7897faf038944d359665067a92f8"
        or record.get("validation_sha256")
        != "a62923fe8cdeb7f7217e114aa391d88acaabfb472573ba18fa451f794ca98351"
        or record.get("artifact_count") != 444
        or record.get("context_views") != 16
        or record.get("target_views_per_hypothesis") != 8
        or record.get("surface_points_per_hypothesis") != 250000
        or record.get("blender_version") != "4.5.14 LTS"
        or record.get("profile") != "benchmark"
        or record.get("samples") != 256
        or record.get("consumers") != list(COMPATIBLE_MODULES)
    ):
        raise ValueError("controlled Blender suite asset lock mismatch")
    return record


def _regular_file(root: Path, relative: str) -> Path:
    candidate = root / relative
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        raise ValueError(f"controlled-suite path escapes or is missing: {relative}") from error
    mode = candidate.lstat().st_mode
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise ValueError(f"controlled-suite artifact is not a regular file: {relative}")
    return candidate


def validate_controlled_suite(
    root: Path, *, lock: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Hash-verify one cached episode and return its compact provenance binding."""
    root = Path(root)
    record = controlled_suite_record() if lock is None else lock
    manifest_path = _regular_file(root, "manifest.json")
    validation_path = _regular_file(root, "validation.json")
    if sha256_file(manifest_path) != record.get("episode_manifest_sha256"):
        raise ValueError("controlled-suite episode manifest hash mismatch")
    if sha256_file(validation_path) != record.get("validation_sha256"):
        raise ValueError("controlled-suite validation hash mismatch")
    manifest = load_json(manifest_path)
    validation = load_json(validation_path)
    artifacts = validation.get("artifact_sha256")
    if (
        validation.get("schema_version") != 1
        or validation.get("status") != "pass"
        or validation.get("episode_manifest_sha256")
        != record.get("episode_manifest_sha256")
        or not isinstance(artifacts, dict)
        or len(artifacts) != record.get("artifact_count")
    ):
        raise ValueError("controlled-suite validation contract mismatch")
    fingerprint_items = []
    for relative in sorted(artifacts):
        path = _regular_file(root, relative)
        metadata = path.stat()
        fingerprint_items.append(
            (
                relative,
                metadata.st_dev,
                metadata.st_ino,
                metadata.st_size,
                metadata.st_mtime_ns,
                metadata.st_ctime_ns,
            )
        )
    fingerprint = tuple(fingerprint_items)
    cached = _VALIDATION_CACHE.get(root.resolve())
    if cached is not None and cached[0] == fingerprint:
        return json.loads(json.dumps(cached[1]))
    for relative, expected in sorted(artifacts.items()):
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise ValueError("controlled-suite artifact registry is malformed")
        if sha256_file(_regular_file(root, relative)) != expected:
            raise ValueError(f"controlled-suite artifact hash mismatch: {relative}")
    renderer = manifest.get("renderer", {})
    counts = validation.get("counts", {})
    if (
        manifest.get("schema_version") != 2
        or manifest.get("task") != "paired_hidden-scene_ambiguity"
        or manifest.get("paired_context", {}).get("pixel_mismatches") != 0
        or renderer.get("blender_version") != record.get("blender_version")
        or renderer.get("profile") != record.get("profile")
        or renderer.get("samples") != record.get("samples")
        or counts.get("context_views") != record.get("context_views")
        or counts.get("target_views_per_scene")
        != record.get("target_views_per_hypothesis")
        or counts.get("surface_points_per_scene")
        != record.get("surface_points_per_hypothesis")
        or validation.get("camera_max_center_error_metres", 1.0) >= 1e-6
    ):
        raise ValueError("controlled-suite Blender/camera/count contract mismatch")
    annotation = manifest.get("annotation_contract", {})
    if (
        annotation.get("coordinate_system") != "opencv_world_to_camera"
        or annotation.get("world_units") != "metres"
        or "camera-axis z" not in str(annotation.get("depth", ""))
        or "Euclidean" not in str(annotation.get("ray_distance", ""))
        or "world-space" not in str(annotation.get("normals", ""))
    ):
        raise ValueError("controlled-suite annotation contract mismatch")
    binding = {
        "asset_id": ASSET_ID,
        "episode_id": record["episode_id"],
        "recipe_sha256": record.get("sha256"),
        "episode_manifest_sha256": record["episode_manifest_sha256"],
        "validation_sha256": record["validation_sha256"],
        "artifact_count": len(artifacts),
        "renderer": {
            "blender_version": renderer["blender_version"],
            "cycles_version": renderer.get("cycles_version"),
            "device": renderer.get("device"),
            "profile": renderer["profile"],
            "samples": renderer["samples"],
            "resolution": renderer.get("resolution"),
            "random_seeds": renderer.get("random_seeds"),
        },
        "views": {
            "context": counts["context_views"],
            "target_per_hypothesis": counts["target_views_per_scene"],
        },
        "surface_points_per_hypothesis": counts["surface_points_per_scene"],
        "camera_max_center_error_metres": validation[
            "camera_max_center_error_metres"
        ],
        "visibility": validation.get("visibility"),
    }
    _VALIDATION_CACHE[root.resolve()] = (fingerprint, binding)
    return json.loads(json.dumps(binding))


def _first_context_arrays(root: Path) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    manifest = load_json(root / "manifest.json")
    records = manifest.get("views", {}).get("shared_context")
    if not isinstance(records, list) or not records:
        raise ValueError("controlled-suite shared context is empty")
    record = records[0]
    required = ("depth", "ray_distance", "geometric_normal", "object_id", "validity")
    arrays: dict[str, np.ndarray] = {}
    for name in required:
        relative = record.get(name)
        if not isinstance(relative, str):
            raise ValueError(f"controlled-suite context record lacks {name}")
        try:
            arrays[name] = np.load(_regular_file(root, relative), allow_pickle=False)
        except (OSError, ValueError) as error:
            raise ValueError(f"controlled-suite {name} array is invalid") from error
    return manifest, arrays


def sensor_summary(root: Path) -> dict[str, Any]:
    """Derive deterministic RGB-D, ToF, and sparse-LiDAR simulations from one render."""
    manifest, arrays = _first_context_arrays(Path(root))
    depth = np.asarray(arrays["depth"], dtype=np.float64)
    ray_distance = np.asarray(arrays["ray_distance"], dtype=np.float64)
    normals = np.asarray(arrays["geometric_normal"], dtype=np.float64)
    object_ids = np.asarray(arrays["object_id"])
    validity = np.asarray(arrays["validity"])
    height, width = depth.shape
    if (
        ray_distance.shape != (height, width)
        or normals.shape != (height, width, 3)
        or object_ids.shape != (height, width)
        or validity.shape != (height, width)
        or validity.dtype != np.bool_
        or not np.array_equal(validity, (depth > 0.0) & (object_ids > 0))
        or not np.all(np.isfinite(depth))
        or not np.all(np.isfinite(ray_distance))
        or not np.all(np.isfinite(normals))
    ):
        raise ValueError("controlled-suite first-view sensor arrays violate their contract")
    valid_count = int(np.count_nonzero(validity))
    if valid_count == 0:
        raise ValueError("controlled-suite first view has no valid sensor support")
    normal_lengths = np.linalg.norm(normals, axis=-1)
    incidence = np.clip(np.abs(normals[..., 2]), 0.0, 1.0)
    structured_missing = validity & ((incidence < 0.25) | (depth > 3.5))
    structured_noise_sigma = 0.0015 + 0.0005 * depth * depth
    tof_bias = 0.0015 * depth * depth + 0.01 * (1.0 - incidence)
    tof_missing = validity & ((incidence < 0.10) | (depth > 8.0))
    lidar_mask = np.zeros_like(validity)
    lidar_stride = max(1, min(height, width) // 32)
    lidar_mask[::lidar_stride, ::lidar_stride] = True
    lidar_mask &= validity
    annotation = manifest["annotation_contract"]
    return {
        "schema_version": 1,
        "source_view": "shared_context/0000",
        "image_shape": [height, width],
        "depth_units": annotation["world_units"],
        "depth_semantics": annotation["depth"],
        "ray_distance_semantics": annotation["ray_distance"],
        "normal_semantics": annotation["normals"],
        "valid_pixels": valid_count,
        "valid_fraction": valid_count / float(height * width),
        "mean_camera_depth_m": float(np.mean(depth[validity])),
        "mean_ray_distance_m": float(np.mean(ray_distance[validity])),
        "unit_normal_max_error": float(
            np.max(np.abs(normal_lengths[validity] - 1.0))
        ),
        "structured_light_missing_fraction": float(
            np.count_nonzero(structured_missing) / valid_count
        ),
        "structured_light_noise_sigma_mean_m": float(
            np.mean(structured_noise_sigma[validity & ~structured_missing])
            if np.any(validity & ~structured_missing)
            else 0.0
        ),
        "tof_missing_fraction": float(np.count_nonzero(tof_missing) / valid_count),
        "tof_bias_mean_m": float(np.mean(tof_bias[validity & ~tof_missing])),
        "lidar_angular_lattice_stride_pixels": lidar_stride,
        "lidar_return_count": int(np.count_nonzero(lidar_mask)),
    }


def write_module_binding(
    root: Path,
    destination: Path,
    module_id: str,
    *,
    lock: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if module_id not in COMPATIBLE_MODULES:
        raise ValueError(f"module {module_id} is not a controlled-suite consumer")
    binding = validate_controlled_suite(root, lock=lock)
    payload = {
        "schema_version": 1,
        "module_id": module_id,
        "purpose": "shared Blender evidence binding; task-specific metrics remain separate",
        "suite": binding,
        "sensor_simulations": sensor_summary(root),
    }
    destination.write_bytes(canonical_json(payload))
    return payload


def candidate_roots() -> list[Path]:
    explicit = os.environ.get("SURFLO_CONTROLLED_SUITE_ROOT")
    if explicit:
        return [Path(explicit).expanduser().resolve()]
    surflo_cache = Path(
        os.environ.get(
            "SURFLO_INSULA_CACHE_ROOT",
            Path.home() / ".cache" / "surflo" / "insula-scout",
        )
    ).expanduser()
    photoreal_cache = Path(
        os.environ.get(
            "PHOTOREAL_CACHE_ROOT",
            Path.home() / ".cache" / "surflo" / "photoreal-scenes",
        )
    ).expanduser()
    return [
        surflo_cache / "photoreal-scenes/episodes/phase-a-v1",
        photoreal_cache / "runs/phase-a-v1",
    ]


def ensure_controlled_suite(*, render_if_missing: bool = False) -> Path:
    errors = []
    for candidate in candidate_roots():
        if not candidate.is_dir():
            continue
        try:
            validate_controlled_suite(candidate)
            return candidate
        except ValueError as error:
            errors.append(f"{candidate}: {error}")
    if render_if_missing:
        command = [
            str(ROOT.parent / "experiments" / "photoreal-scenes" / "run.sh"),
            "render",
            "--run-id",
            "phase-a-v1",
            "--device",
            "OPTIX",
        ]
        completed = subprocess.run(command, cwd=ROOT.parent, check=False)
        if completed.returncode == 0:
            return ensure_controlled_suite(render_if_missing=False)
        errors.append(f"offline Blender render failed with exit code {completed.returncode}")
    detail = "; ".join(errors) if errors else "no candidate episode exists"
    raise ValueError(
        "validated Blender controlled suite is unavailable; run `run.sh build`, "
        "`run.sh fetch --asset controlled-suite`, then retry the full profile: "
        + detail
    )
