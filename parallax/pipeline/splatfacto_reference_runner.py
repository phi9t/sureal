"""Offline Nerfstudio Splatfacto maintained-reference execution for module 11."""

from __future__ import annotations

import csv
import hashlib
import math
import os
from pathlib import Path
import platform
import shutil
import stat
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
from pipeline.nerfacto_reference_runner import (
    _image_metrics,
    _nearest,
    _points_from_depth,
    _psnr,
    _sample_points,
    _validate_input_manifest,
    _values_match,
)
from pipeline.reference_runner import (
    _hash_tree,
    _inspect_image,
    _parse_key_value_manifest,
    _require_regular_file,
    _secure_directory,
)
from pipeline.reference_scene import generate_radiance_field_scene


ADAPTER = "splatfacto"
IMAGE = "surflo-pathway-gaussian-splatting:1"
PINNED_NERFSTUDIO_COMMIT = "50e0e3c70c775e89333256213363badbf074f29d"
PINNED_GSPLAT_COMMIT = "4d3a3b69db4de0326f983ccf7b7b255271a17b01"
PINNED_GSPLAT_VERSION = "1.4.0"
REQUIREMENTS_LOCK_SHA256 = "02c623f2a636dd774dda048f1a08c8d936d0701f74d3f50b3a7916d2280ed65a"
RESOLVED_REQUIREMENTS_SHA256 = "587350cc8d7a65840facd27ebcf6fabc43f1e09d4f82541efa851ae914631076"
LPIPS_CHECKPOINT_ID = "nerfstudio-lpips-alexnet"
LPIPS_CHECKPOINT_SHA256 = "7be5be791159472b1fbf3c69796f7cb30dca7ad8466c2df70058c37116cdee02"
LPIPS_CHECKPOINT_BYTES = 244408911
LPIPS_CHECKPOINT_FILENAME = "alexnet-owt-7be5be79.pth"
IMAGE_ID_PATTERN = __import__("re").compile(r"sha256:[0-9a-f]{64}")
SEED = 260925
DETERMINISTIC_ENVIRONMENT = {
    "USER": "surflo",
    "PYTHONHASHSEED": str(SEED),
    "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
    "NVIDIA_TF32_OVERRIDE": "0",
}
PROFILE_CONFIG = {
    "smoke": {"iterations": 1000},
    "full": {"iterations": 30000},
}
SUPPORT_CONTRACT = {
    "render_score_domain": "three held-out target RGB images",
    "geometry_score_domain": "accumulation-qualified expected-depth rays on common-visible analytic truth",
    "accumulation_threshold": 0.5,
    "depth_semantics": "ordered alpha-compositing expectation; not a first surface intersection",
    "triangle_mesh": "unsupported",
    "canonical_surface": "unsupported",
    "hidden_surface_completion": "unsupported",
    "completion_claim": "none",
    "posterior_sampling_claim": "none",
    "complete_scene_samples": 0,
}
PINNED_INSULA_MANIFEST = {
    "schema_version": "1",
    "kind": "gaussian-splatting",
    "cuda": "12.8.1",
    "python": "3.12",
    "torch": "2.7.1+cu128",
    "torchvision": "0.22.1+cu128",
    "pillow": "11.1.0",
    "nerfstudio_commit": PINNED_NERFSTUDIO_COMMIT,
    "gsplat_commit": PINNED_GSPLAT_COMMIT,
    "gsplat_version": PINNED_GSPLAT_VERSION,
    "torch_cuda_arch_list": "10.0",
    "requirements_lock_sha256": REQUIREMENTS_LOCK_SHA256,
    "resolved_requirements_sha256": RESOLVED_REQUIREMENTS_SHA256,
    "network_policy": "build-and-fetch-only",
}
REFERENCE_IMPLEMENTATION = (
    "pipeline/cli.py",
    "pipeline/contracts.py",
    "pipeline/reference_runner.py",
    "pipeline/mvs_reference_runner.py",
    "pipeline/nerfacto_reference_runner.py",
    "pipeline/splatfacto_reference_runner.py",
    "pipeline/reference_scene.py",
    "insulas/build.sh",
    "insulas/gaussian-splatting/Dockerfile",
    "insulas/gaussian-splatting/run-splatfacto.py",
    "insulas/radiance-field/requirements.lock.txt",
    "insulas/radiance-field/resolved-requirements.lock.txt",
    "insulas/locks.json",
    "assets.lock.json",
    "reference-result.schema.json",
    "shared-scene.json",
)


def validate_gaussian_archive(path: Path) -> dict[str, Any]:
    """Validate and summarize the explicit Gaussian parameter archive."""
    try:
        archive = np.load(path, allow_pickle=False)
    except (OSError, ValueError) as error:
        raise ValueError("malformed Splatfacto Gaussian archive") from error
    required = {
        "means": (3,),
        "log_scales": (3,),
        "quaternions": (4,),
        "opacity_logits": (1,),
        "features_dc": (3,),
    }
    try:
        if set(archive.files) != set(required):
            raise ValueError("Splatfacto Gaussian archive inventory mismatch")
        arrays = {name: archive[name] for name in required}
    finally:
        archive.close()
    counts = {array.shape[0] for array in arrays.values() if array.ndim == 2}
    if len(counts) != 1 or not counts or next(iter(counts)) <= 0:
        raise ValueError("Splatfacto Gaussian parameter count mismatch")
    count = next(iter(counts))
    for name, trailing in required.items():
        array = arrays[name]
        if (
            array.dtype != np.float32
            or array.shape != (count, *trailing)
            or not np.isfinite(array).all()
        ):
            raise ValueError(f"Splatfacto Gaussian {name} shape, dtype, or finiteness mismatch")
    quaternion_norm = np.linalg.norm(arrays["quaternions"].astype(np.float64), axis=1)
    if not np.allclose(quaternion_norm, 1.0, atol=1e-4, rtol=1e-4):
        raise ValueError("Splatfacto Gaussian parameters require a unit quaternion")
    scales = np.exp(arrays["log_scales"].astype(np.float64))
    if not np.isfinite(scales).all() or np.any(scales <= 0.0):
        raise ValueError("Splatfacto Gaussian scales are invalid")
    opacity = 1.0 / (1.0 + np.exp(-arrays["opacity_logits"].astype(np.float64)))
    anisotropy = np.max(scales, axis=1) / np.min(scales, axis=1)
    metrics: dict[str, int | float] = {
        "primitive_count": int(count),
        "parameter_bytes": int(sum(array.nbytes for array in arrays.values())),
        "scale_min_m": float(np.min(scales)),
        "scale_median_m": float(np.median(scales)),
        "scale_p95_m": float(np.quantile(scales, 0.95)),
        "scale_max_m": float(np.max(scales)),
        "scale_anisotropy_median": float(np.median(anisotropy)),
        "scale_anisotropy_p95": float(np.quantile(anisotropy, 0.95)),
        "opacity_median": float(np.median(opacity)),
        "opacity_ge_0_1_count": int(np.count_nonzero(opacity >= 0.1)),
        "opacity_ge_0_5_count": int(np.count_nonzero(opacity >= 0.5)),
        "opacity_ge_0_9_count": int(np.count_nonzero(opacity >= 0.9)),
        "center_radius_median_m": float(
            np.median(np.linalg.norm(arrays["means"].astype(np.float64), axis=1))
        ),
    }
    if not all(math.isfinite(float(value)) for value in metrics.values()):
        raise ValueError("Splatfacto Gaussian summary is non-finite")
    return metrics


def _adapter_record() -> dict[str, Any]:
    return next(
        item
        for item in load_json(ROOT / "reference-adapters.json")["adapters"]
        if item["id"] == "nerfstudio-splatfacto-reference"
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
            "acceptance",
            "baseline_environment",
        )
    }
    return hashlib.sha256(canonical_json(contract)).hexdigest()


def _approved_image_id() -> str:
    image_id = _adapter_record().get("baseline_environment", {}).get(
        "container_image_id"
    )
    if IMAGE_ID_PATTERN.fullmatch(str(image_id)) is None:
        raise ValueError("Splatfacto approved calibration image ID is invalid")
    return str(image_id)


def _lpips_checkpoint_record() -> dict[str, Any]:
    matches = [
        item
        for item in load_json(ROOT / "assets.lock.json")["assets"]
        if item.get("id") == LPIPS_CHECKPOINT_ID
    ]
    if len(matches) != 1:
        raise ValueError("Splatfacto LPIPS checkpoint asset registry mismatch")
    record = matches[0]
    if (
        record.get("mode") != "download"
        or record.get("sha256") != LPIPS_CHECKPOINT_SHA256
        or record.get("byte_size") != LPIPS_CHECKPOINT_BYTES
        or "nerfstudio-splatfacto-reference" not in record.get("consumers", [])
        or not str(record.get("source", "")).endswith(LPIPS_CHECKPOINT_FILENAME)
    ):
        raise ValueError("Splatfacto LPIPS checkpoint lock mismatch")
    return record


def _lpips_checkpoint_path(cache_root: Path, record: dict[str, Any]) -> Path:
    path = cache_root / "assets" / f"{LPIPS_CHECKPOINT_ID}.archive"
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as error:
        raise FileNotFoundError(
            f"missing Splatfacto LPIPS checkpoint: {path}; "
            f"run `run.sh fetch --asset {LPIPS_CHECKPOINT_ID}`"
        ) from error
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise ValueError("Splatfacto LPIPS checkpoint must be a regular non-symlink file")
    if path.stat().st_size != record["byte_size"] or sha256_file(path) != record["sha256"]:
        raise ValueError("Splatfacto LPIPS checkpoint hash or byte-size mismatch")
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(cache_root.resolve(strict=True))
    except ValueError as error:
        raise ValueError("Splatfacto LPIPS checkpoint escapes the cache root") from error
    return resolved


def _regular_npy(path: Path, label: str) -> np.ndarray:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as error:
        raise ValueError(f"missing Splatfacto {label}: {path.name}") from error
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise ValueError(f"Splatfacto {label} is not a regular file: {path.name}")
    try:
        return np.load(path, allow_pickle=False)
    except (OSError, ValueError) as error:
        raise ValueError(f"malformed Splatfacto {label}: {path.name}") from error


def _mean(rows: list[dict[str, Any]], key: str) -> float:
    return float(np.mean([float(row[key]) for row in rows]))


def _expected_resolved_requirements() -> bytes:
    source = (ROOT / "insulas/radiance-field/resolved-requirements.lock.txt").read_text()
    expected = source.replace(
        "gsplat==1.4.0\n", "gsplat @ file:///opt/src/gsplat\n"
    ).encode()
    if hashlib.sha256(expected).hexdigest() != RESOLVED_REQUIREMENTS_SHA256:
        raise ValueError("Splatfacto transformed resolved dependency lock mismatch")
    return expected


def _binary_ply_header(path: Path) -> tuple[list[str], int]:
    """Read only the ASCII header of a binary PLY artifact."""
    lines: list[str] = []
    size = 0
    with path.open("rb") as stream:
        while True:
            line = stream.readline(4097)
            if not line:
                raise ValueError("Splatfacto PLY is missing end_header")
            size += len(line)
            if size > 65536 or len(line) > 4096:
                raise ValueError("Splatfacto PLY header exceeds 64 KiB")
            try:
                decoded = line.decode("ascii", errors="strict")
            except UnicodeDecodeError as error:
                raise ValueError("Splatfacto PLY header is not ASCII") from error
            lines.append(decoded.rstrip("\r\n"))
            if line.rstrip(b"\r\n") == b"end_header":
                return lines, size


def _validate_gaussian_ply(
    path: Path, archive_path: Path, primitive_count: int
) -> int:
    property_names = (
        "x", "y", "z", "nx", "ny", "nz", "f_dc_0", "f_dc_1", "f_dc_2",
        "opacity", "scale_0", "scale_1", "scale_2", "rot_0", "rot_1", "rot_2", "rot_3",
    )
    expected_header = [
        "ply",
        "format binary_little_endian 1.0",
        "comment renderable_primitives_not_mesh",
        f"element vertex {primitive_count}",
        *(f"property float {name}" for name in property_names),
        "end_header",
    ]
    header, payload_offset = _binary_ply_header(path)
    if header != expected_header:
        raise ValueError("Splatfacto PLY schema or semantics mismatch")
    dtype = np.dtype([(name, "<f4") for name in property_names])
    contents = path.read_bytes()
    expected_size = payload_offset + primitive_count * dtype.itemsize
    if len(contents) != expected_size:
        raise ValueError(
            f"Splatfacto PLY payload length mismatch: {len(contents)} != {expected_size}"
        )
    records = np.frombuffer(contents, dtype=dtype, count=primitive_count, offset=payload_offset)
    matrix = records.view("<f4").reshape(primitive_count, len(property_names))
    if not np.isfinite(matrix).all():
        raise ValueError("Splatfacto PLY payload is non-finite")
    with np.load(archive_path, allow_pickle=False) as archive:
        expected = np.column_stack(
            (
                archive["means"],
                np.zeros((primitive_count, 3), dtype=np.float32),
                archive["features_dc"],
                archive["opacity_logits"],
                archive["log_scales"],
                archive["quaternions"],
            )
        ).astype(np.float32, copy=False)
    if not np.array_equal(matrix, expected):
        raise ValueError("Splatfacto PLY payload does not match Gaussian archive")
    return len(contents)


def _evaluate_outputs(run_dir: Path, profile: str) -> dict[str, Any]:
    manifest = _validate_input_manifest(run_dir / "input", profile)
    target_perceptual = load_json(
        _require_regular_file(run_dir, "output/target-image-metrics.json")
    )
    context_perceptual = load_json(
        _require_regular_file(run_dir, "output/context-image-metrics.json")
    )
    target_frames = manifest["target_frames"]
    frame_by_id = {
        frame["id"]: frame
        for frame in manifest["context_frames"] + manifest["target_frames"]
    }
    contexts = [frame_by_id[item] for item in manifest["primary_context_frame_ids"]]
    if [row.get("id") for row in target_perceptual] != [
        frame["id"] for frame in target_frames
    ] or [row.get("id") for row in context_perceptual] != [
        frame["id"] for frame in contexts
    ]:
        raise ValueError("Splatfacto image metric inventory mismatch")

    target_rows: list[dict[str, Any]] = []
    context_rows: list[dict[str, Any]] = []
    residuals: list[np.ndarray] = []
    truth_depths: list[np.ndarray] = []
    predicted_points: list[np.ndarray] = []
    truth_points: list[np.ndarray] = []
    unsupported_residuals: list[np.ndarray] = []
    unsupported_truth_depths: list[np.ndarray] = []
    supported_total = supported_qualified = 0
    unsupported_total = unsupported_qualified = 0
    threshold = float(SUPPORT_CONTRACT["accumulation_threshold"])
    for frame, perceptual in zip(target_frames, target_perceptual):
        prefix = run_dir / "output/target-renders" / frame["id"]
        predicted = _regular_npy(Path(f"{prefix}.rgb.float32.npy"), "target RGB")
        accumulation = _regular_npy(
            Path(f"{prefix}.accumulation.npy"), "target accumulation"
        )
        expected_depth = _regular_npy(
            Path(f"{prefix}.expected-camera-depth.npy"), "target expected depth"
        )
        truth = _regular_npy(
            run_dir / "input" / frame["rgb_truth_path"], "target truth RGB"
        ).astype(np.float64) / 255.0
        truth_depth = _regular_npy(
            run_dir / "input" / frame["depth_path"], "target truth depth"
        )
        common = _regular_npy(
            run_dir / "input" / frame["common_visible_mask_path"], "target support"
        ).astype(bool)
        shape = truth_depth.shape
        if (
            predicted.shape != (*shape, 3)
            or truth.shape != predicted.shape
            or accumulation.shape != shape
            or expected_depth.shape != shape
            or common.shape != shape
            or not all(np.isfinite(value).all() for value in (predicted, accumulation, expected_depth))
            or np.any(accumulation < 0.0)
            or np.any(accumulation > 1.0001)
        ):
            raise ValueError("Splatfacto target render shape, range, or finiteness mismatch")
        foreground = truth_depth > 0.0
        target_rows.append(
            {"id": frame["id"], **_image_metrics(predicted, truth, foreground, perceptual)}
        )
        qualified = (accumulation >= threshold) & (expected_depth > 0.0)
        supported = foreground & common
        unsupported = foreground & ~common
        valid = supported & qualified
        unsupported_valid = unsupported & qualified
        supported_total += int(np.count_nonzero(supported))
        supported_qualified += int(np.count_nonzero(valid))
        unsupported_total += int(np.count_nonzero(unsupported))
        unsupported_qualified += int(np.count_nonzero(unsupported_valid))
        if np.any(valid):
            residuals.append(expected_depth[valid] - truth_depth[valid])
            truth_depths.append(truth_depth[valid])
            predicted_points.append(
                _points_from_depth(expected_depth, valid, frame, manifest["intrinsics"])
            )
            truth_points.append(
                _points_from_depth(truth_depth, supported, frame, manifest["intrinsics"])
            )
        if np.any(unsupported_valid):
            unsupported_residuals.append(
                expected_depth[unsupported_valid] - truth_depth[unsupported_valid]
            )
            unsupported_truth_depths.append(truth_depth[unsupported_valid])
    if not residuals or supported_total == 0:
        raise ValueError("Splatfacto has no qualified common-visible geometry rays")
    residual = np.concatenate(residuals).astype(np.float64)
    truth_depth = np.concatenate(truth_depths).astype(np.float64)
    predicted_xyz = _sample_points(np.concatenate(predicted_points, axis=0))
    truth_xyz = _sample_points(np.concatenate(truth_points, axis=0))
    accuracy = _nearest(predicted_xyz, truth_xyz)
    completeness = _nearest(truth_xyz, predicted_xyz)
    geometry: dict[str, int | float | str] = {
        "depth_semantics": SUPPORT_CONTRACT["depth_semantics"],
        "common_visible_truth_rays": supported_total,
        "common_visible_qualified_rays": supported_qualified,
        "common_visible_accumulation_coverage": supported_qualified / supported_total,
        "expected_depth_rmse_m": float(np.sqrt(np.mean(residual * residual))),
        "expected_depth_abs_rel": float(np.mean(np.abs(residual) / truth_depth)),
        "point_accuracy_rmse_m": float(np.sqrt(np.mean(accuracy * accuracy))),
        "point_completeness_rmse_m": float(np.sqrt(np.mean(completeness * completeness))),
        "point_samples_predicted": int(len(predicted_xyz)),
        "point_samples_truth": int(len(truth_xyz)),
    }
    for threshold_cm in (2, 5, 10):
        distance = threshold_cm / 100.0
        precision = float(np.mean(accuracy <= distance))
        recall = float(np.mean(completeness <= distance))
        geometry[f"point_precision_{threshold_cm}cm"] = precision
        geometry[f"point_recall_{threshold_cm}cm"] = recall
        geometry[f"point_fscore_{threshold_cm}cm"] = (
            0.0 if precision + recall == 0.0 else 2.0 * precision * recall / (precision + recall)
        )

    for frame, perceptual in zip(contexts, context_perceptual):
        prefix = run_dir / "output/context-renders" / frame["id"]
        predicted = _regular_npy(Path(f"{prefix}.rgb.float32.npy"), "context RGB")
        truth = _regular_npy(
            run_dir / "input" / frame["rgb_truth_path"], "context truth RGB"
        ).astype(np.float64) / 255.0
        truth_depth = _regular_npy(
            run_dir / "input" / frame["depth_path"], "context truth depth"
        )
        if predicted.shape != truth.shape or not np.isfinite(predicted).all():
            raise ValueError("Splatfacto context render mismatch")
        context_rows.append(
            {
                "id": frame["id"],
                **_image_metrics(predicted, truth, truth_depth > 0.0, perceptual),
            }
        )

    representation = validate_gaussian_archive(run_dir / "output/gaussians.npz")
    with np.load(run_dir / "output/gaussians.npz", allow_pickle=False) as archive:
        centers = archive["means"].astype(np.float64)
        opacity = 1.0 / (1.0 + np.exp(-archive["opacity_logits"].astype(np.float64)[:, 0]))
    selected = opacity >= 0.5
    if not np.any(selected):
        raise ValueError("Splatfacto has no opacity-qualified primitives")
    center_residual = np.linalg.norm(centers[selected], axis=1) - 0.72
    representation["opacity_ge_0_5_center_sphere_rmse_m"] = float(
        np.sqrt(np.mean(center_residual * center_residual))
    )
    ply = _require_regular_file(run_dir, "output/gaussians.ply")
    representation["ply_bytes"] = _validate_gaussian_ply(
        ply,
        run_dir / "output/gaussians.npz",
        representation["primitive_count"],
    )

    sweep: dict[str, dict[str, float | int]] = {}
    for count in (3, 5, 9):
        psnrs: list[float] = []
        sweep_residuals: list[np.ndarray] = []
        realized_counts: list[int] = []
        for frame in target_frames:
            prefix = run_dir / "output/view-sweep" / f"views-{count}" / frame["id"]
            predicted = _regular_npy(Path(f"{prefix}.rgb.float32.npy"), "sweep RGB")
            accumulation = _regular_npy(Path(f"{prefix}.accumulation.npy"), "sweep accumulation")
            expected = _regular_npy(Path(f"{prefix}.expected-camera-depth.npy"), "sweep depth")
            truth = _regular_npy(
                run_dir / "input" / frame["rgb_truth_path"], "sweep truth RGB"
            ).astype(np.float64) / 255.0
            depth = _regular_npy(
                run_dir / "input" / frame["depth_path"], "sweep truth depth"
            )
            common = _regular_npy(
                run_dir / "input" / frame["common_visible_mask_path"], "sweep support"
            ).astype(bool)
            if predicted.shape != truth.shape or accumulation.shape != depth.shape or expected.shape != depth.shape:
                raise ValueError("Splatfacto view-sweep output mismatch")
            psnrs.append(_psnr(predicted, truth))
            valid = (depth > 0.0) & common & (accumulation >= threshold) & (expected > 0.0)
            if np.any(valid):
                sweep_residuals.append(expected[valid] - depth[valid])
        count_path = _require_regular_file(
            run_dir, f"output/view-sweep/views-{count}/primitive-count.txt"
        )
        try:
            realized_counts.append(int(count_path.read_text().strip()))
        except ValueError as error:
            raise ValueError("Splatfacto view-sweep primitive count mismatch") from error
        if not sweep_residuals or realized_counts[0] <= 0:
            raise ValueError("Splatfacto view sweep lacks geometry or primitives")
        sweep_residual = np.concatenate(sweep_residuals).astype(np.float64)
        sweep[str(count)] = {
            "context_views": count,
            "iterations": 1000,
            "realized_primitive_count": realized_counts[0],
            "target_psnr_db": float(np.mean(psnrs)),
            "expected_depth_rmse_m": float(
                np.sqrt(np.mean(sweep_residual * sweep_residual))
            ),
        }

    csv_path = _require_regular_file(run_dir, "output/failure_sweep.csv")
    with csv_path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != [
            "factor",
            "value",
            "metric",
            "measurement",
            "interpretation",
        ]:
            raise ValueError("Splatfacto failure-sweep columns mismatch")
        csv_rows = list(reader)
    expected_rows: dict[tuple[str, str, str], float] = {}
    for count, values in sweep.items():
        for metric in (
            "target_psnr_db",
            "expected_depth_rmse_m",
            "realized_primitive_count",
        ):
            expected_rows[("context_view_count", count, metric)] = float(values[metric])
    actual_rows: dict[tuple[str, str, str], float] = {}
    for row in csv_rows:
        key = (row["factor"], row["value"], row["metric"])
        if key in actual_rows or not row["interpretation"]:
            raise ValueError("Splatfacto failure-sweep row mismatch")
        actual_rows[key] = float(row["measurement"])
    if actual_rows.keys() != expected_rows.keys() or any(
        not math.isclose(actual_rows[key], value, rel_tol=1e-6, abs_tol=1e-8)
        for key, value in expected_rows.items()
    ):
        raise ValueError("Splatfacto failure-sweep metric mismatch")

    unsupported_file = load_json(_require_regular_file(run_dir, "output/unsupported.json"))
    expected_unsupported = {
        "triangle_mesh": "unsupported",
        "mesh_f_score": "unsupported",
        "canonical_surface": "unsupported",
        "hidden_surface_completion": "unsupported",
        "surface_regularization_sweep": "unsupported_until_separate_sugar_or_2dgs_adapter",
    }
    if unsupported_file != expected_unsupported:
        raise ValueError("Splatfacto unsupported-claim inventory mismatch")
    unsupported_residual = (
        np.concatenate(unsupported_residuals).astype(np.float64)
        if unsupported_residuals
        else np.empty(0, dtype=np.float64)
    )
    unsupported_truth = (
        np.concatenate(unsupported_truth_depths).astype(np.float64)
        if unsupported_truth_depths
        else np.empty(0, dtype=np.float64)
    )
    metrics = {
        "rendering": {
            "metric_implementation": "host-numpy-gaussian-ssim-v1; LPIPS from pinned container",
            "target_psnr_db": _mean(target_rows, "psnr_db"),
            "target_foreground_psnr_db": _mean(target_rows, "foreground_psnr_db"),
            "target_ssim": _mean(target_rows, "ssim"),
            "target_crop_psnr_db": _mean(target_rows, "crop_psnr_db"),
            "target_crop_ssim": _mean(target_rows, "crop_ssim"),
            "target_lpips": _mean(target_rows, "lpips"),
            "target_crop_lpips": _mean(target_rows, "crop_lpips"),
            "target_views": len(target_rows),
            "target_per_view": target_rows,
            "context_fit_psnr_db": _mean(context_rows, "psnr_db"),
            "context_fit_ssim": _mean(context_rows, "ssim"),
            "context_fit_lpips": _mean(context_rows, "lpips"),
            "context_fit_views": len(context_rows),
            "context_fit_per_view": context_rows,
        },
        "geometry": geometry,
        "representation": representation,
        "failure_sweep": sweep,
        "unsupported": {
            **expected_unsupported,
            "truth_rays": unsupported_total,
            "accumulation_qualified_rays": unsupported_qualified,
            "accumulation_coverage": (
                0.0 if unsupported_total == 0 else unsupported_qualified / unsupported_total
            ),
            "expected_depth_rmse_m": (
                0.0
                if not len(unsupported_residual)
                else float(np.sqrt(np.mean(unsupported_residual * unsupported_residual)))
            ),
            "expected_depth_abs_rel": (
                0.0
                if not len(unsupported_residual)
                else float(np.mean(np.abs(unsupported_residual) / unsupported_truth))
            ),
            "completion_claim": "none",
        },
    }
    ensure_finite(metrics, "Splatfacto scored metrics")
    return metrics


def _validate_runtime_identity(run_dir: Path, profile: str) -> dict[str, Any]:
    if _require_regular_file(run_dir, "output/source-commit.txt").read_text().strip() != PINNED_NERFSTUDIO_COMMIT:
        raise ValueError("Splatfacto Nerfstudio source commit mismatch")
    if _require_regular_file(run_dir, "output/gsplat-commit.txt").read_text().strip() != PINNED_GSPLAT_COMMIT:
        raise ValueError("Splatfacto gsplat source commit mismatch")
    manifest = _parse_key_value_manifest(
        _require_regular_file(run_dir, "output/insula-manifest.txt")
    )
    if manifest != PINNED_INSULA_MANIFEST:
        raise ValueError("gaussian-splatting Insula manifest mismatch")
    locks = load_json(ROOT / "insulas/locks.json")["insulas"]["gaussian-splatting"]
    requirements = _require_regular_file(run_dir, "output/requirements.lock.txt")
    resolved = _require_regular_file(run_dir, "output/resolved-requirements.txt")
    if (
        sha256_file(ROOT / "insulas/radiance-field/requirements.lock.txt") != REQUIREMENTS_LOCK_SHA256
        or sha256_file(requirements) != REQUIREMENTS_LOCK_SHA256
        or resolved.read_bytes() != _expected_resolved_requirements()
        or sha256_file(resolved) != RESOLVED_REQUIREMENTS_SHA256
        or locks["resolved_requirements_sha256"] != RESOLVED_REQUIREMENTS_SHA256
    ):
        raise ValueError("Splatfacto dependency lock mismatch")
    versions = load_json(_require_regular_file(run_dir, "output/runtime-versions.json"))
    if (
        versions.get("nerfstudio_commit") != PINNED_NERFSTUDIO_COMMIT
        or versions.get("gsplat_commit") != PINNED_GSPLAT_COMMIT
        or versions.get("gsplat") != PINNED_GSPLAT_VERSION
        or versions.get("gsplat_direct_url") != "file:///opt/src/gsplat"
        or versions.get("resolved_requirements_sha256") != RESOLVED_REQUIREMENTS_SHA256
        or versions.get("torch") != "2.7.1+cu128"
        or versions.get("torchvision") != "0.22.1+cu128"
        or versions.get("pillow") != "11.1.0"
        or versions.get("python") != "3.12.3"
        or versions.get("numpy") != "2.5.2"
        or versions.get("cuda_runtime") != "12.8"
        or "release 12.8" not in str(versions.get("cuda_compiler", ""))
        or versions.get("compute_capability") != [10, 0]
        or versions.get("torch_cuda_arch_list") != "10.0"
        or not versions.get("device")
    ):
        raise ValueError("Splatfacto runtime identity mismatch")
    gates = load_json(_require_regular_file(run_dir, "output/environment-gates.json"))
    if gates.keys() != {
        "compute_capability_10_0",
        "gsplat_forward_backward",
        "splatfacto_forward_backward",
        "camera_round_trip",
    } or not all(gates.values()):
        raise ValueError("Splatfacto environment gate failed")
    summary = load_json(_require_regular_file(run_dir, "output/training-summary.json"))
    expected_iterations = PROFILE_CONFIG[profile]["iterations"]
    if (
        summary.get("method") != "splatfacto"
        or summary.get("iterations") != expected_iterations
        or summary.get("random_init") is not True
        or summary.get("num_random") != 50000
        or summary.get("random_scale") != 2.0
        or summary.get("camera_optimizer") != "off"
        or summary.get("background_color") != "black"
        or summary.get("scale_regularization") is not False
        or summary.get("rasterization_mode") != "classic"
        or summary.get("seed") != SEED
        or summary.get("tf32") is not False
        or summary.get("trained_view_sweep")
        != {"context_views": [3, 5, 9], "iterations": 1000}
        or not isinstance(summary.get("training_seconds"), (int, float))
        or summary["training_seconds"] <= 0.0
        or not math.isclose(
            summary.get("training_steps_per_second", -1.0),
            expected_iterations / summary["training_seconds"],
            rel_tol=1e-9,
        )
        or not isinstance(summary.get("final_primitive_count"), int)
        or summary["final_primitive_count"] <= 0
        or summary.get("render_benchmark", {}).get("warmup_frames") != 20
        or summary.get("render_benchmark", {}).get("measured_frames") != 100
        or summary["render_benchmark"].get("median_fps", 0.0) <= 0.0
        or summary["render_benchmark"].get("p95_latency_ms", 0.0) <= 0.0
    ):
        raise ValueError("Splatfacto training identity mismatch")
    _require_regular_file(run_dir, "output/nerfstudio/checkpoint.ckpt")
    _require_regular_file(run_dir, "output/nerfstudio/config.yml")
    return summary


def _acceptance_failures(metrics: dict[str, Any], acceptance: dict[str, Any]) -> list[str]:
    values = {
        **metrics["rendering"],
        **metrics["geometry"],
        **metrics["representation"],
    }
    failures: list[str] = []
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
            raise ValueError(f"unsupported Splatfacto acceptance key: {key}")
    return failures


def _validated_resources(run_dir: Path, result: dict[str, Any]) -> dict[str, Any]:
    summary = load_json(_require_regular_file(run_dir, "output/resource-summary.json"))
    if result.get("resources") != summary:
        raise ValueError("Splatfacto result resource summary mismatch")
    expected_keys = {
        "runtime_seconds",
        "peak_cpu_memory_bytes",
        "peak_gpu_compute_memory_bytes",
        "gpu_memory_scope",
        "gpu_measurement_status",
        "gpu_selection",
        "gpu_host_index",
        "gpu_hardware",
        "host",
        "training_seconds",
        "training_steps_per_second",
        "render_median_fps",
        "render_p95_latency_ms",
    }
    positive = (
        "runtime_seconds",
        "peak_cpu_memory_bytes",
        "training_seconds",
        "training_steps_per_second",
        "render_median_fps",
        "render_p95_latency_ms",
    )
    if (
        set(summary) != expected_keys
        or any(not isinstance(summary.get(name), (int, float)) for name in positive)
        or any(float(summary[name]) <= 0.0 for name in positive)
        or not isinstance(summary.get("peak_gpu_compute_memory_bytes"), int)
        or summary["peak_gpu_compute_memory_bytes"] < 0
        or summary.get("gpu_measurement_status")
        not in {"measured", "unavailable"}
        or (summary["peak_gpu_compute_memory_bytes"] > 0)
        != (summary["gpu_measurement_status"] == "measured")
        or not isinstance(summary.get("gpu_hardware"), list)
        or not summary.get("host")
    ):
        raise ValueError("Splatfacto resource summary contract mismatch")
    ensure_finite(summary, "Splatfacto resource summary")
    return summary


def _write_visualization(run_dir: Path, metrics: dict[str, Any]) -> None:
    artifacts = run_dir / "artifacts"
    artifacts.mkdir()
    (artifacts / "metric-summary.svg").write_text(
        "<svg xmlns='http://www.w3.org/2000/svg' width='760' height='160'>"
        "<rect width='760' height='160' fill='#101820'/>"
        f"<text x='20' y='44' fill='#f2f2f2'>target PSNR: {metrics['rendering']['target_psnr_db']:.3f} dB</text>"
        f"<text x='20' y='80' fill='#f2f2f2'>expected-depth RMSE: {metrics['geometry']['expected_depth_rmse_m']:.4f} m</text>"
        f"<text x='20' y='116' fill='#f2f2f2'>primitives: {metrics['representation']['primitive_count']}</text>"
        "<text x='20' y='146' fill='#f2f2f2'>rendering, view-conditioned depth, and surface claims remain separate</text>"
        "</svg>\n",
        encoding="utf-8",
    )


def _report(profile: str, metrics: dict[str, Any], summary: dict[str, Any]) -> str:
    return f"""# Splatfacto maintained reference ({profile})

## Rendering

Held-out target PSNR: {metrics['rendering']['target_psnr_db']:.3f} dB; host-recomputed SSIM: {metrics['rendering']['target_ssim']:.4f}; pinned-container LPIPS: {metrics['rendering']['target_lpips']:.4f}. The retained representation has {metrics['representation']['primitive_count']} explicit Gaussians and renders at a measured median {summary['render_benchmark']['median_fps']:.2f} FPS on the recorded hardware.

## Geometry diagnostic

Accumulation-qualified common-visible expected-depth RMSE: {metrics['geometry']['expected_depth_rmse_m']:.5f} m; point F-score at 10 cm: {metrics['geometry']['point_fscore_10cm']:.4f}. Expected depth is an alpha-compositing statistic, not a first surface intersection.

## Unsupported claims

Vanilla Splatfacto defines neither a canonical triangle mesh nor hidden-surface completion. SuGaR/2DGS extraction and generative scene sampling require separate adapters. The trained 3/5/9-view sweep is retained as sparse-view failure evidence; no target metric selected a checkpoint or hyperparameter.
"""


def _entrypoint_command(profile: str) -> list[str]:
    return [
        "/usr/bin/time",
        "-v",
        "-o",
        "/output/resource-usage.txt",
        "python",
        "/usr/local/bin/run-splatfacto.py",
        "--input",
        "/input",
        "--output",
        "/output",
        "--iterations",
        str(PROFILE_CONFIG[profile]["iterations"]),
    ]


def _container_command(
    engine: str,
    image_id: str,
    staging: Path,
    cuda_cache: Path,
    lpips_checkpoint: Path,
    profile: str,
    gpu_device: str,
) -> list[str]:
    return [
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
        "-e",
        f"PYTHONHASHSEED={DETERMINISTIC_ENVIRONMENT['PYTHONHASHSEED']}",
        "-e",
        f"CUBLAS_WORKSPACE_CONFIG={DETERMINISTIC_ENVIRONMENT['CUBLAS_WORKSPACE_CONFIG']}",
        "-e",
        f"NVIDIA_TF32_OVERRIDE={DETERMINISTIC_ENVIRONMENT['NVIDIA_TF32_OVERRIDE']}",
        "--cidfile",
        str(staging / "container.cid"),
        "-e",
        "CUDA_CACHE_PATH=/cuda-cache",
        "-e",
        "MPLCONFIGDIR=/cuda-cache/matplotlib",
        "-e",
        "TORCH_EXTENSIONS_DIR=/cuda-cache/torch-extensions",
        "-e",
        "TRITON_CACHE_DIR=/cuda-cache/triton",
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
        "module_ids": ["11"],
        "image": IMAGE,
        "image_id": tool["container_image_id"],
        "scene_contract_sha256": sha256_file(ROOT / "shared-scene.json"),
        "input_manifest_sha256": sha256_file(run_dir / "input/manifest.json"),
        "source_commit": PINNED_NERFSTUDIO_COMMIT,
        "dependency_commit": PINNED_GSPLAT_COMMIT,
        "requirements_lock_sha256": REQUIREMENTS_LOCK_SHA256,
        "resolved_requirements_sha256": load_json(ROOT / "insulas/locks.json")[
            "insulas"
        ]["gaussian-splatting"]["resolved_requirements_sha256"],
        **PROFILE_CONFIG[profile],
        "seed": SEED,
        "random_init": True,
        "num_random": 50000,
        "random_scale": 2.0,
        "camera_optimizer": "off",
        "background_color": "black",
        "scale_regularization": False,
        "rasterization_mode": "classic",
        "tf32": False,
        "trained_view_sweep": {"context_views": [3, 5, 9], "iterations": 1000},
        "container_user_environment": DETERMINISTIC_ENVIRONMENT,
        "support": SUPPORT_CONTRACT,
        "cuda_cache": "persistent-cache-root-mount",
        "lpips_backbone": _lpips_checkpoint_record(),
        "adapter_execution_contract_sha256": _adapter_execution_contract_sha256(),
        "entrypoint_command": _entrypoint_command(profile),
        "evaluation_software": {
            "python": platform.python_version(),
            "numpy": np.__version__,
        },
        "acceptance": acceptance,
    }


def validate_splatfacto_reference_result(run_dir: Path) -> dict[str, Any]:
    result = load_json(_require_regular_file(run_dir, "result.json"))
    validate_json_schema_instance(
        result,
        load_json(ROOT / "reference-result.schema.json"),
        "Splatfacto reference result",
    )
    if (
        result.get("adapter") != ADAPTER
        or result.get("module_ids") != ["11"]
        or result.get("status") != "complete"
        or result.get("network_mode") != "offline"
        or result.get("support") != SUPPORT_CONTRACT
    ):
        raise ValueError("Splatfacto result identity mismatch")
    profile = result.get("profile")
    if profile not in PROFILE_CONFIG:
        raise ValueError("Splatfacto result profile mismatch")
    _validate_runtime_identity(run_dir, profile)
    _validated_resources(run_dir, result)
    metrics = _evaluate_outputs(run_dir, profile)
    if not _values_match(result.get("metrics"), metrics):
        raise ValueError("Splatfacto persisted metric recomputation mismatch")
    acceptance = _adapter_record()["acceptance"][profile]
    if result.get("acceptance") != acceptance:
        raise ValueError("Splatfacto acceptance binding mismatch")
    failures = _acceptance_failures(metrics, acceptance)
    if failures:
        raise ValueError(f"Splatfacto output is below locked acceptance: {failures}")
    tool = result.get("tool", {})
    if (
        tool.get("source_commit") != PINNED_NERFSTUDIO_COMMIT
        or tool.get("dependency_commit") != PINNED_GSPLAT_COMMIT
        or tool.get("container_image") != IMAGE
        or tool.get("container_image_id") != _approved_image_id()
    ):
        raise ValueError("Splatfacto tool identity mismatch")
    config = result["provenance"]["config"]
    if config != _expected_config(run_dir, result, profile, acceptance):
        raise ValueError("Splatfacto config identity binding mismatch")
    if hashlib.sha256(canonical_json(config)).hexdigest() != result["provenance"]["config_sha256"]:
        raise ValueError("Splatfacto config hash mismatch")
    implementation = {name: sha256_file(ROOT / name) for name in REFERENCE_IMPLEMENTATION}
    if result["provenance"].get("implementation_sha256") != implementation:
        raise ValueError("Splatfacto implementation identity mismatch")
    if result["provenance"].get("artifacts_sha256") != _hash_tree(run_dir):
        raise ValueError("Splatfacto artifact hash mismatch")
    return result


def run_splatfacto_reference(cache_root: Path, profile: str, run_id: str) -> Path:
    validate_run_id(run_id)
    if profile not in PROFILE_CONFIG:
        raise ValueError(f"unknown profile: {profile}")
    engine = os.environ.get("SURFLO_PATHWAY_CONTAINER_ENGINE", "docker")
    image_id = _inspect_image(engine, IMAGE)
    if image_id != _approved_image_id():
        raise ValueError(
            f"Splatfacto image {image_id} is not the approved calibration image "
            f"{_approved_image_id()}"
        )
    gpu_hardware = _gpu_hardware(engine)
    if Path(engine).name == "docker" and not gpu_hardware:
        raise ValueError("unable to inventory GPU hardware for the real Splatfacto reference")
    gpu_device = selected_gpu_device(require_health=Path(engine).name == "docker")
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_root = cache_root.resolve(strict=True)
    checkpoint = _lpips_checkpoint_path(cache_root, _lpips_checkpoint_record())
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
            checkpoint,
            profile,
            gpu_device,
        )
        completed, peak_gpu = _run_monitored(command, staging / "container.cid")
        (staging / "adapter.log").write_text(
            completed.stdout + completed.stderr, encoding="utf-8"
        )
        if completed.returncode != 0:
            raise ValueError(
                f"Splatfacto adapter failed ({completed.returncode}): {completed.stderr.strip()}"
            )
        if Path(engine).name == "docker" and peak_gpu <= 0:
            raise ValueError("unable to measure compute memory for Splatfacto optimization")
        summary = _validate_runtime_identity(staging, profile)
        metrics = _evaluate_outputs(staging, profile)
        _write_visualization(staging, metrics)
        acceptance = _adapter_record()["acceptance"][profile]
        failures = _acceptance_failures(metrics, acceptance)
        if failures:
            raise ValueError(f"Splatfacto output is below locked acceptance: {failures}")
        (staging / "report.md").write_text(
            _report(profile, metrics, summary), encoding="utf-8"
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
            "training_seconds": summary["training_seconds"],
            "training_steps_per_second": summary["training_steps_per_second"],
            "render_median_fps": summary["render_benchmark"]["median_fps"],
            "render_p95_latency_ms": summary["render_benchmark"]["p95_latency_ms"],
        }
        write_json(staging / "output/resource-summary.json", resources)
        provisional = {
            "tool": {"container_image_id": image_id},
            "provenance": {"config": {"run_id": run_id}},
        }
        config = _expected_config(staging, provisional, profile, acceptance)
        result = {
            "schema_version": 1,
            "adapter": ADAPTER,
            "module_ids": ["11"],
            "profile": profile,
            "status": "complete",
            "network_mode": "offline",
            "metrics": metrics,
            "support": SUPPORT_CONTRACT,
            "acceptance": acceptance,
            "tool": {
                "name": "Nerfstudio Splatfacto with gsplat",
                "version": "splatfacto",
                "package_version": f"nerfstudio@{PINNED_NERFSTUDIO_COMMIT}+gsplat@{PINNED_GSPLAT_VERSION}",
                "source_commit": PINNED_NERFSTUDIO_COMMIT,
                "dependency_commit": PINNED_GSPLAT_COMMIT,
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
        ensure_finite(result, "Splatfacto reference result")
        write_json(staging / "result.json", result)
        validate_splatfacto_reference_result(staging)
        os.replace(promotion, final_parent)
        return final
    except BaseException:
        shutil.rmtree(promotion, ignore_errors=True)
        raise
