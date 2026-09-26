"""Offline Nerfstudio Nerfacto maintained-reference execution for module 10."""

from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
import platform
import shutil
import stat
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
    sha256_file,
    validate_json_schema_instance,
    validate_run_id,
    write_json,
)
from mvs_reference_runner import _gpu_hardware, _peak_cpu_memory_bytes, _run_monitored
from reference_runner import (
    _hash_tree,
    _inspect_image,
    _parse_key_value_manifest,
    _require_regular_file,
    _secure_directory,
)
from reference_scene import generate_radiance_field_scene


ADAPTER = "nerfacto"
IMAGE = "surflo-pathway-radiance-field:1"
PINNED_NERFSTUDIO_COMMIT = "50e0e3c70c775e89333256213363badbf074f29d"
PINNED_TCNN_COMMIT = "0109538c37ac0bf613f2bac8de6cda48352feca7"
LPIPS_CHECKPOINT_ID = "nerfstudio-lpips-alexnet"
LPIPS_CHECKPOINT_SHA256 = "7be5be791159472b1fbf3c69796f7cb30dca7ad8466c2df70058c37116cdee02"
LPIPS_CHECKPOINT_BYTES = 244408911
LPIPS_CHECKPOINT_FILENAME = "alexnet-owt-7be5be79.pth"
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
REFERENCE_IMPLEMENTATION = (
    "pipeline/cli.py",
    "pipeline/contracts.py",
    "pipeline/reference_runner.py",
    "pipeline/mvs_reference_runner.py",
    "pipeline/nerfacto_reference_runner.py",
    "pipeline/reference_scene.py",
    "insulas/build.sh",
    "insulas/radiance-field/Dockerfile",
    "insulas/radiance-field/run-nerfacto.py",
    "insulas/locks.json",
    "assets.lock.json",
    "reference-result.schema.json",
    "reference-adapters.json",
    "shared-scene.json",
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


def _surface_comparator_record() -> dict[str, Any]:
    return next(
        item
        for item in load_json(ROOT / "reference-adapters.json")["adapters"]
        if item["id"] == "nerfstudio-neus-facto-reference"
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
        != {"nerfstudio-neus-facto-reference", "nerfstudio-nerfacto-reference"}
        or not str(record.get("source", "")).endswith(LPIPS_CHECKPOINT_FILENAME)
    ):
        raise ValueError("Nerfacto LPIPS checkpoint lock mismatch")
    return record


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


def _evaluate_outputs(run_dir: Path, profile: str) -> dict[str, Any]:
    manifest = _validate_input_manifest(run_dir / "input", profile)
    official = load_json(_require_regular_file(run_dir, "output/target-image-metrics.json"))
    if [item.get("id") for item in official] != [frame["id"] for frame in manifest["target_frames"]]:
        raise ValueError("Nerfacto target metric inventory mismatch")

    psnrs: list[float] = []
    foreground_psnrs: list[float] = []
    ssims: list[float] = []
    lpips_values: list[float] = []
    median_residuals: list[np.ndarray] = []
    expected_residuals: list[np.ndarray] = []
    qualified_truth_depths: list[np.ndarray] = []
    predicted_points: list[np.ndarray] = []
    truth_points: list[np.ndarray] = []
    supported_total = 0
    supported_qualified = 0
    unsupported_total = 0
    unsupported_qualified = 0
    intrinsics = manifest["intrinsics"]
    for frame, image_metrics in zip(manifest["target_frames"], official):
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
        mse = float(np.mean((predicted_rgb.astype(np.float64) - truth_rgb) ** 2))
        psnr = float(-10.0 * math.log10(mse))
        if not math.isclose(psnr, float(image_metrics["psnr_db"]), rel_tol=2e-5, abs_tol=2e-4):
            raise ValueError("Nerfacto official and recomputed PSNR mismatch")
        foreground = truth_depth > 0.0
        foreground_mse = float(np.mean((predicted_rgb[foreground].astype(np.float64) - truth_rgb[foreground]) ** 2))
        psnrs.append(psnr)
        foreground_psnrs.append(float(-10.0 * math.log10(foreground_mse)))
        ssims.append(float(image_metrics["ssim"]))
        lpips_values.append(float(image_metrics["lpips"]))

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
    field = {
        "density_min": float(np.min(density)),
        "density_median": float(np.median(density)),
        "density_p95": float(np.quantile(density, 0.95)),
        "density_max": float(np.max(density)),
        "occupied_fraction_ge_0_1": float(np.mean(density >= 0.1)),
        "occupied_fraction_ge_1": float(np.mean(density >= 1.0)),
        "occupied_fraction_ge_10": float(np.mean(density >= 10.0)),
        "occupied_fraction_ge_100": float(np.mean(density >= 100.0)),
    }
    comparator = _surface_comparator_record()[f"last_verified_{profile}"]
    comparison = {
        "metric_families_combined": False,
        "identical_scene_contract_sha256": sha256_file(ROOT / "shared-scene.json"),
        "surface_model_target_psnr_db": float(comparator["target_psnr_db"]),
        "surface_model_common_visible_accuracy_rmse_m": float(
            comparator["common_visible_accuracy_rmse_m"]
        ),
    }
    metrics = {
        "rendering": {
            "target_psnr_db": float(np.mean(psnrs)),
            "target_foreground_psnr_db": float(np.mean(foreground_psnrs)),
            "target_ssim": float(np.mean(ssims)),
            "target_lpips": float(np.mean(lpips_values)),
            "target_views": len(psnrs),
        },
        "geometry": geometry,
        "field": field,
        "comparison": comparison,
        "unsupported": {
            "truth_rays": unsupported_total,
            "accumulation_qualified_rays": unsupported_qualified,
            "accumulation_coverage": 0.0 if unsupported_total == 0 else unsupported_qualified / unsupported_total,
            "completion_claim": "none",
        },
    }
    ensure_finite(
        {key: value for key, value in metrics.items() if key != "comparison"},
        "Nerfacto scored metrics",
    )
    return metrics


def _validate_runtime_identity(run_dir: Path, profile: str) -> dict[str, Any]:
    if _require_regular_file(run_dir, "output/source-commit.txt").read_text().strip() != PINNED_NERFSTUDIO_COMMIT:
        raise ValueError("Nerfstudio source commit mismatch")
    if _require_regular_file(run_dir, "output/tcnn-commit.txt").read_text().strip() != PINNED_TCNN_COMMIT:
        raise ValueError("tiny-cuda-nn source commit mismatch")
    manifest = _parse_key_value_manifest(_require_regular_file(run_dir, "output/insula-manifest.txt"))
    if manifest != PINNED_INSULA_MANIFEST:
        raise ValueError("radiance-field Insula manifest mismatch")
    versions = load_json(_require_regular_file(run_dir, "output/runtime-versions.json"))
    if (
        versions.get("nerfstudio_commit") != PINNED_NERFSTUDIO_COMMIT
        or versions.get("tiny_cuda_nn_commit") != PINNED_TCNN_COMMIT
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
        or summary.get("tf32") is not False
        or summary.get("seed") != 260925
        or not isinstance(summary.get("training_seconds"), (int, float))
        or summary["training_seconds"] <= 0
        or not math.isclose(summary.get("training_steps_per_second", -1.0), expected["iterations"] / summary["training_seconds"], rel_tol=1e-9)
        or not isinstance(summary.get("density_query_seconds"), (int, float))
        or summary["density_query_seconds"] < 0
    ):
        raise ValueError("Nerfacto training identity mismatch")
    _require_regular_file(run_dir, "output/nerfstudio/checkpoint.ckpt")
    _require_regular_file(run_dir, "output/nerfstudio/config.yml")
    _require_regular_file(run_dir, "output/failure_sweep.csv")
    return summary


def _acceptance_failures(metrics: dict[str, Any], acceptance: dict[str, Any]) -> list[str]:
    values = {**metrics["rendering"], **metrics["geometry"], **metrics["field"]}
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
    return f"""# Nerfacto maintained reference ({profile})

## Rendering

Held-out target PSNR: {metrics['rendering']['target_psnr_db']:.3f} dB; SSIM: {metrics['rendering']['target_ssim']:.4f}; LPIPS: {metrics['rendering']['target_lpips']:.4f}.

## Geometry

Accumulation-qualified common-visible expected-depth RMSE: {metrics['geometry']['expected_depth_rmse_m']:.5f} m; F-score at 10 cm: {metrics['geometry']['point_fscore_10cm']:.4f}.

## Interpretation

Nerfacto optimizes one deterministic per-scene density/radiance field. Density has no canonical surface level, and neither target-view stochasticity nor a hidden-scene posterior is sampled. The retained NeuS-Facto values are shown only as a separate surface-oriented comparator; no composite rank is formed.
"""


def _entrypoint_command(profile: str) -> list[str]:
    config = PROFILE_CONFIG[profile]
    return [
        "/usr/bin/time",
        "-v",
        "-o",
        "/work/output/resource-usage.txt",
        "python",
        "/usr/local/bin/run-nerfacto.py",
        "--input",
        "/work/input",
        "--output",
        "/work/output",
        "--iterations",
        str(config["iterations"]),
        "--rays-per-batch",
        str(config["rays_per_batch"]),
        "--density-resolution",
        str(config["density_resolution"]),
    ]


def _container_command(
    engine: str,
    image_id: str,
    staging: Path,
    cuda_cache: Path,
    lpips_checkpoint: Path,
    profile: str,
) -> list[str]:
    return [
        engine,
        "run",
        "--rm",
        "--network",
        "none",
        "--pull=never",
        "--gpus",
        "all",
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
        f"{staging.resolve()}:/work",
        "-v",
        f"{lpips_checkpoint}:/model/hub/checkpoints/{LPIPS_CHECKPOINT_FILENAME}:ro",
        image_id,
        *_entrypoint_command(profile),
    ]


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
        **PROFILE_CONFIG[profile],
        "seed": 260925,
        "camera_optimizer": "off",
        "appearance_embedding": False,
        "scene_contraction": False,
        "near_plane_m": 0.1,
        "far_plane_m": 6.0,
        "proposal_initial_sampler": "uniform",
        "tf32": False,
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
    gpu_hardware = _gpu_hardware(engine)
    if Path(engine).name == "docker" and not gpu_hardware:
        raise ValueError("unable to inventory GPU hardware for the real Nerfacto reference")
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_root = cache_root.resolve(strict=True)
    lpips_record = _lpips_checkpoint_record()
    lpips_checkpoint = _lpips_checkpoint_path(cache_root, lpips_record)
    runs_root = _secure_directory(cache_root, "reference-runs")
    staging_root = _secure_directory(cache_root, "reference-staging")
    cuda_cache = _secure_directory(cache_root, "cuda-cache")
    final_parent = runs_root / run_id
    final = final_parent / ADAPTER
    if os.path.lexists(final_parent):
        raise FileExistsError(f"reference run already exists: {final}")
    staging = staging_root / f"{run_id}.{ADAPTER}.{uuid.uuid4().hex}"
    staging.mkdir()
    started = time.perf_counter()
    try:
        generate_radiance_field_scene(
            staging / "input", load_json(ROOT / "shared-scene.json"), profile
        )
        (staging / "output").mkdir()
        command = _container_command(
            engine, image_id, staging, cuda_cache, lpips_checkpoint, profile
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
            "gpu_selection": "all-visible; pinned entrypoint selects CUDA device 0",
            "gpu_hardware": gpu_hardware,
            "host": platform.platform(),
            "density_query_seconds": summary["density_query_seconds"],
            "training_seconds": summary["training_seconds"],
            "training_steps_per_second": summary["training_steps_per_second"],
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
        final_parent.mkdir()
        os.replace(staging, final)
        return final
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
