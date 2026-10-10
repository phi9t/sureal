"""Offline Depth Anything V2 maintained-reference execution for module 08."""

from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import tempfile
import time
from typing import Any
import uuid

import numpy as np

from pipeline.contracts import (
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
from pipeline.mvs_reference_runner import _gpu_hardware, _peak_cpu_memory_bytes, _run_monitored
from pipeline.reference_runner import (
    _hash_tree,
    _inspect_image,
    _parse_key_value_manifest,
    _require_regular_file,
    _secure_directory,
)
from pipeline.reference_scene import generate_learned_depth_scene


ADAPTER = "depth-anything-v2"
IMAGE = "surflo-pathway-neural-rendering:1"
PINNED_SOURCE_COMMIT = "a561b849ebae10a6f5ef49e26c83cbbcd36c71bf"
CHECKPOINT_ID = "depth-anything-v2-metric-hypersim-small"
CHECKPOINT_REVISION = "3bc65d4e14a6786a61acec16453c50e12bf5f338"
CHECKPOINT_SHA256 = "b782898d8a3e8be1f639de33837ed85e9b4b73e40f8f5e5cd99067588d722545"
CHECKPOINT_BYTES = 99_222_290
INPUT_SIZE = 518
MAX_DEPTH_M = 20.0
TOOL_NAME = "Depth Anything V2 Metric Hypersim Small"
TOOL_VERSION = "metric-hypersim-small"
TOOL_PACKAGE_VERSION = f"source@{PINNED_SOURCE_COMMIT}"
EVALUATION_SOFTWARE = {"numpy": np.__version__}
CUDA_CACHE_POLICY = "persistent-cache-root-mount"
IMAGE_ID_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
PINNED_INSULA_MANIFEST = {
    "schema_version": "1",
    "kind": "neural-rendering",
    "cuda": "13.2.1",
    "uv": "0.11.13",
    "torch": "2.13.0+cu132",
    "torchvision": "0.28.0+cu132",
    "depth_anything_v2_commit": PINNED_SOURCE_COMMIT,
    "network_policy": "build-and-fetch-only",
}
SUPPORT_CONTRACT = {
    "prediction_domain": "input-visible-pixels",
    "model_output": "deterministic-per-view-camera-axis-depth",
    "hidden_scene_prediction_count": 0,
    "complete_scene_samples": 0,
    "completion_claim": "none",
    "posterior_sampling_claim": "none",
}
REFERENCE_IMPLEMENTATION = (
    "pipeline/cli.py",
    "pipeline/contracts.py",
    "pipeline/reference_runner.py",
    "pipeline/mvs_reference_runner.py",
    "pipeline/depth_reference_runner.py",
    "pipeline/reference_scene.py",
    "insulas/build.sh",
    "insulas/neural-rendering/Dockerfile",
    "insulas/neural-rendering/run-depth-anything-v2.py",
    "insulas/locks.json",
    "assets.lock.json",
    "reference-result.schema.json",
    "shared-scene.json",
    "reference-adapters.json",
)


def _affine_metrics(predicted: np.ndarray, target: np.ndarray) -> dict[str, Any]:
    predicted = np.asarray(predicted, dtype=np.float64).reshape(-1)
    target = np.asarray(target, dtype=np.float64).reshape(-1)
    if predicted.shape != target.shape or predicted.size < 2:
        raise ValueError("affine depth alignment requires matching non-trivial samples")
    if not np.isfinite(predicted).all() or not np.isfinite(target).all():
        raise ValueError("affine depth alignment requires finite samples")
    centered_prediction = predicted - predicted.mean()
    denominator = float(np.dot(centered_prediction, centered_prediction))
    tolerance = float(np.finfo(np.float64).eps * max(1.0, np.dot(predicted, predicted)))
    if denominator <= tolerance:
        unconstrained_scale = 0.0
    else:
        unconstrained_scale = float(
            np.dot(centered_prediction, target - target.mean()) / denominator
        )
    if not math.isfinite(unconstrained_scale):
        raise ValueError("affine depth alignment is non-finite")
    scale = max(0.0, unconstrained_scale)
    shift = float(target.mean() - scale * predicted.mean())
    aligned = scale * predicted + shift
    return {
        "affine_aligned_rmse_m": float(np.sqrt(np.mean((aligned - target) ** 2))),
        "affine_aligned_abs_rel": float(np.mean(np.abs(aligned - target) / target)),
        "affine_scale": scale,
        "affine_shift_m": shift,
        "alignment_scale_at_boundary": scale == 0.0,
    }


def _depth_metrics(prediction: np.ndarray, truth: np.ndarray) -> dict[str, Any]:
    prediction = np.asarray(prediction)
    truth = np.asarray(truth)
    if prediction.ndim != 2 or prediction.shape != truth.shape:
        raise ValueError("depth prediction and truth must have identical HxW shapes")
    valid = np.isfinite(prediction) & (prediction > 0.0) & np.isfinite(truth) & (truth > 0.0)
    valid_pixels = int(np.count_nonzero(valid))
    if valid_pixels < 2:
        raise ValueError("depth evaluation requires at least two valid positive pixels")
    predicted = prediction[valid].astype(np.float64)
    target = truth[valid].astype(np.float64)
    residual = predicted - target
    ratios = np.maximum(predicted / target, target / predicted)
    metrics = {
        "valid_pixels": valid_pixels,
        "valid_pixel_fraction": float(valid_pixels / truth.size),
        "raw_rmse_m": float(np.sqrt(np.mean(residual * residual))),
        "raw_abs_rel": float(np.mean(np.abs(residual) / target)),
        "raw_delta1": float(np.mean(ratios < 1.25)),
        **_affine_metrics(predicted, target),
    }
    if not all(math.isfinite(value) for value in metrics.values()):
        raise ValueError("depth metrics must be finite")
    return metrics


def _depth_colors(values: np.ndarray, maximum: float) -> np.ndarray:
    normalized = np.clip(np.asarray(values, dtype=np.float64) / maximum, 0.0, 1.0)
    red = np.clip(1.5 - np.abs(4.0 * normalized - 3.0), 0.0, 1.0)
    green = np.clip(1.5 - np.abs(4.0 * normalized - 2.0), 0.0, 1.0)
    blue = np.clip(1.5 - np.abs(4.0 * normalized - 1.0), 0.0, 1.0)
    return np.rint(np.stack((red, green, blue), axis=-1) * 255.0).astype(np.uint8)


def _comparison_ppm(truth: np.ndarray, prediction: np.ndarray) -> bytes:
    if truth.shape != prediction.shape or truth.ndim != 2:
        raise ValueError("comparison visualization requires matching depth maps")
    panels = np.concatenate(
        (
            _depth_colors(truth, MAX_DEPTH_M),
            _depth_colors(prediction, MAX_DEPTH_M),
            _depth_colors(np.abs(prediction - truth), 6.0),
        ),
        axis=1,
    )
    height, width = panels.shape[:2]
    return f"P6\n{width} {height}\n255\n".encode("ascii") + panels.tobytes()


def _write_visualizations(run_dir: Path, manifest: dict[str, Any]) -> None:
    output = run_dir / "output/visualizations"
    output.mkdir()
    for case in manifest["cases"]:
        shape = (int(case["height"]), int(case["width"]))
        truth = _load_depth_output(
            run_dir / "input" / case["depth_path"], shape, np.dtype("float32")
        )
        prediction = _load_depth_output(
            run_dir / "output/predictions" / f"{case['id']}.depth.npy",
            shape,
            np.dtype("float32"),
        )
        (output / f"{case['id']}-comparison.ppm").write_bytes(
            _comparison_ppm(truth, prediction)
        )


def _validate_visualizations(run_dir: Path, manifest: dict[str, Any]) -> None:
    for case in manifest["cases"]:
        shape = (int(case["height"]), int(case["width"]))
        truth = _load_depth_output(
            run_dir / "input" / case["depth_path"], shape, np.dtype("float32")
        )
        prediction = _load_depth_output(
            run_dir / "output/predictions" / f"{case['id']}.depth.npy",
            shape,
            np.dtype("float32"),
        )
        path = _require_regular_file(
            run_dir, f"output/visualizations/{case['id']}-comparison.ppm"
        )
        if path.read_bytes() != _comparison_ppm(truth, prediction):
            raise ValueError(f"learned-depth visualization mismatch: {case['id']}")


def _checkpoint_record() -> dict[str, Any]:
    matches = [
        item
        for item in load_json(ROOT / "assets.lock.json")["assets"]
        if item.get("id") == CHECKPOINT_ID
    ]
    if len(matches) != 1:
        raise ValueError("Depth Anything checkpoint asset registry mismatch")
    record = matches[0]
    if (
        record.get("mode") != "download"
        or record.get("license") != "Apache-2.0"
        or record.get("sha256") != CHECKPOINT_SHA256
        or record.get("byte_size") != CHECKPOINT_BYTES
        or CHECKPOINT_REVISION not in str(record.get("source", ""))
        or record.get("consumers") != ["depth-anything-v2-reference"]
    ):
        raise ValueError("Depth Anything checkpoint lock does not match the pinned model contract")
    return record


def _adapter_record() -> dict[str, Any]:
    matches = [
        item
        for item in load_json(ROOT / "reference-adapters.json")["adapters"]
        if item.get("id") == "depth-anything-v2-reference"
    ]
    if len(matches) != 1 or matches[0].get("status") != "landed":
        raise ValueError("Depth Anything adapter registry mismatch")
    return matches[0]


def _checkpoint_path(cache_root: Path, record: dict[str, Any]) -> Path:
    asset_root = cache_root / "assets"
    try:
        asset_mode = asset_root.lstat().st_mode
    except FileNotFoundError as error:
        raise FileNotFoundError(
            f"missing Depth Anything checkpoint asset directory: {asset_root}; "
            f"run `run.sh fetch --asset {CHECKPOINT_ID}`"
        ) from error
    if stat.S_ISLNK(asset_mode) or not stat.S_ISDIR(asset_mode):
        raise ValueError("Depth Anything checkpoint cache must be a real directory")
    path = asset_root / f"{CHECKPOINT_ID}.archive"
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as error:
        raise FileNotFoundError(
            f"missing Depth Anything checkpoint: {path}; run `run.sh fetch --asset {CHECKPOINT_ID}`"
        ) from error
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise ValueError("Depth Anything checkpoint must be a regular non-symlink file")
    size = path.stat().st_size
    if size != record["byte_size"]:
        raise ValueError(
            f"Depth Anything checkpoint byte-size mismatch: expected {record['byte_size']}, got {size}"
        )
    actual = sha256_file(path)
    if actual != record["sha256"]:
        raise ValueError(
            f"Depth Anything checkpoint hash mismatch: expected {record['sha256']}, got {actual}"
        )
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(cache_root.resolve(strict=True))
    except ValueError as error:
        raise ValueError("Depth Anything checkpoint escapes the cache root") from error
    return resolved


def _container_script(checkpoint: dict[str, Any]) -> str:
    return (
        "python /usr/local/bin/run-depth-anything-v2.py "
        "--manifest /work/input/manifest.json "
        "--checkpoint /model/checkpoint.pth "
        f"--checkpoint-sha256 {checkpoint['sha256']} "
        f"--checkpoint-bytes {checkpoint['byte_size']} "
        f"--input-size {INPUT_SIZE} --max-depth {MAX_DEPTH_M:g}"
    )


def _validate_input_manifest(input_root: Path, profile: str) -> dict[str, Any]:
    manifest_path = _require_regular_file(input_root.parent, "input/manifest.json")
    manifest = load_json(manifest_path)
    with tempfile.TemporaryDirectory(prefix="surflo-depth-manifest-") as temporary:
        expected_root = Path(temporary) / "input"
        expected = generate_learned_depth_scene(
            expected_root, load_json(ROOT / "shared-scene.json"), profile
        )
        if manifest != expected:
            raise ValueError("learned-depth input manifest does not match the shared-scene contract")
        for case in expected["cases"]:
            for path_key, hash_key in (
                ("image_path", "image_sha256"),
                ("depth_path", "depth_sha256"),
            ):
                relative = case[path_key]
                actual_path = input_root / relative
                expected_path = expected_root / relative
                try:
                    actual_mode = actual_path.lstat().st_mode
                except FileNotFoundError as error:
                    raise ValueError(f"missing learned-depth input: {relative}") from error
                if stat.S_ISLNK(actual_mode) or not stat.S_ISREG(actual_mode):
                    raise ValueError(f"learned-depth input is not a regular file: {relative}")
                if (
                    sha256_file(actual_path) != case[hash_key]
                    or sha256_file(expected_path) != case[hash_key]
                ):
                    raise ValueError(f"learned-depth input hash mismatch: {relative}")
    return manifest


def _load_depth_output(
    path: Path, expected_shape: tuple[int, int], expected_dtype: np.dtype[Any]
) -> np.ndarray:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as error:
        raise ValueError(f"missing learned-depth output: {path.name}") from error
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise ValueError(f"learned-depth output is not a regular file: {path.name}")
    try:
        values = np.load(path, allow_pickle=False)
    except (OSError, ValueError) as error:
        raise ValueError(f"malformed learned-depth output: {path.name}") from error
    if values.shape != expected_shape or values.dtype != expected_dtype:
        raise ValueError(f"learned-depth output shape or dtype mismatch: {path.name}")
    return values


def _weighted_metrics(records: list[dict[str, Any]]) -> dict[str, float | int]:
    if not records:
        raise ValueError("cannot aggregate an empty learned-depth metric set")
    total = sum(int(record["valid_pixels"]) for record in records)
    if total <= 0:
        raise ValueError("learned-depth aggregation has no valid pixels")

    def weighted(key: str) -> float:
        return float(
            sum(float(record[key]) * int(record["valid_pixels"]) for record in records) / total
        )

    return {
        "valid_pixels": total,
        "raw_rmse_m": float(
            math.sqrt(
                sum(
                    float(record["raw_rmse_m"]) ** 2 * int(record["valid_pixels"])
                    for record in records
                )
                / total
            )
        ),
        "raw_abs_rel": weighted("raw_abs_rel"),
        "raw_delta1": weighted("raw_delta1"),
        "affine_aligned_rmse_m": float(
            math.sqrt(
                sum(
                    float(record["affine_aligned_rmse_m"]) ** 2
                    * int(record["valid_pixels"])
                    for record in records
                )
                / total
            )
        ),
        "affine_aligned_abs_rel": weighted("affine_aligned_abs_rel"),
    }


def _evaluate_outputs(
    run_dir: Path, profile: str
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    manifest = _validate_input_manifest(run_dir / "input", profile)
    case_metrics: dict[str, dict[str, Any]] = {}
    family_records: dict[str, list[dict[str, Any]]] = {
        family: [] for family in manifest["case_families"]
    }
    profile_predictions: list[np.ndarray] = []
    profile_targets: list[np.ndarray] = []
    total_pixels = 0
    for case in manifest["cases"]:
        shape = (int(case["height"]), int(case["width"]))
        truth = _load_depth_output(run_dir / "input" / case["depth_path"], shape, np.dtype("float32"))
        prediction = _load_depth_output(
            run_dir / "output/predictions" / f"{case['id']}.depth.npy",
            shape,
            np.dtype("float32"),
        )
        valid = _load_depth_output(
            run_dir / "output/predictions" / f"{case['id']}.valid.npy",
            shape,
            np.dtype("uint8"),
        )
        if not np.isin(valid, np.array([0, 1], dtype=np.uint8)).all():
            raise ValueError(f"learned-depth validity mask is not binary: {case['id']}")
        if not np.isfinite(prediction[valid.astype(bool)]).all():
            raise ValueError(f"learned-depth prediction contains non-finite valid values: {case['id']}")
        evaluation_mask = (
            valid.astype(bool)
            & np.isfinite(prediction)
            & (prediction > 0.0)
            & np.isfinite(truth)
            & (truth > 0.0)
        )
        masked = np.where(evaluation_mask, prediction, np.nan)
        measured = _depth_metrics(masked, truth)
        record = {"family": case["family"], **measured}
        case_metrics[case["id"]] = record
        family_records[case["family"]].append(measured)
        profile_predictions.append(prediction[evaluation_mask].astype(np.float64))
        profile_targets.append(truth[evaluation_mask].astype(np.float64))
        total_pixels += int(truth.size)

    aggregate = _weighted_metrics(
        [{key: value for key, value in record.items() if key != "family"} for record in case_metrics.values()]
    )
    profile_affine = _affine_metrics(
        np.concatenate(profile_predictions), np.concatenate(profile_targets)
    )
    metrics: dict[str, Any] = {
        "evaluated_cases": len(case_metrics),
        "evaluated_pixels": total_pixels,
        "valid_pixels": aggregate["valid_pixels"],
        "valid_pixel_fraction": float(aggregate["valid_pixels"] / total_pixels),
        **{
            key: value
            for key, value in aggregate.items()
            if key
            not in {
                "valid_pixels",
                "affine_aligned_rmse_m",
                "affine_aligned_abs_rel",
            }
        },
        **profile_affine,
    }
    for family, records in family_records.items():
        family_metric = _weighted_metrics(records)
        prefix = family.replace("-", "_")
        metrics[f"{prefix}_raw_rmse_m"] = family_metric["raw_rmse_m"]
        metrics[f"{prefix}_affine_aligned_rmse_m"] = family_metric[
            "affine_aligned_rmse_m"
        ]
    metrics["failure_raw_rmse_gap_m"] = float(
        max(metrics["focal_crop_raw_rmse_m"], metrics["ood_concavity_raw_rmse_m"])
        - metrics["shared_scene_raw_rmse_m"]
    )
    ensure_finite(metrics, "learned-depth metrics")
    ensure_finite(case_metrics, "learned-depth case metrics")
    return metrics, case_metrics


def _values_match(recorded: Any, recomputed: Any) -> bool:
    if isinstance(recomputed, dict):
        return isinstance(recorded, dict) and recorded.keys() == recomputed.keys() and all(
            _values_match(recorded[key], value) for key, value in recomputed.items()
        )
    if isinstance(recomputed, int) and not isinstance(recomputed, bool):
        return isinstance(recorded, int) and not isinstance(recorded, bool) and recorded == recomputed
    if isinstance(recomputed, float):
        return (
            isinstance(recorded, (int, float))
            and not isinstance(recorded, bool)
            and math.isclose(float(recorded), recomputed, rel_tol=1e-10, abs_tol=1e-12)
        )
    return recorded == recomputed


def _acceptance_failures(metrics: dict[str, Any], acceptance: dict[str, Any]) -> list[str]:
    failures = []
    for metric, threshold in acceptance.items():
        if metric.endswith("_min"):
            name = metric.removesuffix("_min")
            if metrics[name] < threshold:
                failures.append(f"{name}={metrics[name]} < {threshold}")
        elif metric.endswith("_max"):
            name = metric.removesuffix("_max")
            if metrics[name] > threshold:
                failures.append(f"{name}={metrics[name]} > {threshold}")
        else:
            raise ValueError(f"unsupported learned-depth acceptance key: {metric}")
    return failures


def _validate_runtime_identity(run_dir: Path) -> dict[str, Any]:
    source_commit = _require_regular_file(run_dir, "output/source-commit.txt").read_text(
        encoding="utf-8"
    ).strip()
    if source_commit != PINNED_SOURCE_COMMIT:
        raise ValueError("Depth Anything source commit mismatch")
    manifest = _parse_key_value_manifest(
        _require_regular_file(run_dir, "output/insula-manifest.txt")
    )
    if manifest != PINNED_INSULA_MANIFEST:
        raise ValueError("neural-rendering Insula manifest mismatch")
    versions = load_json(_require_regular_file(run_dir, "output/runtime-versions.json"))
    if (
        versions.get("source_commit") != PINNED_SOURCE_COMMIT
        or versions.get("torch") != "2.13.0+cu132"
        or versions.get("torchvision") != "0.28.0+cu132"
        or not isinstance(versions.get("numpy"), str)
        or not versions["numpy"]
        or versions.get("opencv") != "4.13.0"
        or versions.get("cuda_runtime") != "13.2"
        or not isinstance(versions.get("device"), str)
        or not versions["device"]
    ):
        raise ValueError("Depth Anything runtime identity mismatch")
    return versions


def _validate_resources(run_dir: Path, result: dict[str, Any]) -> None:
    resources = result["resources"]
    runtime = resources.get("runtime_seconds")
    if isinstance(runtime, bool) or not isinstance(runtime, (int, float)) or runtime < 0:
        raise ValueError("runtime must be a finite non-negative number")
    for key in ("peak_cpu_memory_bytes", "peak_gpu_compute_memory_bytes"):
        value = resources.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{key} must be a non-negative integer")
    if (
        resources.get("gpu_memory_scope") != "container-cgroup-compute-process-sum"
        or resources.get("gpu_selection") != "one healthy host GPU mapped to CUDA device 0"
        or not isinstance(resources.get("gpu_host_index"), int)
        or resources.get("gpu_measurement_status") not in {"measured", "unavailable"}
        or not isinstance(resources.get("gpu_hardware"), list)
        or not isinstance(resources.get("host"), str)
        or not resources["host"]
    ):
        raise ValueError("invalid learned-depth resource metadata")
    if resources["gpu_measurement_status"] == "measured":
        if resources["peak_gpu_compute_memory_bytes"] <= 0 or not resources["gpu_hardware"]:
            raise ValueError("measured GPU resources require hardware and a positive peak")
    elif resources["peak_gpu_compute_memory_bytes"] != 0:
        raise ValueError("unavailable GPU measurement must record a zero peak")
    if load_json(run_dir / "output/resource-summary.json") != resources:
        raise ValueError("resource summary mismatch")


def validate_depth_reference_result(run_dir: Path) -> dict[str, Any]:
    result_path = run_dir / "result.json"
    if not result_path.is_file():
        raise ValueError(f"missing reference result: {result_path}")
    result = load_json(result_path)
    validate_json_schema_instance(
        result, load_json(ROOT / "reference-result.schema.json"), "reference-result"
    )
    ensure_finite(result, "reference-result")
    if (
        result.get("adapter") != ADAPTER
        or result.get("module_ids") != ["08"]
        or result.get("status") != "complete"
        or result.get("network_mode") != "offline"
    ):
        raise ValueError("module scope mismatch: Depth Anything V2 belongs to module 08")
    if result.get("support") != SUPPORT_CONTRACT:
        raise ValueError("learned-depth support/claim contract mismatch")
    tool = result["tool"]
    if (
        tool.get("name") != TOOL_NAME
        or tool.get("version") != TOOL_VERSION
        or tool.get("package_version") != TOOL_PACKAGE_VERSION
        or tool.get("source_commit") != PINNED_SOURCE_COMMIT
        or tool.get("container_image") != IMAGE
        or not isinstance(tool.get("container_image_id"), str)
        or IMAGE_ID_PATTERN.fullmatch(tool["container_image_id"]) is None
    ):
        raise ValueError("Depth Anything tool identity mismatch")
    provenance = result["provenance"]
    config = provenance["config"]
    if provenance.get("config_sha256") != hashlib.sha256(canonical_json(config)).hexdigest():
        raise ValueError("config hash mismatch")
    validate_run_id(config.get("run_id", ""))
    checkpoint = _checkpoint_record()
    acceptance = _adapter_record()["acceptance"][result["profile"]]
    if (
        config.get("adapter") != ADAPTER
        or config.get("profile") != result["profile"]
        or config.get("module_ids") != ["08"]
        or config.get("image") != tool["container_image"]
        or config.get("image_id") != tool["container_image_id"]
        or config.get("scene_contract_sha256") != sha256_file(ROOT / "shared-scene.json")
        or config.get("input_manifest_sha256") != sha256_file(run_dir / "input/manifest.json")
        or config.get("source_commit") != PINNED_SOURCE_COMMIT
        or config.get("checkpoint") != checkpoint
        or config.get("input_size") != INPUT_SIZE
        or config.get("max_depth_m") != MAX_DEPTH_M
        or config.get("container_user_environment") != {"USER": "surflo"}
        or config.get("support") != SUPPORT_CONTRACT
        or config.get("evaluation_software") != EVALUATION_SOFTWARE
        or config.get("cuda_cache") != CUDA_CACHE_POLICY
        or config.get("acceptance") != acceptance
        or result.get("acceptance") != acceptance
    ):
        raise ValueError("learned-depth config binding mismatch")
    implementation = {name: sha256_file(ROOT / name) for name in REFERENCE_IMPLEMENTATION}
    if provenance.get("implementation_sha256") != implementation:
        raise ValueError("implementation hash mismatch")
    if _hash_tree(run_dir) != provenance.get("artifacts_sha256"):
        raise ValueError("artifact hash mismatch")
    if load_json(run_dir / "output/checkpoint.json") != checkpoint:
        raise ValueError("checkpoint provenance mismatch")
    _validate_runtime_identity(run_dir)
    metrics, case_metrics = _evaluate_outputs(run_dir, result["profile"])
    _validate_visualizations(run_dir, load_json(run_dir / "input/manifest.json"))
    if not _values_match(result.get("metrics"), metrics) or not _values_match(
        result.get("case_metrics"), case_metrics
    ):
        raise ValueError("Depth Anything metric mismatch")
    failures = _acceptance_failures(metrics, acceptance)
    if failures:
        raise ValueError(
            f"Depth Anything output is below the locked acceptance threshold: {failures}"
        )
    _validate_resources(run_dir, result)
    return result


def _report(profile: str, metrics: dict[str, Any], case_metrics: dict[str, Any]) -> str:
    lines = [
        "# Depth Anything V2 metric-depth reference",
        "",
        f"Profile: `{profile}`. The pinned Metric Hypersim Small model ran offline on "
        f"{metrics['evaluated_cases']} deterministic single-view inputs.",
        "",
        f"Raw metric RMSE/AbsRel: {metrics['raw_rmse_m']:.4f} m / "
        f"{metrics['raw_abs_rel']:.4f}. Profile-global affine-aligned RMSE: "
        f"{metrics['affine_aligned_rmse_m']:.4f} m at scale "
        f"{metrics['affine_scale']:.4f} and shift {metrics['affine_shift_m']:.4f} m. "
        "Raw metre-space error is the primary metric-depth result; affine alignment is "
        "only a shape diagnostic, and the per-case fits below only localize errors.",
        "",
        "| Case | Family | Raw RMSE (m) | Affine-aligned RMSE (m) | Affine scale | Shift (m) |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for case_id, record in case_metrics.items():
        lines.append(
            f"| `{case_id}` | {record['family']} | {record['raw_rmse_m']:.4f} | "
            f"{record['affine_aligned_rmse_m']:.4f} | {record['affine_scale']:.4f} | "
            f"{record['affine_shift_m']:.4f} |"
        )
    lines.extend(
        [
            "",
            "Every prediction is a prior-conditioned depth for a ray visible in its input image. "
            "The adapter emits no hidden geometry, complete scene, or posterior scene sample; a "
            "plausible OOD map therefore remains deterministic prior behavior, not completion.",
            "",
        ]
    )
    return "\n".join(lines)


def run_depth_reference(cache_root: Path, profile: str, run_id: str) -> Path:
    validate_run_id(run_id)
    if profile not in {"smoke", "full"}:
        raise ValueError(f"unknown profile: {profile}")
    checkpoint_record = _checkpoint_record()
    checkpoint_path = _checkpoint_path(cache_root, checkpoint_record)
    engine = os.environ.get("SURFLO_PATHWAY_CONTAINER_ENGINE", "docker")
    image_id = _inspect_image(engine, IMAGE)
    gpu_hardware = _gpu_hardware(engine)
    if Path(engine).name == "docker" and not gpu_hardware:
        raise ValueError("unable to inventory GPU hardware for the real Depth Anything reference")
    gpu_device = selected_gpu_device(require_health=Path(engine).name == "docker")

    cache_root.mkdir(parents=True, exist_ok=True)
    cache_root = cache_root.resolve(strict=True)
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
        generate_learned_depth_scene(
            staging / "input", load_json(ROOT / "shared-scene.json"), profile
        )
        (staging / "output").mkdir()
        write_json(staging / "output/checkpoint.json", checkpoint_record)
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
            "-v",
            f"{cuda_cache}:/cuda-cache",
            "-v",
            f"{staging.resolve()}:/work",
            "-v",
            f"{checkpoint_path}:/model/checkpoint.pth:ro",
            image_id,
            "/usr/bin/time",
            "-v",
            "-o",
            "/work/output/resource-usage.txt",
            "bash",
            "-lc",
            _container_script(checkpoint_record),
        ]
        completed, peak_gpu = _run_monitored(command, staging / "container.cid")
        (staging / "adapter.log").write_text(
            completed.stdout + completed.stderr, encoding="utf-8"
        )
        if completed.returncode != 0:
            raise ValueError(
                f"Depth Anything adapter failed ({completed.returncode}): {completed.stderr.strip()}"
            )
        if Path(engine).name == "docker" and peak_gpu <= 0:
            raise ValueError("unable to measure compute memory for Depth Anything GPU inference")
        _validate_runtime_identity(staging)
        metrics, case_metrics = _evaluate_outputs(staging, profile)
        _write_visualizations(staging, load_json(staging / "input/manifest.json"))
        acceptance = _adapter_record()["acceptance"][profile]
        failures = _acceptance_failures(metrics, acceptance)
        if failures:
            raise ValueError(
                f"Depth Anything output is below the locked acceptance threshold: {failures}"
            )
        (staging / "report.md").write_text(
            _report(profile, metrics, case_metrics), encoding="utf-8"
        )
        resources = {
            "runtime_seconds": time.perf_counter() - started,
            "peak_cpu_memory_bytes": _peak_cpu_memory_bytes(
                staging / "output/resource-usage.txt"
            ),
            "peak_gpu_compute_memory_bytes": peak_gpu,
            "gpu_memory_scope": "container-cgroup-compute-process-sum",
            "gpu_measurement_status": "measured" if peak_gpu > 0 else "unavailable",
            "gpu_selection": "one healthy host GPU mapped to CUDA device 0",
            "gpu_host_index": int(gpu_device),
            "gpu_hardware": gpu_hardware,
            "host": platform.platform(),
        }
        write_json(staging / "output/resource-summary.json", resources)
        config = {
            "adapter": ADAPTER,
            "profile": profile,
            "run_id": run_id,
            "module_ids": ["08"],
            "image": IMAGE,
            "image_id": image_id,
            "scene_contract_sha256": sha256_file(ROOT / "shared-scene.json"),
            "input_manifest_sha256": sha256_file(staging / "input/manifest.json"),
            "source_commit": PINNED_SOURCE_COMMIT,
            "checkpoint": checkpoint_record,
            "input_size": INPUT_SIZE,
            "max_depth_m": MAX_DEPTH_M,
            "container_user_environment": {"USER": "surflo"},
            "support": SUPPORT_CONTRACT,
            "evaluation_software": EVALUATION_SOFTWARE,
            "cuda_cache": CUDA_CACHE_POLICY,
            "acceptance": acceptance,
        }
        result = {
            "schema_version": 1,
            "adapter": ADAPTER,
            "module_ids": ["08"],
            "profile": profile,
            "status": "complete",
            "network_mode": "offline",
            "metrics": metrics,
            "case_metrics": case_metrics,
            "support": SUPPORT_CONTRACT,
            "acceptance": acceptance,
            "tool": {
                "name": TOOL_NAME,
                "version": TOOL_VERSION,
                "package_version": TOOL_PACKAGE_VERSION,
                "source_commit": PINNED_SOURCE_COMMIT,
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
        ensure_finite(result, "reference-result")
        write_json(staging / "result.json", result)
        validate_depth_reference_result(staging)
        final_parent.mkdir()
        os.replace(staging, final)
        return final
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
