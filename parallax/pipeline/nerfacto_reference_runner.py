"""Offline Nerfstudio Nerfacto maintained-reference execution for module 10."""

from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
import platform
from collections import deque
import csv
import shutil
import stat
import subprocess
import tempfile
import time
from typing import Any
import uuid

import numpy as np

from contracts import (
    ROOT,
    canonical_json,
    ensure_finite,
    load_json,
    selected_gpu_device,
    sha256_file,
    validate_json_schema_instance,
    validate_run_id,
    write_json,
)
from fetch import extract_locked_asset
from mvs_reference_runner import _gpu_hardware, _peak_cpu_memory_bytes, _run_monitored
from reference_runner import (
    _hash_tree,
    _inspect_image,
    _parse_key_value_manifest,
    _require_regular_file,
    _secure_directory,
    _validated_resource_summary,
)
from reference_scene import generate_radiance_field_scene


ADAPTER = "nerfacto"
IMAGE = "surflo-pathway-radiance-field:1"
PINNED_NERFSTUDIO_COMMIT = "50e0e3c70c775e89333256213363badbf074f29d"
PINNED_TCNN_COMMIT = "0109538c37ac0bf613f2bac8de6cda48352feca7"
REQUIREMENTS_LOCK_SHA256 = "02c623f2a636dd774dda048f1a08c8d936d0701f74d3f50b3a7916d2280ed65a"
LPIPS_CHECKPOINT_ID = "nerfstudio-lpips-alexnet"
LPIPS_CHECKPOINT_SHA256 = "7be5be791159472b1fbf3c69796f7cb30dca7ad8466c2df70058c37116cdee02"
LPIPS_CHECKPOINT_BYTES = 244408911
LPIPS_CHECKPOINT_FILENAME = "alexnet-owt-7be5be79.pth"
NERF_SYNTHETIC_ASSET_ID = "nerf-synthetic"
NERF_SYNTHETIC_SHA256 = "ce4e94e031c099a19ef04cfb6c71f1e47225d97d365be610b476e379a386c25f"
NERF_SYNTHETIC_BYTES = 370385516
NERF_SYNTHETIC_TREE_SHA256 = "b98a082b13d4b099d54cbcbea474d967cb3f448e9304494ba0749bde874936fe"
IMAGE_ID_PATTERN = __import__("re").compile(r"sha256:[0-9a-f]{64}")
CUDA_CACHE_POLICY = "persistent-cache-root-mount"
PINNED_INSULA_MANIFEST = {
    "schema_version": "1",
    "kind": "radiance-field",
    "cuda": "12.8.1",
    "python": "3.12",
    "torch": "2.7.1+cu128",
    "torchvision": "0.22.1+cu128",
    "pillow": "11.1.0",
    "nerfstudio_commit": PINNED_NERFSTUDIO_COMMIT,
    "tiny_cuda_nn_commit": PINNED_TCNN_COMMIT,
    "tcnn_cuda_architectures": "100",
    "requirements_lock_sha256": REQUIREMENTS_LOCK_SHA256,
    "network_policy": "build-and-fetch-only",
}
SUPPORT_CONTRACT = {
    "render_score_domain": "three held-out target RGB images",
    "geometry_score_domain": "accumulation-qualified target rays on common-visible analytic truth",
    "accumulation_threshold": 0.5,
    "unsupported_domain": "target foreground outside common-visible context support",
    "completion_claim": "none",
    "posterior_sampling_claim": "none",
    "complete_scene_samples": 0,
}
PROFILE_CONFIG = {
    "smoke": {"iterations": 1000, "rays_per_batch": 1024, "density_resolution": 128},
    "full": {"iterations": 20001, "rays_per_batch": 2048, "density_resolution": 256},
}
CANONICAL_NERF_EXAMPLE = {
    "asset_id": NERF_SYNTHETIC_ASSET_ID,
    "dataset": "nerf_synthetic/lego",
    "training_frame_ids": [
        f"train/r_{index}"
        for index in (0, 6, 13, 19, 26, 33, 39, 46, 52, 59, 66, 72, 79, 85, 92, 99)
    ],
    "target_frame_ids": [f"test/r_{index}" for index in (0, 66, 132, 199)],
    "image_size": 256,
    "iterations": 2000,
    "rays_per_batch": 2048,
    "seed": 260925,
}
REFERENCE_IMPLEMENTATION = (
    "pipeline/cli.py",
    "pipeline/contracts.py",
    "pipeline/reference_runner.py",
    "pipeline/mvs_reference_runner.py",
    "pipeline/nerfacto_reference_runner.py",
    "pipeline/reference_scene.py",
    "insulas/build.sh",
    "insulas/radiance-field/Dockerfile",
    "insulas/radiance-field/requirements.lock.txt",
    "insulas/radiance-field/resolved-requirements.lock.txt",
    "insulas/radiance-field/run-nerfacto.py",
    "insulas/locks.json",
    "assets.lock.json",
    "reference-result.schema.json",
    "shared-scene.json",
)


def _verify_container_entrypoint(engine: str, image_id: str) -> None:
    if Path(engine).name != "docker":
        return
    expected = sha256_file(ROOT / "insulas/radiance-field/run-nerfacto.py")
    try:
        completed = subprocess.run(
            [
                engine,
                "run",
                "--rm",
                "--network",
                "none",
                "--pull=never",
                image_id,
                "sha256sum",
                "/usr/local/bin/run-nerfacto.py",
            ],
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired as error:
        raise ValueError("unable to verify Nerfacto container entrypoint") from error
    embedded = None
    for line in completed.stdout.splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[1] == "/usr/local/bin/run-nerfacto.py":
            embedded = fields[0]
            break
    if completed.returncode != 0 or embedded != expected:
        raise ValueError(
            "stale Nerfacto container entrypoint; rebuild with `run.sh build`"
        )


def _values_match(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        return (
            isinstance(actual, dict)
            and actual.keys() == expected.keys()
            and all(_values_match(actual[key], value) for key, value in expected.items())
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(_values_match(left, right) for left, right in zip(actual, expected))
        )
    if isinstance(expected, bool):
        return isinstance(actual, bool) and actual is expected
    if isinstance(expected, int):
        return type(actual) is int and actual == expected
    if isinstance(expected, float):
        return type(actual) is float and math.isclose(actual, expected, rel_tol=1e-6, abs_tol=1e-8)
    return type(actual) is type(expected) and actual == expected


def _adapter_record() -> dict[str, Any]:
    return next(
        item
        for item in load_json(ROOT / "reference-adapters.json")["adapters"]
        if item["id"] == "nerfstudio-nerfacto-reference"
    )


def _adapter_execution_contract_sha256() -> str:
    record = _adapter_record()
    contract = {
        key: record[key]
        for key in (
            "id",
            "command",
            "modules",
            "status",
            "model_contract",
            "evaluation_contract",
        )
    }
    if "acceptance" in record:
        contract["acceptance"] = record["acceptance"]
    return hashlib.sha256(canonical_json(contract)).hexdigest()


def _lpips_checkpoint_record() -> dict[str, Any]:
    matches = [
        item
        for item in load_json(ROOT / "assets.lock.json")["assets"]
        if item.get("id") == LPIPS_CHECKPOINT_ID
    ]
    if len(matches) != 1:
        raise ValueError("Nerfacto LPIPS checkpoint asset registry mismatch")
    record = matches[0]
    if (
        record.get("mode") != "download"
        or record.get("sha256") != LPIPS_CHECKPOINT_SHA256
        or record.get("byte_size") != LPIPS_CHECKPOINT_BYTES
        or set(record.get("consumers", []))
        != {
            "nerfstudio-neus-facto-reference",
            "nerfstudio-nerfacto-reference",
            "nerfstudio-splatfacto-reference",
        }
        or not str(record.get("source", "")).endswith(LPIPS_CHECKPOINT_FILENAME)
    ):
        raise ValueError("Nerfacto LPIPS checkpoint lock mismatch")
    return record


def _nerf_synthetic_record() -> dict[str, Any]:
    matches = [
        item
        for item in load_json(ROOT / "assets.lock.json")["assets"]
        if item.get("id") == NERF_SYNTHETIC_ASSET_ID
    ]
    if len(matches) != 1:
        raise ValueError("NeRF example asset registry mismatch")
    record = matches[0]
    if (
        record.get("mode") != "download"
        or record.get("sha256") != NERF_SYNTHETIC_SHA256
        or record.get("byte_size") != NERF_SYNTHETIC_BYTES
        or record.get("digest_status") != "verified_2026-09-26"
        or record.get("archive_format") != "zip"
        or record.get("extraction")
        != {"mode": "zip", "roots": ["nerf_llff_data", "nerf_synthetic"]}
        or record.get("tree_sha256") != NERF_SYNTHETIC_TREE_SHA256
        or record.get("tree_file_count") != 873
        or record.get("tree_byte_size") != 385357718
        or record.get("consumers") != ["nerfstudio-nerfacto-reference"]
    ):
        raise ValueError("NeRF example asset lock mismatch")
    return record


def _locked_nerf_example(
    cache_root: Path, record: dict[str, Any] | None = None
) -> tuple[Path, dict[str, Any]]:
    """Return the verified Lego example and its recomputed extraction witness."""

    record = _nerf_synthetic_record() if record is None else record
    assets = cache_root / "assets"
    archive = assets / f"{NERF_SYNTHETIC_ASSET_ID}.archive"
    try:
        mode = archive.lstat().st_mode
    except FileNotFoundError as error:
        raise FileNotFoundError(
            f"missing NeRF example archive: {archive}; "
            f"run `run.sh fetch --asset {NERF_SYNTHETIC_ASSET_ID}`"
        ) from error
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise ValueError("NeRF example archive must be a regular non-symlink file")
    if (
        archive.stat().st_size != record.get("byte_size")
        or sha256_file(archive) != record.get("sha256")
    ):
        raise ValueError("NeRF example archive hash or byte-size mismatch")
    extracted = extract_locked_asset(record, archive, assets)
    extraction = load_json(assets / f"{NERF_SYNTHETIC_ASSET_ID}.extraction.json")
    if (
        extraction.get("archive_sha256") != record.get("sha256")
        or extraction.get("tree_sha256") != record.get("tree_sha256")
        or extraction.get("file_count") != record.get("tree_file_count")
        or sum(item.get("size", -1) for item in extraction.get("files", []))
        != record.get("tree_byte_size")
    ):
        raise ValueError("NeRF example extraction tree does not match its lock")
    lego = extracted / "nerf_synthetic" / "lego"
    for name in ("transforms_train.json", "transforms_val.json", "transforms_test.json"):
        _require_regular_file(lego, name)
    return lego, extraction


def _lpips_checkpoint_path(cache_root: Path, record: dict[str, Any]) -> Path:
    path = cache_root / "assets" / f"{LPIPS_CHECKPOINT_ID}.archive"
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as error:
        raise FileNotFoundError(
            f"missing Nerfacto LPIPS checkpoint: {path}; "
            f"run `run.sh fetch --asset {LPIPS_CHECKPOINT_ID}`"
        ) from error
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise ValueError("Nerfacto LPIPS checkpoint must be a regular non-symlink file")
    if path.stat().st_size != record["byte_size"] or sha256_file(path) != record["sha256"]:
        raise ValueError("Nerfacto LPIPS checkpoint hash or byte-size mismatch")
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(cache_root.resolve(strict=True))
    except ValueError as error:
        raise ValueError("Nerfacto LPIPS checkpoint escapes the cache root") from error
    return resolved


def _regular_npy(path: Path, label: str) -> np.ndarray:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as error:
        raise ValueError(f"missing Nerfacto {label}: {path.name}") from error
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise ValueError(f"Nerfacto {label} is not a regular file: {path.name}")
    try:
        return np.load(path, allow_pickle=False)
    except (OSError, ValueError) as error:
        raise ValueError(f"malformed Nerfacto {label}: {path.name}") from error


def _validate_input_manifest(input_root: Path, profile: str) -> dict[str, Any]:
    manifest = load_json(_require_regular_file(input_root.parent, "input/manifest.json"))
    with tempfile.TemporaryDirectory(prefix="surflo-nerfacto-manifest-") as temporary:
        expected_root = Path(temporary) / "input"
        expected = generate_radiance_field_scene(
            expected_root, load_json(ROOT / "shared-scene.json"), profile
        )
        if manifest != expected:
            raise ValueError("Nerfacto input manifest does not match the shared-scene contract")
        path_hash_pairs = [
            (expected["nerfstudio_transforms_path"], expected["nerfstudio_transforms_sha256"]),
            (expected["sdfstudio_metadata_path"], expected["sdfstudio_metadata_sha256"]),
        ]
        for frame in expected["context_frames"] + expected["target_frames"]:
            for path_key, hash_key in (
                ("image_path", "image_sha256"),
                ("mask_path", "mask_sha256"),
                ("depth_path", "depth_sha256"),
                ("normal_path", "normal_sha256"),
                ("rgb_truth_path", "rgb_truth_sha256"),
                ("common_visible_mask_path", "common_visible_mask_sha256"),
            ):
                path_hash_pairs.append((frame[path_key], frame[hash_key]))
        truth = expected["surface_truth"]
        path_hash_pairs.extend(
            (truth[path_key], truth[hash_key])
            for path_key, hash_key in (
                ("points_path", "points_sha256"),
                ("normals_path", "normals_sha256"),
                ("support_path", "support_sha256"),
            )
        )
        for relative, expected_hash in path_hash_pairs:
            actual = _require_regular_file(input_root, relative)
            if sha256_file(actual) != expected_hash or sha256_file(expected_root / relative) != expected_hash:
                raise ValueError(f"Nerfacto input hash mismatch: {relative}")
            try:
                actual.resolve(strict=True).relative_to(input_root.resolve(strict=True))
            except ValueError as error:
                raise ValueError(f"Nerfacto input escapes input root: {relative}") from error
    return manifest


def _nearest(query: np.ndarray, target: np.ndarray) -> np.ndarray:
    target_norm = np.sum(target * target, axis=1)
    distances = np.empty(len(query), dtype=np.float64)
    for start in range(0, len(query), 256):
        batch = query[start : start + 256]
        squared = (
            np.sum(batch * batch, axis=1, keepdims=True)
            + target_norm
            - 2.0 * batch @ target.T
        )
        distances[start : start + len(batch)] = np.sqrt(
            np.maximum(np.min(squared, axis=1), 0.0)
        )
    return distances


def _sample_points(points: np.ndarray, maximum: int = 4096) -> np.ndarray:
    if len(points) <= maximum:
        return points
    indices = np.linspace(0, len(points) - 1, maximum, dtype=np.int64)
    return points[indices]


def _points_from_depth(
    depth: np.ndarray,
    mask: np.ndarray,
    frame: dict[str, Any],
    intrinsics: dict[str, Any],
) -> np.ndarray:
    rows, columns = np.nonzero(mask)
    z = depth[rows, columns].astype(np.float64)
    camera = np.column_stack(
        (
            (columns - float(intrinsics["cx"])) / float(intrinsics["fx"]) * z,
            (rows - float(intrinsics["cy"])) / float(intrinsics["fy"]) * z,
            z,
        )
    )
    transform = np.asarray(frame["camera_to_world_model"], dtype=np.float64)
    return camera @ transform[:3, :3].T + transform[:3, 3]


def _gaussian_ssim(left: np.ndarray, right: np.ndarray) -> float:
    """Compute a fixed 11x11 Gaussian-window RGB SSIM using NumPy only."""
    if left.shape != right.shape or left.ndim != 3 or left.shape[2] != 3:
        raise ValueError("SSIM expects matching HxWx3 RGB arrays")
    if left.shape[0] < 11 or left.shape[1] < 11:
        raise ValueError("SSIM image or crop is smaller than the fixed 11x11 window")
    x = left.astype(np.float64, copy=False)
    y = right.astype(np.float64, copy=False)
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("SSIM inputs must be finite")
    axis = np.arange(-5, 6, dtype=np.float64)
    kernel = np.exp(-(axis * axis) / (2.0 * 1.5 * 1.5))
    kernel /= np.sum(kernel)

    def blur(image: np.ndarray) -> np.ndarray:
        horizontal_source = np.pad(image, ((0, 0), (5, 5), (0, 0)), mode="reflect")
        horizontal = sum(
            float(weight) * horizontal_source[:, index : index + image.shape[1], :]
            for index, weight in enumerate(kernel)
        )
        vertical_source = np.pad(horizontal, ((5, 5), (0, 0), (0, 0)), mode="reflect")
        return sum(
            float(weight) * vertical_source[index : index + image.shape[0], :, :]
            for index, weight in enumerate(kernel)
        )

    mu_x = blur(x)
    mu_y = blur(y)
    sigma_x = np.maximum(blur(x * x) - mu_x * mu_x, 0.0)
    sigma_y = np.maximum(blur(y * y) - mu_y * mu_y, 0.0)
    sigma_xy = blur(x * y) - mu_x * mu_y
    c1 = 0.01 ** 2
    c2 = 0.03 ** 2
    numerator = (2.0 * mu_x * mu_y + c1) * (2.0 * sigma_xy + c2)
    denominator = (mu_x * mu_x + mu_y * mu_y + c1) * (sigma_x + sigma_y + c2)
    return float(np.mean(numerator / denominator))


def _tight_foreground_crop(mask: np.ndarray) -> tuple[slice, slice]:
    rows, columns = np.nonzero(mask)
    if not len(rows):
        raise ValueError("foreground crop has no truth support")
    return (
        slice(int(np.min(rows)), int(np.max(rows)) + 1),
        slice(int(np.min(columns)), int(np.max(columns)) + 1),
    )


def _psnr(predicted: np.ndarray, truth: np.ndarray) -> float:
    mse = float(np.mean((predicted.astype(np.float64) - truth.astype(np.float64)) ** 2))
    if not math.isfinite(mse) or mse <= 0.0:
        raise ValueError("PSNR requires a finite non-zero residual")
    return float(-10.0 * math.log10(mse))


def _component_count(mask: np.ndarray) -> int:
    """Count 6-connected components on a small diagnostic grid."""
    if mask.ndim != 3:
        raise ValueError("component mask must be a 3D grid")
    visited = np.zeros(mask.shape, dtype=bool)
    components = 0
    for seed in np.argwhere(mask):
        x, y, z = (int(value) for value in seed)
        if visited[x, y, z]:
            continue
        components += 1
        visited[x, y, z] = True
        queue: deque[tuple[int, int, int]] = deque([(x, y, z)])
        while queue:
            cx, cy, cz = queue.popleft()
            for nx, ny, nz in (
                (cx - 1, cy, cz),
                (cx + 1, cy, cz),
                (cx, cy - 1, cz),
                (cx, cy + 1, cz),
                (cx, cy, cz - 1),
                (cx, cy, cz + 1),
            ):
                if (
                    0 <= nx < mask.shape[0]
                    and 0 <= ny < mask.shape[1]
                    and 0 <= nz < mask.shape[2]
                    and mask[nx, ny, nz]
                    and not visited[nx, ny, nz]
                ):
                    visited[nx, ny, nz] = True
                    queue.append((nx, ny, nz))
    return components


def _image_metrics(
    predicted: np.ndarray,
    truth: np.ndarray,
    foreground: np.ndarray,
    perceptual: dict[str, Any],
) -> dict[str, float]:
    crop = _tight_foreground_crop(foreground)
    predicted_crop = predicted[crop]
    truth_crop = truth[crop]
    return {
        "psnr_db": _psnr(predicted, truth),
        "foreground_psnr_db": _psnr(predicted[foreground], truth[foreground]),
        "ssim": _gaussian_ssim(predicted, truth),
        "crop_psnr_db": _psnr(predicted_crop, truth_crop),
        "crop_ssim": _gaussian_ssim(predicted_crop, truth_crop),
        "lpips": float(perceptual["lpips"]),
        "crop_lpips": float(perceptual["crop_lpips"]),
    }


def _validate_failure_sweep(run_dir: Path, metrics: dict[str, Any]) -> None:
    path = _require_regular_file(run_dir, "output/failure_sweep.csv")
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != [
            "factor",
            "value",
            "metric",
            "measurement",
            "interpretation",
        ]:
            raise ValueError("Nerfacto failure-sweep columns mismatch")
        rows = list(reader)
    expected: dict[tuple[str, str, str], float | int] = {}
    for count, values in metrics["failure_sweep"].items():
        expected[("context_view_count", count, "target_psnr_db")] = values[
            "target_psnr_db"
        ]
        expected[("context_view_count", count, "expected_depth_rmse_m")] = values[
            "expected_depth_rmse_m"
        ]
    field = metrics["field"]
    for value, label in (("0.1", "0_1"), ("1.0", "1"), ("10.0", "10"), ("100.0", "100")):
        expected[("density_threshold", value, "occupied_fraction")] = field[
            f"occupied_fraction_ge_{label}"
        ]
        expected[
            (
                "density_threshold",
                value,
                f"component_count_{field['component_grid_resolution']}cube",
            )
        ] = field[f"component_count_ge_{label}"]
    actual: dict[tuple[str, str, str], float] = {}
    for row in rows:
        key = (row["factor"], row["value"], row["metric"])
        if key in actual or not row["interpretation"]:
            raise ValueError("Nerfacto failure-sweep row mismatch")
        try:
            actual[key] = float(row["measurement"])
        except ValueError as error:
            raise ValueError("Nerfacto failure-sweep value mismatch") from error
    if actual.keys() != expected.keys() or any(
        not math.isclose(actual[key], float(value), rel_tol=1e-6, abs_tol=1e-8)
        for key, value in expected.items()
    ):
        raise ValueError("Nerfacto failure-sweep metric mismatch")


def _evaluate_canonical_nerf_example(run_dir: Path) -> dict[str, Any]:
    root = run_dir / "output" / "canonical-nerf-example"
    manifest = load_json(_require_regular_file(root, "manifest.json"))
    target_rows = [
        {
            "id": frame_id,
            "truth_path": f"truth/target-{ordinal:03d}.rgb.float32.npy",
            "render_path": f"renders/target-{ordinal:03d}.rgb.float32.npy",
        }
        for ordinal, frame_id in enumerate(CANONICAL_NERF_EXAMPLE["target_frame_ids"])
    ]
    expected_manifest = {
        "schema_version": 1,
        "asset_id": NERF_SYNTHETIC_ASSET_ID,
        "archive_sha256": NERF_SYNTHETIC_SHA256,
        "extraction_tree_sha256": NERF_SYNTHETIC_TREE_SHA256,
        "dataset": CANONICAL_NERF_EXAMPLE["dataset"],
        "training_frame_ids": CANONICAL_NERF_EXAMPLE["training_frame_ids"],
        "target_frame_ids": CANONICAL_NERF_EXAMPLE["target_frame_ids"],
        "image_size": [
            CANONICAL_NERF_EXAMPLE["image_size"],
            CANONICAL_NERF_EXAMPLE["image_size"],
        ],
        "iterations": CANONICAL_NERF_EXAMPLE["iterations"],
        "rays_per_batch": CANONICAL_NERF_EXAMPLE["rays_per_batch"],
        "seed": CANONICAL_NERF_EXAMPLE["seed"],
        "targets": target_rows,
    }
    if manifest != expected_manifest:
        raise ValueError("canonical NeRF example manifest mismatch")
    image_size = int(CANONICAL_NERF_EXAMPLE["image_size"])
    per_view: list[dict[str, Any]] = []
    for row in target_rows:
        truth = _regular_npy(root / row["truth_path"], "canonical truth RGB")
        predicted = _regular_npy(root / row["render_path"], "canonical rendered RGB")
        if (
            truth.dtype != np.float32
            or predicted.dtype != np.float32
            or truth.shape != (image_size, image_size, 3)
            or predicted.shape != truth.shape
            or not np.isfinite(truth).all()
            or not np.isfinite(predicted).all()
            or np.any(truth < 0.0)
            or np.any(truth > 1.0)
            or np.any(predicted < 0.0)
            or np.any(predicted > 1.0)
        ):
            raise ValueError("canonical NeRF example render shape, dtype, range, or finiteness mismatch")
        per_view.append(
            {
                "id": row["id"],
                "psnr_db": _psnr(predicted, truth),
                "ssim": _gaussian_ssim(predicted, truth),
            }
        )
    result = {
        "asset_id": NERF_SYNTHETIC_ASSET_ID,
        "archive_sha256": NERF_SYNTHETIC_SHA256,
        "extraction_tree_sha256": NERF_SYNTHETIC_TREE_SHA256,
        "dataset": CANONICAL_NERF_EXAMPLE["dataset"],
        "training_views": len(CANONICAL_NERF_EXAMPLE["training_frame_ids"]),
        "target_views": len(per_view),
        "iterations": CANONICAL_NERF_EXAMPLE["iterations"],
        "rays_per_batch": CANONICAL_NERF_EXAMPLE["rays_per_batch"],
        "image_size": image_size,
        "target_psnr_db": float(np.mean([row["psnr_db"] for row in per_view])),
        "target_ssim": float(np.mean([row["ssim"] for row in per_view])),
        "target_per_view": per_view,
    }
    ensure_finite(result, "canonical NeRF example metrics")
    return result


def _evaluate_outputs(run_dir: Path, profile: str) -> dict[str, Any]:
    manifest = _validate_input_manifest(run_dir / "input", profile)
    target_perceptual = load_json(
        _require_regular_file(run_dir, "output/target-image-metrics.json")
    )
    context_perceptual = load_json(
        _require_regular_file(run_dir, "output/context-image-metrics.json")
    )
    if [item.get("id") for item in target_perceptual] != [
        frame["id"] for frame in manifest["target_frames"]
    ]:
        raise ValueError("Nerfacto target metric inventory mismatch")
    frame_by_id = {
        frame["id"]: frame
        for frame in manifest["context_frames"] + manifest["target_frames"]
    }
    primary_contexts = [frame_by_id[item] for item in manifest["primary_context_frame_ids"]]
    if [item.get("id") for item in context_perceptual] != [
        frame["id"] for frame in primary_contexts
    ]:
        raise ValueError("Nerfacto context metric inventory mismatch")

    target_image_metrics: list[dict[str, Any]] = []
    context_image_metrics: list[dict[str, Any]] = []
    median_residuals: list[np.ndarray] = []
    expected_residuals: list[np.ndarray] = []
    qualified_truth_depths: list[np.ndarray] = []
    unsupported_residuals: list[np.ndarray] = []
    unsupported_truth_depths: list[np.ndarray] = []
    predicted_points: list[np.ndarray] = []
    truth_points: list[np.ndarray] = []
    supported_total = 0
    supported_qualified = 0
    unsupported_total = 0
    unsupported_qualified = 0
    intrinsics = manifest["intrinsics"]
    for frame, perceptual in zip(manifest["target_frames"], target_perceptual):
        prefix = run_dir / "output/target-renders" / frame["id"]
        predicted_rgb = _regular_npy(Path(f"{prefix}.rgb.float32.npy"), "target RGB float")
        truth_rgb = _regular_npy(run_dir / "input" / frame["rgb_truth_path"], "truth RGB").astype(np.float64) / 255.0
        accumulation = _regular_npy(Path(f"{prefix}.accumulation.npy"), "target accumulation")
        median_depth = _regular_npy(Path(f"{prefix}.median-camera-depth.npy"), "target median depth")
        expected_depth = _regular_npy(Path(f"{prefix}.expected-camera-depth.npy"), "target expected depth")
        truth_depth = _regular_npy(run_dir / "input" / frame["depth_path"], "truth depth")
        common = _regular_npy(run_dir / "input" / frame["common_visible_mask_path"], "target support").astype(bool)
        shape = truth_depth.shape
        if (
            predicted_rgb.shape != (*shape, 3)
            or truth_rgb.shape != predicted_rgb.shape
            or any(array.shape != shape for array in (accumulation, median_depth, expected_depth, common))
            or not all(np.isfinite(array).all() for array in (predicted_rgb, accumulation, median_depth, expected_depth))
            or np.any(accumulation < 0.0)
            or np.any(accumulation > 1.0001)
        ):
            raise ValueError("Nerfacto target render shape, range, or finiteness mismatch")
        foreground = truth_depth > 0.0
        image_metrics = {
            "id": frame["id"],
            **_image_metrics(predicted_rgb, truth_rgb, foreground, perceptual),
        }
        if image_metrics["lpips"] < 0.0 or image_metrics["crop_lpips"] < 0.0:
            raise ValueError("Nerfacto perceptual metrics must be non-negative")
        target_image_metrics.append(image_metrics)

        qualified = accumulation >= SUPPORT_CONTRACT["accumulation_threshold"]
        supported = foreground & common
        unsupported = foreground & ~common
        supported_valid = supported & qualified & (median_depth > 0.0) & (expected_depth > 0.0)
        unsupported_valid = unsupported & qualified & (expected_depth > 0.0)
        supported_total += int(np.count_nonzero(supported))
        supported_qualified += int(np.count_nonzero(supported_valid))
        unsupported_total += int(np.count_nonzero(unsupported))
        unsupported_qualified += int(np.count_nonzero(unsupported_valid))
        if np.any(supported_valid):
            median_residuals.append(median_depth[supported_valid] - truth_depth[supported_valid])
            expected_residuals.append(expected_depth[supported_valid] - truth_depth[supported_valid])
            qualified_truth_depths.append(truth_depth[supported_valid])
            predicted_points.append(
                _points_from_depth(expected_depth, supported_valid, frame, intrinsics)
            )
            truth_points.append(_points_from_depth(truth_depth, supported, frame, intrinsics))
        if np.any(unsupported_valid):
            unsupported_residuals.append(
                expected_depth[unsupported_valid] - truth_depth[unsupported_valid]
            )
            unsupported_truth_depths.append(truth_depth[unsupported_valid])

    if not median_residuals or supported_total == 0:
        raise ValueError("Nerfacto has no accumulation-qualified common-visible target rays")

    predicted_xyz = _sample_points(np.concatenate(predicted_points, axis=0))
    truth_xyz = _sample_points(np.concatenate(truth_points, axis=0))
    accuracy = _nearest(predicted_xyz, truth_xyz)
    completeness = _nearest(truth_xyz, predicted_xyz)
    median_residual = np.concatenate(median_residuals).astype(np.float64)
    expected_residual = np.concatenate(expected_residuals).astype(np.float64)
    qualified_truth_depth = np.concatenate(qualified_truth_depths).astype(np.float64)
    geometry: dict[str, float | int] = {
        "common_visible_truth_rays": supported_total,
        "common_visible_qualified_rays": supported_qualified,
        "common_visible_accumulation_coverage": supported_qualified / supported_total,
        "median_depth_rmse_m": float(np.sqrt(np.mean(median_residual * median_residual))),
        "median_depth_abs_rel": float(
            np.mean(np.abs(median_residual) / qualified_truth_depth)
        ),
        "expected_depth_rmse_m": float(np.sqrt(np.mean(expected_residual * expected_residual))),
        "expected_depth_abs_rel": float(
            np.mean(np.abs(expected_residual) / qualified_truth_depth)
        ),
        "point_accuracy_rmse_m": float(np.sqrt(np.mean(accuracy * accuracy))),
        "point_completeness_rmse_m": float(np.sqrt(np.mean(completeness * completeness))),
        "point_samples_predicted": int(len(predicted_xyz)),
        "point_samples_truth": int(len(truth_xyz)),
    }
    for threshold_cm in (2, 5, 10):
        threshold = threshold_cm / 100.0
        precision = float(np.mean(accuracy <= threshold))
        recall = float(np.mean(completeness <= threshold))
        geometry[f"point_precision_{threshold_cm}cm"] = precision
        geometry[f"point_recall_{threshold_cm}cm"] = recall
        geometry[f"point_fscore_{threshold_cm}cm"] = 0.0 if precision + recall == 0.0 else 2.0 * precision * recall / (precision + recall)

    resolution = PROFILE_CONFIG[profile]["density_resolution"]
    density = _regular_npy(run_dir / "output/field.density_grid.float32.npy", "density grid")
    if density.dtype != np.float32 or density.shape != (resolution,) * 3 or not np.isfinite(density).all() or np.any(density < 0.0):
        raise ValueError("Nerfacto density grid shape, dtype, or values mismatch")
    component_resolution = min(32, resolution)
    component_indices = np.linspace(
        0, resolution - 1, component_resolution, dtype=np.int64
    )
    component_grid = density[np.ix_(component_indices, component_indices, component_indices)]
    field: dict[str, float | int] = {
        "density_min": float(np.min(density)),
        "density_median": float(np.median(density)),
        "density_p95": float(np.quantile(density, 0.95)),
        "density_max": float(np.max(density)),
        "occupied_fraction_ge_0_1": float(np.mean(density >= 0.1)),
        "occupied_fraction_ge_1": float(np.mean(density >= 1.0)),
        "occupied_fraction_ge_10": float(np.mean(density >= 10.0)),
        "occupied_fraction_ge_100": float(np.mean(density >= 100.0)),
        "component_grid_resolution": component_resolution,
    }
    for label, threshold in (("0_1", 0.1), ("1", 1.0), ("10", 10.0), ("100", 100.0)):
        field[f"component_count_ge_{label}"] = _component_count(
            component_grid >= threshold
        )

    for frame, perceptual in zip(primary_contexts, context_perceptual):
        prefix = run_dir / "output/context-renders" / frame["id"]
        predicted = _regular_npy(Path(f"{prefix}.rgb.float32.npy"), "context RGB float")
        truth = _regular_npy(
            run_dir / "input" / frame["rgb_truth_path"], "context truth RGB"
        ).astype(np.float64) / 255.0
        truth_depth = _regular_npy(
            run_dir / "input" / frame["depth_path"], "context truth depth"
        )
        if predicted.shape != truth.shape or not np.isfinite(predicted).all():
            raise ValueError("Nerfacto context render shape or finiteness mismatch")
        context_image_metrics.append(
            {
                "id": frame["id"],
                **_image_metrics(predicted, truth, truth_depth > 0.0, perceptual),
            }
        )

    sweep: dict[str, dict[str, float | int]] = {}
    for count in (3, 5, 9):
        psnrs: list[float] = []
        depth_residuals: list[np.ndarray] = []
        for frame in manifest["target_frames"]:
            prefix = run_dir / "output/view-sweep" / f"views-{count}" / frame["id"]
            predicted = _regular_npy(Path(f"{prefix}.rgb.float32.npy"), "sweep target RGB")
            expected_depth = _regular_npy(
                Path(f"{prefix}.expected-camera-depth.npy"), "sweep expected depth"
            )
            accumulation = _regular_npy(
                Path(f"{prefix}.accumulation.npy"), "sweep accumulation"
            )
            truth = _regular_npy(
                run_dir / "input" / frame["rgb_truth_path"], "sweep truth RGB"
            ).astype(np.float64) / 255.0
            truth_depth = _regular_npy(
                run_dir / "input" / frame["depth_path"], "sweep truth depth"
            )
            common = _regular_npy(
                run_dir / "input" / frame["common_visible_mask_path"],
                "sweep support",
            ).astype(bool)
            if (
                predicted.shape != truth.shape
                or expected_depth.shape != truth_depth.shape
                or accumulation.shape != truth_depth.shape
                or not all(
                    np.isfinite(value).all()
                    for value in (predicted, expected_depth, accumulation)
                )
            ):
                raise ValueError("Nerfacto view-sweep output mismatch")
            psnrs.append(_psnr(predicted, truth))
            valid = (
                (truth_depth > 0.0)
                & common
                & (accumulation >= SUPPORT_CONTRACT["accumulation_threshold"])
                & (expected_depth > 0.0)
            )
            if np.any(valid):
                depth_residuals.append(expected_depth[valid] - truth_depth[valid])
        if not depth_residuals:
            raise ValueError("Nerfacto view sweep has no qualified geometry support")
        residual = np.concatenate(depth_residuals).astype(np.float64)
        sweep[str(count)] = {
            "context_views": count,
            "iterations": 1000,
            "rays_per_batch": 1024,
            "target_psnr_db": float(np.mean(psnrs)),
            "expected_depth_rmse_m": float(np.sqrt(np.mean(residual * residual))),
        }

    unsupported_residual = (
        np.concatenate(unsupported_residuals).astype(np.float64)
        if unsupported_residuals
        else np.empty(0, dtype=np.float64)
    )
    unsupported_truth_depth = (
        np.concatenate(unsupported_truth_depths).astype(np.float64)
        if unsupported_truth_depths
        else np.empty(0, dtype=np.float64)
    )

    def mean_metric(rows: list[dict[str, Any]], key: str) -> float:
        return float(np.mean([float(row[key]) for row in rows]))

    metrics = {
        "rendering": {
            "metric_implementation": "host-numpy-gaussian-ssim-v1; LPIPS from pinned container",
            "target_psnr_db": mean_metric(target_image_metrics, "psnr_db"),
            "target_foreground_psnr_db": mean_metric(
                target_image_metrics, "foreground_psnr_db"
            ),
            "target_ssim": mean_metric(target_image_metrics, "ssim"),
            "target_crop_psnr_db": mean_metric(target_image_metrics, "crop_psnr_db"),
            "target_crop_ssim": mean_metric(target_image_metrics, "crop_ssim"),
            "target_lpips": mean_metric(target_image_metrics, "lpips"),
            "target_crop_lpips": mean_metric(target_image_metrics, "crop_lpips"),
            "target_views": len(target_image_metrics),
            "target_per_view": target_image_metrics,
            "context_fit_psnr_db": mean_metric(context_image_metrics, "psnr_db"),
            "context_fit_ssim": mean_metric(context_image_metrics, "ssim"),
            "context_fit_lpips": mean_metric(context_image_metrics, "lpips"),
            "context_fit_views": len(context_image_metrics),
            "context_fit_per_view": context_image_metrics,
        },
        "geometry": geometry,
        "field": field,
        "failure_sweep": sweep,
        "unsupported": {
            "truth_rays": unsupported_total,
            "accumulation_qualified_rays": unsupported_qualified,
            "accumulation_coverage": 0.0 if unsupported_total == 0 else unsupported_qualified / unsupported_total,
            "expected_depth_rmse_m": 0.0
            if not len(unsupported_residual)
            else float(np.sqrt(np.mean(unsupported_residual * unsupported_residual))),
            "expected_depth_abs_rel": 0.0
            if not len(unsupported_residual)
            else float(
                np.mean(np.abs(unsupported_residual) / unsupported_truth_depth)
            ),
            "completion_claim": "none",
        },
    }
    if profile == "full":
        metrics["canonical_nerf_example"] = _evaluate_canonical_nerf_example(run_dir)
    ensure_finite(metrics, "Nerfacto scored metrics")
    _validate_failure_sweep(run_dir, metrics)
    return metrics


def _validate_runtime_identity(run_dir: Path, profile: str) -> dict[str, Any]:
    if _require_regular_file(run_dir, "output/source-commit.txt").read_text().strip() != PINNED_NERFSTUDIO_COMMIT:
        raise ValueError("Nerfstudio source commit mismatch")
    if _require_regular_file(run_dir, "output/tcnn-commit.txt").read_text().strip() != PINNED_TCNN_COMMIT:
        raise ValueError("tiny-cuda-nn source commit mismatch")
    manifest = _parse_key_value_manifest(_require_regular_file(run_dir, "output/insula-manifest.txt"))
    if manifest != PINNED_INSULA_MANIFEST:
        raise ValueError("radiance-field Insula manifest mismatch")
    locks = load_json(ROOT / "insulas/locks.json")["insulas"]["radiance-field"]
    requirements_lock = _require_regular_file(run_dir, "output/requirements.lock.txt")
    resolved_requirements = _require_regular_file(
        run_dir, "output/resolved-requirements.txt"
    )
    if (
        sha256_file(ROOT / "insulas/radiance-field/requirements.lock.txt")
        != REQUIREMENTS_LOCK_SHA256
        or sha256_file(requirements_lock) != REQUIREMENTS_LOCK_SHA256
        or sha256_file(
            ROOT / "insulas/radiance-field/resolved-requirements.lock.txt"
        )
        != locks.get("resolved_requirements_sha256")
        or sha256_file(resolved_requirements)
        != locks.get("resolved_requirements_sha256")
    ):
        raise ValueError("Nerfacto dependency lock or resolved manifest mismatch")
    versions = load_json(_require_regular_file(run_dir, "output/runtime-versions.json"))
    if (
        versions.get("nerfstudio_commit") != PINNED_NERFSTUDIO_COMMIT
        or versions.get("tiny_cuda_nn_commit") != PINNED_TCNN_COMMIT
        or versions.get("requirements_lock_sha256") != REQUIREMENTS_LOCK_SHA256
        or versions.get("resolved_requirements_sha256")
        != locks.get("resolved_requirements_sha256")
        or versions.get("torch") != "2.7.1+cu128"
        or versions.get("torchvision") != "0.22.1+cu128"
        or versions.get("pillow") != "11.1.0"
        or versions.get("python") != "3.12.3"
        or versions.get("numpy") != "2.5.2"
        or versions.get("cuda_runtime") != "12.8"
        or "release 12.8" not in str(versions.get("cuda_compiler", ""))
        or versions.get("compute_capability") != [10, 0]
        or versions.get("tcnn_cuda_architectures") != "100"
        or not versions.get("device")
    ):
        raise ValueError("Nerfacto runtime identity mismatch")
    gates = load_json(_require_regular_file(run_dir, "output/environment-gates.json"))
    required_gates = {
        "compute_capability_10_0",
        "tcnn_forward_backward",
        "nerfacto_forward_backward",
        "density_query_32",
    }
    if gates.keys() != required_gates or not all(gates.values()):
        raise ValueError("Nerfacto environment gate failed")
    summary = load_json(_require_regular_file(run_dir, "output/training-summary.json"))
    expected = PROFILE_CONFIG[profile]
    if (
        summary.get("method") != "nerfacto"
        or summary.get("iterations") != expected["iterations"]
        or summary.get("rays_per_batch") != expected["rays_per_batch"]
        or summary.get("density_resolution") != expected["density_resolution"]
        or summary.get("camera_optimizer") != "off"
        or summary.get("appearance_embedding") is not False
        or summary.get("scene_contraction") is not False
        or summary.get("near_plane_m") != 0.1
        or summary.get("far_plane_m") != 6.0
        or summary.get("proposal_initial_sampler") != "uniform"
        or summary.get("context_split_mode") != "all-context-frames-train-and-eval"
        or summary.get("dataloader_num_workers") != 1
        or summary.get("tf32") is not False
        or summary.get("seed") != 260925
        or summary.get("trained_view_sweep")
        != {"context_views": [3, 5, 9], "iterations": 1000, "rays_per_batch": 1024}
        or not isinstance(summary.get("training_seconds"), (int, float))
        or summary["training_seconds"] <= 0
        or not math.isclose(summary.get("training_steps_per_second", -1.0), expected["iterations"] / summary["training_seconds"], rel_tol=1e-9)
        or not isinstance(summary.get("density_query_seconds"), (int, float))
        or summary["density_query_seconds"] < 0
    ):
        raise ValueError("Nerfacto training identity mismatch")
    canonical = summary.get("canonical_nerf_example")
    if profile == "smoke":
        if canonical is not None:
            raise ValueError("smoke Nerfacto run unexpectedly executed the canonical dataset")
    elif (
        not isinstance(canonical, dict)
        or canonical.keys()
        != {
            "asset_id",
            "dataset",
            "iterations",
            "rays_per_batch",
            "training_views",
            "target_views",
            "image_size",
            "training_seconds",
        }
        or canonical.get("asset_id") != NERF_SYNTHETIC_ASSET_ID
        or canonical.get("dataset") != CANONICAL_NERF_EXAMPLE["dataset"]
        or canonical.get("iterations") != CANONICAL_NERF_EXAMPLE["iterations"]
        or canonical.get("rays_per_batch") != CANONICAL_NERF_EXAMPLE["rays_per_batch"]
        or canonical.get("training_views")
        != len(CANONICAL_NERF_EXAMPLE["training_frame_ids"])
        or canonical.get("target_views")
        != len(CANONICAL_NERF_EXAMPLE["target_frame_ids"])
        or canonical.get("image_size") != CANONICAL_NERF_EXAMPLE["image_size"]
        or not isinstance(canonical.get("training_seconds"), (int, float))
        or canonical["training_seconds"] <= 0
    ):
        raise ValueError("canonical NeRF example training identity mismatch")
    _require_regular_file(run_dir, "output/nerfstudio/checkpoint.ckpt")
    _require_regular_file(run_dir, "output/nerfstudio/config.yml")
    _require_regular_file(run_dir, "output/failure_sweep.csv")
    return summary


def _acceptance_failures(metrics: dict[str, Any], acceptance: dict[str, Any]) -> list[str]:
    values = {**metrics["rendering"], **metrics["geometry"], **metrics["field"]}
    if "canonical_nerf_example" in metrics:
        values.update(
            {
                "canonical_target_psnr_db": metrics["canonical_nerf_example"][
                    "target_psnr_db"
                ],
                "canonical_target_ssim": metrics["canonical_nerf_example"][
                    "target_ssim"
                ],
            }
        )
    failures = []
    for key, threshold in acceptance.items():
        if key.endswith("_min"):
            name = key.removesuffix("_min")
            if values[name] < threshold:
                failures.append(f"{name}={values[name]} < {threshold}")
        elif key.endswith("_max"):
            name = key.removesuffix("_max")
            if values[name] > threshold:
                failures.append(f"{name}={values[name]} > {threshold}")
        else:
            raise ValueError(f"unsupported Nerfacto acceptance key: {key}")
    return failures


def _write_visualizations(run_dir: Path, metrics: dict[str, Any]) -> None:
    artifacts = run_dir / "artifacts"
    artifacts.mkdir()
    (artifacts / "metric-summary.svg").write_text(
        "<svg xmlns='http://www.w3.org/2000/svg' width='700' height='140'>"
        "<rect width='700' height='140' fill='#101820'/>"
        f"<text x='20' y='48' fill='#f2f2f2'>target PSNR: {metrics['rendering']['target_psnr_db']:.3f} dB</text>"
        f"<text x='20' y='82' fill='#f2f2f2'>expected-depth RMSE: {metrics['geometry']['expected_depth_rmse_m']:.4f} m</text>"
        "<text x='20' y='116' fill='#f2f2f2'>rendering and geometry remain separate metric families</text>"
        "</svg>\n",
        encoding="utf-8",
    )


def _report(profile: str, metrics: dict[str, Any]) -> str:
    canonical = ""
    if "canonical_nerf_example" in metrics:
        measured = metrics["canonical_nerf_example"]
        canonical = f"""
## Locked canonical NeRF example

The full profile consumed the tree-verified Lego sample from the canonical NeRF example archive, optimized from {measured['training_views']} fixed training views, and scored {measured['target_views']} held-out views. The canonical NeRF example measured {measured['target_psnr_db']:.3f} dB PSNR and {measured['target_ssim']:.4f} SSIM. These rendering measurements are reported separately from the analytic shared-scene geometry metrics.
"""
    return f"""# Nerfacto maintained reference ({profile})

## Rendering

Held-out target PSNR: {metrics['rendering']['target_psnr_db']:.3f} dB; host-recomputed SSIM: {metrics['rendering']['target_ssim']:.4f}; pinned-container LPIPS: {metrics['rendering']['target_lpips']:.4f}. Context fit is reported separately at {metrics['rendering']['context_fit_psnr_db']:.3f} dB PSNR.

## Geometry

Accumulation-qualified common-visible expected-depth RMSE: {metrics['geometry']['expected_depth_rmse_m']:.5f} m; F-score at 10 cm: {metrics['geometry']['point_fscore_10cm']:.4f}.
{canonical}

## Interpretation

Nerfacto performs one seeded per-scene density/radiance optimization; CUDA execution can vary numerically. Density has no canonical surface level, and neither target-view stochasticity nor a hidden-scene posterior is sampled. The trained 3/5/9-view sweep is failure evidence. Module 09's retained mesh metrics use a different evaluator and are not copied into this result or collapsed into a composite rank.
"""


def _entrypoint_command(profile: str) -> list[str]:
    config = PROFILE_CONFIG[profile]
    command = [
        "/usr/bin/time",
        "-v",
        "-o",
        "/output/resource-usage.txt",
        "python",
        "/usr/local/bin/run-nerfacto.py",
        "--input",
        "/input",
        "--output",
        "/output",
        "--iterations",
        str(config["iterations"]),
        "--rays-per-batch",
        str(config["rays_per_batch"]),
        "--density-resolution",
        str(config["density_resolution"]),
    ]
    if profile == "full":
        command.extend(
            [
                "--canonical-input",
                "/canonical",
                "--canonical-archive-sha256",
                NERF_SYNTHETIC_SHA256,
                "--canonical-tree-sha256",
                NERF_SYNTHETIC_TREE_SHA256,
            ]
        )
    return command


def _container_command(
    engine: str,
    image_id: str,
    staging: Path,
    cuda_cache: Path,
    lpips_checkpoint: Path,
    profile: str,
    canonical_input: Path | None,
    gpu_device: str,
) -> list[str]:
    command = [
        engine,
        "run",
        "--rm",
        "--network",
        "none",
        "--pull=never",
        "--gpus",
        f"device={gpu_device}",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "-e",
        "USER=surflo",
        "--cidfile",
        str(staging / "container.cid"),
        "-e",
        "CUDA_CACHE_PATH=/cuda-cache",
        "-e",
        "MPLCONFIGDIR=/cuda-cache/matplotlib",
        "-e",
        "TORCH_HOME=/model",
        "-v",
        f"{cuda_cache}:/cuda-cache",
        "-v",
        f"{(staging / 'input').resolve()}:/input:ro",
        "-v",
        f"{(staging / 'output').resolve()}:/output",
        "-v",
        f"{lpips_checkpoint}:/model/hub/checkpoints/{LPIPS_CHECKPOINT_FILENAME}:ro",
        image_id,
        *_entrypoint_command(profile),
    ]
    if canonical_input is not None:
        image_index = command.index(image_id)
        command[image_index:image_index] = [
            "-v",
            f"{canonical_input.resolve(strict=True)}:/canonical:ro",
        ]
    return command


def _expected_config(
    run_dir: Path,
    result: dict[str, Any],
    profile: str,
    acceptance: dict[str, Any],
) -> dict[str, Any]:
    tool = result["tool"]
    return {
        "adapter": ADAPTER,
        "profile": profile,
        "run_id": result["provenance"]["config"]["run_id"],
        "module_ids": ["10"],
        "image": IMAGE,
        "image_id": tool["container_image_id"],
        "scene_contract_sha256": sha256_file(ROOT / "shared-scene.json"),
        "input_manifest_sha256": sha256_file(run_dir / "input/manifest.json"),
        "source_commit": PINNED_NERFSTUDIO_COMMIT,
        "dependency_commit": PINNED_TCNN_COMMIT,
        "requirements_lock_sha256": REQUIREMENTS_LOCK_SHA256,
        "resolved_requirements_sha256": load_json(ROOT / "insulas/locks.json")["insulas"]["radiance-field"]["resolved_requirements_sha256"],
        **PROFILE_CONFIG[profile],
        "seed": 260925,
        "camera_optimizer": "off",
        "appearance_embedding": False,
        "scene_contraction": False,
        "near_plane_m": 0.1,
        "far_plane_m": 6.0,
        "proposal_initial_sampler": "uniform",
        "context_split_mode": "all-context-frames-train-and-eval",
        "dataloader_num_workers": 1,
        "tf32": False,
        "trained_view_sweep": {
            "context_views": [3, 5, 9],
            "iterations": 1000,
            "rays_per_batch": 1024,
        },
        "canonical_nerf_example": None
        if profile == "smoke"
        else {
            **CANONICAL_NERF_EXAMPLE,
            "archive_sha256": NERF_SYNTHETIC_SHA256,
            "extraction_tree_sha256": NERF_SYNTHETIC_TREE_SHA256,
            "asset_lock": _nerf_synthetic_record(),
        },
        "container_user_environment": {"USER": "surflo"},
        "support": SUPPORT_CONTRACT,
        "cuda_cache": CUDA_CACHE_POLICY,
        "lpips_backbone": _lpips_checkpoint_record(),
        "adapter_execution_contract_sha256": _adapter_execution_contract_sha256(),
        "entrypoint_command": _entrypoint_command(profile),
        "evaluation_software": {"python": platform.python_version(), "numpy": np.__version__},
        "acceptance": acceptance,
    }


def validate_nerfacto_reference_result(run_dir: Path) -> dict[str, Any]:
    result = load_json(_require_regular_file(run_dir, "result.json"))
    validate_json_schema_instance(
        result, load_json(ROOT / "reference-result.schema.json"), "Nerfacto reference result"
    )
    if (
        result.get("adapter") != ADAPTER
        or result.get("module_ids") != ["10"]
        or result.get("status") != "complete"
        or result.get("network_mode") != "offline"
        or result.get("support") != SUPPORT_CONTRACT
    ):
        raise ValueError("Nerfacto result identity mismatch")
    profile = result.get("profile")
    if profile not in PROFILE_CONFIG:
        raise ValueError("Nerfacto result profile mismatch")
    _validate_runtime_identity(run_dir, profile)
    _validated_resource_summary(
        run_dir,
        result,
        label="Nerfacto",
        expected_keys={
            "runtime_seconds",
            "peak_cpu_memory_bytes",
            "peak_gpu_compute_memory_bytes",
            "gpu_memory_scope",
            "gpu_measurement_status",
            "gpu_selection",
            "gpu_host_index",
            "gpu_hardware",
            "host",
            "density_query_seconds",
            "training_seconds",
            "training_steps_per_second",
            "canonical_training_seconds",
        },
        positive_keys=(
            "runtime_seconds",
            "peak_cpu_memory_bytes",
            "density_query_seconds",
            "training_seconds",
            "training_steps_per_second",
        ),
        nonnegative_keys=("canonical_training_seconds",),
    )
    metrics = _evaluate_outputs(run_dir, profile)
    if not _values_match(result.get("metrics"), metrics):
        raise ValueError("Nerfacto persisted metric recomputation mismatch")
    acceptance = _adapter_record().get("acceptance", {}).get(profile, {})
    if result.get("acceptance") != acceptance:
        raise ValueError("Nerfacto acceptance binding mismatch")
    failures = _acceptance_failures(metrics, acceptance)
    if failures:
        raise ValueError(f"Nerfacto output is below the locked acceptance threshold: {failures}")
    tool = result.get("tool", {})
    if (
        tool.get("source_commit") != PINNED_NERFSTUDIO_COMMIT
        or tool.get("dependency_commit") != PINNED_TCNN_COMMIT
        or tool.get("container_image") != IMAGE
        or IMAGE_ID_PATTERN.fullmatch(str(tool.get("container_image_id", ""))) is None
    ):
        raise ValueError("Nerfacto tool identity mismatch")
    config = result["provenance"]["config"]
    if config != _expected_config(run_dir, result, profile, acceptance):
        raise ValueError("Nerfacto config identity binding mismatch")
    if hashlib.sha256(canonical_json(config)).hexdigest() != result["provenance"]["config_sha256"]:
        raise ValueError("Nerfacto config hash mismatch")
    implementation = {name: sha256_file(ROOT / name) for name in REFERENCE_IMPLEMENTATION}
    if result["provenance"].get("implementation_sha256") != implementation:
        raise ValueError("Nerfacto implementation identity mismatch")
    if result["provenance"].get("artifacts_sha256") != _hash_tree(run_dir):
        raise ValueError("Nerfacto artifact hash mismatch")
    return result


def run_nerfacto_reference(cache_root: Path, profile: str, run_id: str) -> Path:
    validate_run_id(run_id)
    if profile not in PROFILE_CONFIG:
        raise ValueError(f"unknown profile: {profile}")
    engine = os.environ.get("SURFLO_PATHWAY_CONTAINER_ENGINE", "docker")
    image_id = _inspect_image(engine, IMAGE)
    _verify_container_entrypoint(engine, image_id)
    gpu_hardware = _gpu_hardware(engine)
    if Path(engine).name == "docker" and not gpu_hardware:
        raise ValueError("unable to inventory GPU hardware for the real Nerfacto reference")
    gpu_device = selected_gpu_device(require_health=Path(engine).name == "docker")
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_root = cache_root.resolve(strict=True)
    lpips_record = _lpips_checkpoint_record()
    lpips_checkpoint = _lpips_checkpoint_path(cache_root, lpips_record)
    canonical_input: Path | None = None
    if profile == "full":
        canonical_input, _ = _locked_nerf_example(cache_root)
    runs_root = _secure_directory(cache_root, "reference-runs")
    staging_root = _secure_directory(cache_root, "reference-staging")
    cuda_cache = _secure_directory(cache_root, "cuda-cache")
    final_parent = runs_root / run_id
    final = final_parent / ADAPTER
    if os.path.lexists(final_parent):
        raise FileExistsError(f"reference run already exists: {final}")
    promotion = staging_root / f"{run_id}.{ADAPTER}.{uuid.uuid4().hex}"
    staging = promotion / ADAPTER
    promotion.mkdir()
    staging.mkdir()
    started = time.perf_counter()
    try:
        generate_radiance_field_scene(
            staging / "input", load_json(ROOT / "shared-scene.json"), profile
        )
        (staging / "output").mkdir()
        command = _container_command(
            engine,
            image_id,
            staging,
            cuda_cache,
            lpips_checkpoint,
            profile,
            canonical_input,
            gpu_device,
        )
        completed, peak_gpu = _run_monitored(command, staging / "container.cid")
        (staging / "adapter.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            raise ValueError(f"Nerfacto adapter failed ({completed.returncode}): {completed.stderr.strip()}")
        if Path(engine).name == "docker" and peak_gpu <= 0:
            raise ValueError("unable to measure compute memory for Nerfacto GPU optimization")
        summary = _validate_runtime_identity(staging, profile)
        metrics = _evaluate_outputs(staging, profile)
        _write_visualizations(staging, metrics)
        acceptance = _adapter_record().get("acceptance", {}).get(profile, {})
        failures = _acceptance_failures(metrics, acceptance)
        if failures:
            raise ValueError(f"Nerfacto output is below the locked acceptance threshold: {failures}")
        (staging / "report.md").write_text(_report(profile, metrics), encoding="utf-8")
        resources = {
            "runtime_seconds": time.perf_counter() - started,
            "peak_cpu_memory_bytes": _peak_cpu_memory_bytes(staging / "output/resource-usage.txt"),
            "peak_gpu_compute_memory_bytes": peak_gpu,
            "gpu_memory_scope": "container-cgroup-compute-process-sum",
            "gpu_measurement_status": "measured" if peak_gpu > 0 else "unavailable",
            "gpu_selection": "one healthy host GPU mapped to CUDA device 0",
            "gpu_host_index": int(gpu_device),
            "gpu_hardware": gpu_hardware,
            "host": platform.platform(),
            "density_query_seconds": summary["density_query_seconds"],
            "training_seconds": summary["training_seconds"],
            "training_steps_per_second": summary["training_steps_per_second"],
            "canonical_training_seconds": 0.0
            if summary["canonical_nerf_example"] is None
            else summary["canonical_nerf_example"]["training_seconds"],
        }
        write_json(staging / "output/resource-summary.json", resources)
        provisional_result = {
            "tool": {"container_image_id": image_id},
            "provenance": {"config": {"run_id": run_id}},
        }
        config = _expected_config(staging, provisional_result, profile, acceptance)
        result = {
            "schema_version": 1,
            "adapter": ADAPTER,
            "module_ids": ["10"],
            "profile": profile,
            "status": "complete",
            "network_mode": "offline",
            "metrics": metrics,
            "support": SUPPORT_CONTRACT,
            "acceptance": acceptance,
            "tool": {
                "name": "Nerfstudio Nerfacto",
                "version": "nerfacto",
                "package_version": f"source@{PINNED_NERFSTUDIO_COMMIT}",
                "source_commit": PINNED_NERFSTUDIO_COMMIT,
                "dependency_commit": PINNED_TCNN_COMMIT,
                "container_image": IMAGE,
                "container_image_id": image_id,
            },
            "resources": resources,
            "provenance": {
                "config": config,
                "config_sha256": hashlib.sha256(canonical_json(config)).hexdigest(),
                "implementation_sha256": {
                    name: sha256_file(ROOT / name) for name in REFERENCE_IMPLEMENTATION
                },
                "artifacts_sha256": _hash_tree(staging),
            },
        }
        ensure_finite(result, "Nerfacto reference result")
        write_json(staging / "result.json", result)
        validate_nerfacto_reference_result(staging)
        os.replace(promotion, final_parent)
        return final
    except BaseException:
        shutil.rmtree(promotion, ignore_errors=True)
        raise
