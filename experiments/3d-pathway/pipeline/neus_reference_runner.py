"""Offline Nerfstudio NeuS-Facto maintained-reference execution for module 09."""

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
    selected_gpu_device,
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
    _validated_resource_summary,
)
from reference_scene import generate_implicit_surface_scene


ADAPTER = "neus-facto"
IMAGE = "surflo-pathway-implicit-surface:1"
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
    "kind": "implicit-surface",
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
    "geometry_score_domain": "surface truth visible from at least two context cameras",
    "unsupported_domain": "surface truth visible from zero context cameras",
    "render_score_domain": "held-out target images with depth restricted to common-visible truth",
    "completion_claim": "none",
    "posterior_sampling_claim": "none",
    "complete_scene_samples": 0,
}
PROFILE_CONFIG = {
    "smoke": {"iterations": 1000, "rays_per_batch": 1024, "extraction_resolution": 128},
    "full": {"iterations": 20001, "rays_per_batch": 2048, "extraction_resolution": 256},
}
REFERENCE_IMPLEMENTATION = (
    "pipeline/cli.py",
    "pipeline/contracts.py",
    "pipeline/reference_runner.py",
    "pipeline/mvs_reference_runner.py",
    "pipeline/neus_reference_runner.py",
    "pipeline/reference_scene.py",
    "insulas/build.sh",
    "insulas/implicit-surface/Dockerfile",
    "insulas/implicit-surface/run-neus-facto.py",
    "insulas/locks.json",
    "assets.lock.json",
    "reference-result.schema.json",
    "shared-scene.json",
)


def _values_match(actual: Any, expected: Any) -> bool:
    """Compare recomputed data with tolerance only for floating-point leaves."""
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
        return type(actual) is float and math.isclose(
            actual, expected, rel_tol=1e-6, abs_tol=1e-8
        )
    return type(actual) is type(expected) and actual == expected


def _finite_xyz(values: np.ndarray, label: str) -> np.ndarray:
    result = np.asarray(values, dtype=np.float64)
    if result.ndim != 2 or result.shape[1] != 3 or len(result) == 0:
        raise ValueError(f"{label} must be a nonempty Nx3 array")
    if not np.isfinite(result).all():
        raise ValueError(f"{label} must be finite")
    return result


def _nearest(query: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    target_norm = np.sum(target * target, axis=1)
    distances = np.empty(len(query), dtype=np.float64)
    indices = np.empty(len(query), dtype=np.int64)
    for start in range(0, len(query), 256):
        batch = query[start : start + 256]
        squared = (
            np.sum(batch * batch, axis=1, keepdims=True)
            + target_norm
            - 2.0 * batch @ target.T
        )
        nearest = np.argmin(squared, axis=1)
        distances[start : start + len(batch)] = np.sqrt(
            np.maximum(squared[np.arange(len(batch)), nearest], 0.0)
        )
        indices[start : start + len(batch)] = nearest
    return distances, indices


def _surface_metrics(
    predicted_points: np.ndarray,
    predicted_normals: np.ndarray,
    truth_points: np.ndarray,
    truth_normals: np.ndarray,
    truth_support: np.ndarray,
) -> dict[str, float | int]:
    predicted_points = _finite_xyz(predicted_points, "predicted points")
    predicted_normals = _finite_xyz(predicted_normals, "predicted normals")
    truth_points = _finite_xyz(truth_points, "truth points")
    truth_normals = _finite_xyz(truth_normals, "truth normals")
    support = np.asarray(truth_support)
    if predicted_normals.shape != predicted_points.shape:
        raise ValueError("predicted point and normal shapes differ")
    if truth_normals.shape != truth_points.shape or support.shape != (len(truth_points),):
        raise ValueError("truth point, normal, and support shapes differ")
    if not np.issubdtype(support.dtype, np.integer) or np.any(support < 0):
        raise ValueError("truth support must contain non-negative integers")

    predicted_normal_norm = np.linalg.norm(predicted_normals, axis=1)
    truth_normal_norm = np.linalg.norm(truth_normals, axis=1)
    if np.any(predicted_normal_norm <= 0.0) or np.any(truth_normal_norm <= 0.0):
        raise ValueError("surface normals must have positive norm")
    predicted_unit = predicted_normals / predicted_normal_norm[:, None]
    truth_unit = truth_normals / truth_normal_norm[:, None]

    predicted_to_truth, predicted_nearest = _nearest(predicted_points, truth_points)
    truth_to_predicted, truth_nearest = _nearest(truth_points, predicted_points)
    predicted_common = support[predicted_nearest] >= 2
    predicted_unsupported = support[predicted_nearest] == 0
    truth_common = support >= 2
    truth_unsupported = support == 0
    if not np.any(predicted_common) or not np.any(truth_common):
        raise ValueError("surface evaluation has no common-visible support")

    accuracy = predicted_to_truth[predicted_common]
    completeness = truth_to_predicted[truth_common]
    normal_cosine = np.sum(
        predicted_unit[predicted_common]
        * truth_unit[predicted_nearest[predicted_common]],
        axis=1,
    )
    normal_angles = np.degrees(np.arccos(np.clip(normal_cosine, -1.0, 1.0)))
    metrics: dict[str, float | int] = {
        "mesh_vertices": int(len(predicted_points)),
        "common_visible_truth_points": int(np.count_nonzero(truth_common)),
        "unsupported_truth_points": int(np.count_nonzero(truth_unsupported)),
        "common_visible_predicted_points": int(np.count_nonzero(predicted_common)),
        "unsupported_predicted_points": int(np.count_nonzero(predicted_unsupported)),
        "common_visible_accuracy_rmse_m": float(np.sqrt(np.mean(accuracy * accuracy))),
        "common_visible_completeness_rmse_m": float(
            np.sqrt(np.mean(completeness * completeness))
        ),
        "common_visible_accuracy_mean_m": float(np.mean(accuracy)),
        "common_visible_completeness_mean_m": float(np.mean(completeness)),
        "common_visible_normal_mean_deg": float(np.mean(normal_angles)),
        "common_visible_normal_median_deg": float(np.median(normal_angles)),
    }
    for threshold_cm in (2, 5, 10):
        threshold = threshold_cm / 100.0
        precision = float(np.mean(accuracy <= threshold))
        recall = float(np.mean(completeness <= threshold))
        fscore = 0.0 if precision + recall == 0.0 else 2.0 * precision * recall / (precision + recall)
        metrics[f"common_visible_precision_{threshold_cm}cm"] = precision
        metrics[f"common_visible_recall_{threshold_cm}cm"] = recall
        metrics[f"common_visible_fscore_{threshold_cm}cm"] = fscore
    metrics["common_visible_completeness_fraction"] = metrics[
        "common_visible_recall_10cm"
    ]
    if np.any(predicted_unsupported):
        unsupported_truth = truth_points[truth_unsupported]
        unsupported_distances, _ = _nearest(
            predicted_points[predicted_unsupported], unsupported_truth
        )
        metrics["unsupported_accuracy_mean_m"] = float(np.mean(unsupported_distances))
    else:
        metrics["unsupported_accuracy_mean_m"] = 0.0
    if np.any(truth_unsupported):
        metrics["unsupported_completeness_mean_m"] = float(
            np.mean(truth_to_predicted[truth_unsupported])
        )
    else:
        metrics["unsupported_completeness_mean_m"] = 0.0
    if not all(math.isfinite(float(value)) for value in metrics.values()):
        raise ValueError("surface metrics are non-finite")
    return metrics


def _render_metrics(
    predicted_rgb: np.ndarray,
    truth_rgb: np.ndarray,
    predicted_depth: np.ndarray,
    truth_depth: np.ndarray,
    common_visible_mask: np.ndarray,
) -> dict[str, float | int]:
    predicted_rgb = np.asarray(predicted_rgb)
    truth_rgb = np.asarray(truth_rgb)
    predicted_depth = np.asarray(predicted_depth)
    truth_depth = np.asarray(truth_depth)
    mask = np.asarray(common_visible_mask, dtype=bool)
    if (
        predicted_rgb.shape != truth_rgb.shape
        or predicted_rgb.ndim != 3
        or predicted_rgb.shape[2] != 3
        or predicted_depth.shape != truth_depth.shape
        or predicted_depth.shape != mask.shape
        or predicted_rgb.shape[:2] != mask.shape
    ):
        raise ValueError("render metric inputs have incompatible shapes")
    if not np.isfinite(predicted_rgb).all() or not np.isfinite(truth_rgb).all():
        raise ValueError("RGB render inputs must be finite")
    if not np.any(mask):
        raise ValueError("render evaluation has no common-visible RGB pixels")
    rgb_residual = (
        predicted_rgb.astype(np.float64)[mask] - truth_rgb.astype(np.float64)[mask]
    )
    mse = float(np.mean(rgb_residual * rgb_residual))
    psnr = float("inf") if mse == 0.0 else float(10.0 * math.log10(255.0 * 255.0 / mse))
    depth_mask = (
        mask
        & np.isfinite(predicted_depth)
        & np.isfinite(truth_depth)
        & (predicted_depth > 0.0)
        & (truth_depth > 0.0)
    )
    if not np.any(depth_mask):
        raise ValueError("render evaluation has no common-visible depth pixels")
    depth_residual = predicted_depth[depth_mask].astype(np.float64) - truth_depth[
        depth_mask
    ].astype(np.float64)
    return {
        "target_psnr_db": psnr,
        "target_rgb_score_domain": "common-visible-truth-pixels",
        "target_common_visible_depth_rmse_m": float(
            np.sqrt(np.mean(depth_residual * depth_residual))
        ),
        "target_common_visible_depth_abs_rel": float(
            np.mean(np.abs(depth_residual) / truth_depth[depth_mask])
        ),
        "target_common_visible_pixels": int(np.count_nonzero(depth_mask)),
    }


def _eikonal_metrics(gradient_norms: np.ndarray) -> dict[str, float]:
    values = np.asarray(gradient_norms, dtype=np.float64).reshape(-1)
    if len(values) == 0 or not np.isfinite(values).all() or np.any(values <= 0.0):
        raise ValueError("eikonal gradient norms must be finite positive values")
    residual = np.abs(values - 1.0)
    return {
        "eikonal_mean": float(np.mean(residual)),
        "eikonal_p95": float(np.quantile(residual, 0.95)),
        "eikonal_max": float(np.max(residual)),
    }


def _adapter_record() -> dict[str, Any]:
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
            "acceptance",
            "model_contract",
            "evaluation_contract",
        )
    }
    return hashlib.sha256(canonical_json(contract)).hexdigest()


def _lpips_checkpoint_record() -> dict[str, Any]:
    matches = [
        item
        for item in load_json(ROOT / "assets.lock.json")["assets"]
        if item.get("id") == LPIPS_CHECKPOINT_ID
    ]
    if len(matches) != 1:
        raise ValueError("NeuS-Facto LPIPS checkpoint asset registry mismatch")
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
        raise ValueError("NeuS-Facto LPIPS checkpoint lock mismatch")
    return record


def _lpips_checkpoint_path(cache_root: Path, record: dict[str, Any]) -> Path:
    path = cache_root / "assets" / f"{LPIPS_CHECKPOINT_ID}.archive"
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as error:
        raise FileNotFoundError(
            f"missing NeuS-Facto LPIPS checkpoint: {path}; "
            f"run `run.sh fetch --asset {LPIPS_CHECKPOINT_ID}`"
        ) from error
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise ValueError("NeuS-Facto LPIPS checkpoint must be a regular non-symlink file")
    if path.stat().st_size != record["byte_size"]:
        raise ValueError("NeuS-Facto LPIPS checkpoint byte-size mismatch")
    if sha256_file(path) != record["sha256"]:
        raise ValueError("NeuS-Facto LPIPS checkpoint hash mismatch")
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(cache_root.resolve(strict=True))
    except ValueError as error:
        raise ValueError("NeuS-Facto LPIPS checkpoint escapes the cache root") from error
    return resolved


def _regular_npy(path: Path, label: str) -> np.ndarray:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as error:
        raise ValueError(f"missing NeuS-Facto {label}: {path.name}") from error
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise ValueError(f"NeuS-Facto {label} is not a regular file: {path.name}")
    try:
        return np.load(path, allow_pickle=False)
    except (OSError, ValueError) as error:
        raise ValueError(f"malformed NeuS-Facto {label}: {path.name}") from error


def _validate_input_manifest(input_root: Path, profile: str) -> dict[str, Any]:
    manifest = load_json(_require_regular_file(input_root.parent, "input/manifest.json"))
    with tempfile.TemporaryDirectory(prefix="surflo-neus-manifest-") as temporary:
        expected_root = Path(temporary) / "input"
        expected = generate_implicit_surface_scene(
            expected_root, load_json(ROOT / "shared-scene.json"), profile
        )
        if manifest != expected:
            raise ValueError("NeuS-Facto input manifest does not match the shared-scene contract")
        metadata_relative = expected["sdfstudio_metadata_path"]
        metadata_hash = expected["sdfstudio_metadata_sha256"]
        metadata_actual = _require_regular_file(input_root, metadata_relative)
        if (
            sha256_file(metadata_actual) != metadata_hash
            or sha256_file(expected_root / metadata_relative) != metadata_hash
        ):
            raise ValueError(
                f"NeuS-Facto input hash mismatch: {metadata_relative}"
            )
        try:
            metadata_actual.resolve(strict=True).relative_to(input_root.resolve(strict=True))
        except ValueError as error:
            raise ValueError(
                f"NeuS-Facto input escapes input root: {metadata_relative}"
            ) from error
        records = expected["context_frames"] + expected["target_frames"]
        pairs = [
            ("image_path", "image_sha256"),
            ("mask_path", "mask_sha256"),
            ("depth_path", "depth_sha256"),
            ("normal_path", "normal_sha256"),
            ("rgb_truth_path", "rgb_truth_sha256"),
            ("common_visible_mask_path", "common_visible_mask_sha256"),
        ]
        truth = expected["surface_truth"]
        records_with_pairs: list[tuple[dict[str, Any], list[tuple[str, str]]]] = [
            (record, pairs) for record in records
        ] + [
            (
                truth,
                [
                    ("points_path", "points_sha256"),
                    ("normals_path", "normals_sha256"),
                    ("support_path", "support_sha256"),
                ],
            )
        ]
        for record, record_pairs in records_with_pairs:
            for path_key, hash_key in record_pairs:
                relative = record[path_key]
                actual = input_root / relative
                expected_path = expected_root / relative
                if (
                    sha256_file(_require_regular_file(input_root, relative)) != record[hash_key]
                    or sha256_file(expected_path) != record[hash_key]
                ):
                    raise ValueError(f"NeuS-Facto input hash mismatch: {relative}")
                try:
                    actual.resolve(strict=True).relative_to(input_root.resolve(strict=True))
                except ValueError as error:
                    raise ValueError(f"NeuS-Facto input escapes input root: {relative}") from error
    return manifest


def _mesh_output(run_dir: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    path = _require_regular_file(run_dir, "output/mesh.npz")
    try:
        with np.load(path, allow_pickle=False) as archive:
            if set(archive.files) != {"points", "normals", "faces"}:
                raise ValueError("mesh archive inventory mismatch")
            points = archive["points"]
            normals = archive["normals"]
            faces = archive["faces"]
    except (OSError, ValueError) as error:
        raise ValueError("malformed NeuS-Facto mesh archive") from error
    points = _finite_xyz(points, "mesh points")
    normals = _finite_xyz(normals, "mesh normals")
    if normals.shape != points.shape:
        raise ValueError("mesh point and normal shapes differ")
    if faces.ndim != 2 or faces.shape[1] != 3 or len(faces) == 0 or not np.issubdtype(faces.dtype, np.integer):
        raise ValueError("mesh faces must be a nonempty integer Mx3 array")
    if np.any(faces < 0) or np.any(faces >= len(points)) or np.any(
        (faces[:, 0] == faces[:, 1]) | (faces[:, 1] == faces[:, 2]) | (faces[:, 0] == faces[:, 2])
    ):
        raise ValueError("mesh contains invalid faces")
    _require_regular_file(run_dir, "output/mesh.ply")
    return points, normals, faces.astype(np.int64)


def _evaluate_outputs(run_dir: Path, profile: str) -> tuple[dict[str, Any], dict[str, int]]:
    manifest = _validate_input_manifest(run_dir / "input", profile)
    points, normals, faces = _mesh_output(run_dir)
    truth = manifest["surface_truth"]
    truth_points = _regular_npy(run_dir / "input" / truth["points_path"], "truth points")
    truth_normals = _regular_npy(run_dir / "input" / truth["normals_path"], "truth normals")
    truth_support = _regular_npy(run_dir / "input" / truth["support_path"], "truth support")
    surface = _surface_metrics(points, normals, truth_points, truth_normals, truth_support)

    predicted_rgbs: list[np.ndarray] = []
    truth_rgbs: list[np.ndarray] = []
    predicted_depths: list[np.ndarray] = []
    truth_depths: list[np.ndarray] = []
    support_masks: list[np.ndarray] = []
    for frame in manifest["target_frames"]:
        predicted_rgbs.append(
            _regular_npy(
                run_dir / "output/target-renders" / f"{frame['id']}.rgb.npy",
                "target RGB",
            )
        )
        predicted_depths.append(
            _regular_npy(
                run_dir / "output/target-renders" / f"{frame['id']}.depth.npy",
                "target depth",
            )
        )
        _regular_npy(
            run_dir / "output/target-renders" / f"{frame['id']}.normal.npy",
            "target normal",
        )
        truth_rgbs.append(_regular_npy(run_dir / "input" / frame["rgb_truth_path"], "truth RGB"))
        truth_depths.append(_regular_npy(run_dir / "input" / frame["depth_path"], "truth depth"))
        support_masks.append(
            _regular_npy(
                run_dir / "input" / frame["common_visible_mask_path"], "target support"
            ).astype(bool)
        )
    rendering = _render_metrics(
        np.concatenate(predicted_rgbs, axis=0),
        np.concatenate(truth_rgbs, axis=0),
        np.concatenate(predicted_depths, axis=0),
        np.concatenate(truth_depths, axis=0),
        np.concatenate(support_masks, axis=0),
    )
    profile_config = PROFILE_CONFIG[profile]
    sdf_grid = _regular_npy(run_dir / "output/field.sdf_grid.float32.npy", "SDF grid")
    if sdf_grid.dtype != np.float32 or sdf_grid.shape != (
        profile_config["extraction_resolution"],
    ) * 3 or not np.isfinite(sdf_grid).all():
        raise ValueError("NeuS-Facto SDF grid shape, dtype, or values mismatch")
    gradient_norms = _regular_npy(
        run_dir / "output/field.gradient_norms.float32.npy", "field gradient norms"
    )
    if gradient_norms.dtype != np.float32:
        raise ValueError("NeuS-Facto gradient norms must be float32")
    field = _eikonal_metrics(gradient_norms)
    geometry_keys = {
        key: value
        for key, value in surface.items()
        if key.startswith("common_visible_")
    }
    unsupported = {
        "truth_points": int(surface["unsupported_truth_points"]),
        "predicted_points": int(surface["unsupported_predicted_points"]),
        "accuracy_mean_m": float(surface["unsupported_accuracy_mean_m"]),
        "completeness_mean_m": float(surface["unsupported_completeness_mean_m"]),
        "completion_claim": "none",
    }
    topology = {"mesh_vertices": int(len(points)), "mesh_faces": int(len(faces))}
    metrics = {
        "geometry": geometry_keys,
        "rendering": rendering,
        "field": field,
        "unsupported": unsupported,
    }
    ensure_finite(
        {"geometry": geometry_keys, "rendering": rendering, "field": field},
        "NeuS-Facto scored metrics",
    )
    return metrics, topology


def _validate_runtime_identity(run_dir: Path, profile: str) -> dict[str, Any]:
    if _require_regular_file(run_dir, "output/source-commit.txt").read_text().strip() != PINNED_NERFSTUDIO_COMMIT:
        raise ValueError("Nerfstudio source commit mismatch")
    if _require_regular_file(run_dir, "output/tcnn-commit.txt").read_text().strip() != PINNED_TCNN_COMMIT:
        raise ValueError("tiny-cuda-nn source commit mismatch")
    manifest = _parse_key_value_manifest(
        _require_regular_file(run_dir, "output/insula-manifest.txt")
    )
    if manifest != PINNED_INSULA_MANIFEST:
        raise ValueError("implicit-surface Insula manifest mismatch")
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
        raise ValueError("NeuS-Facto runtime identity mismatch")
    gates = load_json(_require_regular_file(run_dir, "output/environment-gates.json"))
    required_gates = {
        "compute_capability_10_0",
        "tcnn_forward_backward",
        "neus_facto_forward_backward",
        "sdf_extraction_32",
    }
    if gates.keys() != required_gates or not all(gates.values()):
        raise ValueError("NeuS-Facto environment gate failed")
    summary = load_json(_require_regular_file(run_dir, "output/training-summary.json"))
    expected = PROFILE_CONFIG[profile]
    if (
        summary.get("method") != "neus-facto"
        or summary.get("iterations") != expected["iterations"]
        or summary.get("rays_per_batch") != expected["rays_per_batch"]
        or summary.get("extraction_resolution") != expected["extraction_resolution"]
        or summary.get("camera_optimizer") != "off"
        or summary.get("mono_prior") is not False
        or summary.get("inside_outside") is not True
        or summary.get("tf32") is not False
        or summary.get("seed") != 260925
        or not isinstance(summary.get("training_seconds"), (int, float))
        or summary["training_seconds"] <= 0
        or not isinstance(summary.get("training_steps_per_second"), (int, float))
        or not math.isclose(
            summary["training_steps_per_second"],
            expected["iterations"] / summary["training_seconds"],
            rel_tol=1e-9,
            abs_tol=1e-12,
        )
        or not isinstance(summary.get("extraction_seconds"), (int, float))
        or summary["extraction_seconds"] < 0
    ):
        raise ValueError("NeuS-Facto training identity mismatch")
    _require_regular_file(run_dir, "output/nerfstudio/checkpoint.ckpt")
    _require_regular_file(run_dir, "output/failure_sweep.csv")
    return summary


def _acceptance_failures(
    metrics: dict[str, Any], topology: dict[str, int], acceptance: dict[str, Any]
) -> list[str]:
    values = {
        **topology,
        **metrics["geometry"],
        **metrics["rendering"],
        **metrics["field"],
    }
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
            raise ValueError(f"unsupported NeuS-Facto acceptance key: {key}")
    return failures


def _write_visualizations(run_dir: Path, metrics: dict[str, Any]) -> None:
    artifacts = run_dir / "artifacts"
    artifacts.mkdir()
    geometry = metrics["geometry"]
    (artifacts / "metric-summary.svg").write_text(
        "<svg xmlns='http://www.w3.org/2000/svg' width='640' height='120'>"
        "<rect width='640' height='120' fill='#101820'/>"
        f"<text x='20' y='55' fill='#f2f2f2'>common-visible F@10cm: {geometry['common_visible_fscore_10cm']:.4f}</text>"
        f"<text x='20' y='85' fill='#f2f2f2'>unsupported truth: {metrics['unsupported']['truth_points']} samples (not scored as completion)</text>"
        "</svg>\n",
        encoding="utf-8",
    )
    (artifacts / "sdf-slice.svg").write_text(
        "<svg xmlns='http://www.w3.org/2000/svg' width='320' height='320'>"
        "<rect width='320' height='320' fill='#17242d'/><circle cx='160' cy='160' r='112' fill='none' stroke='#51d0b1' stroke-width='3'/>"
        "<text x='58' y='302' fill='#f2f2f2'>zero-level slice (schematic)</text></svg>\n",
        encoding="utf-8",
    )


def _report(profile: str, metrics: dict[str, Any], topology: dict[str, int]) -> str:
    geometry, rendering, field, unsupported = (
        metrics["geometry"],
        metrics["rendering"],
        metrics["field"],
        metrics["unsupported"],
    )
    return f"""# NeuS-Facto maintained reference ({profile})

## Geometry

Common-visible F-score at 10 cm: {geometry['common_visible_fscore_10cm']:.4f}; accuracy RMSE: {geometry['common_visible_accuracy_rmse_m']:.5f} m; mesh: {topology['mesh_vertices']} vertices / {topology['mesh_faces']} faces.

## Rendering

Held-out target PSNR: {rendering['target_psnr_db']:.3f} dB. This image metric is reported separately from surface geometry.

## Field

Mean Eikonal residual: {field['eikonal_mean']:.5f}. This is a field regularity diagnostic, not surface accuracy.

## Unsupported region

The back side contains {unsupported['truth_points']} zero-context-support truth samples. Its output is regularizer-dependent and is not a completion or posterior-sampling claim.
"""


def _entrypoint_command(profile: str) -> list[str]:
    config = PROFILE_CONFIG[profile]
    return [
        "/usr/bin/time",
        "-v",
        "-o",
        "/work/output/resource-usage.txt",
        "python",
        "/usr/local/bin/run-neus-facto.py",
        "--input",
        "/work/input",
        "--output",
        "/work/output",
        "--iterations",
        str(config["iterations"]),
        "--rays-per-batch",
        str(config["rays_per_batch"]),
        "--extraction-resolution",
        str(config["extraction_resolution"]),
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


def validate_neus_reference_result(run_dir: Path) -> dict[str, Any]:
    result = load_json(_require_regular_file(run_dir, "result.json"))
    validate_json_schema_instance(
        result, load_json(ROOT / "reference-result.schema.json"), "NeuS-Facto reference result"
    )
    if (
        result.get("adapter") != ADAPTER
        or result.get("module_ids") != ["09"]
        or result.get("status") != "complete"
        or result.get("network_mode") != "offline"
        or result.get("support") != SUPPORT_CONTRACT
    ):
        raise ValueError("NeuS-Facto result identity mismatch")
    profile = result.get("profile")
    if profile not in PROFILE_CONFIG:
        raise ValueError("NeuS-Facto result profile mismatch")
    summary = _validate_runtime_identity(run_dir, profile)
    _validated_resource_summary(
        run_dir,
        result,
        label="NeuS-Facto",
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
            "extraction_seconds",
            "training_seconds",
            "training_steps_per_second",
        },
        positive_keys=(
            "runtime_seconds",
            "peak_cpu_memory_bytes",
            "extraction_seconds",
            "training_seconds",
            "training_steps_per_second",
        ),
    )
    metrics, topology = _evaluate_outputs(run_dir, profile)
    if not _values_match(result.get("metrics"), metrics) or not _values_match(
        result.get("topology"), topology
    ):
        raise ValueError("NeuS-Facto persisted metric recomputation mismatch")
    acceptance = _adapter_record()["acceptance"][profile]
    if result.get("acceptance") != acceptance:
        raise ValueError("NeuS-Facto acceptance binding mismatch")
    failures = _acceptance_failures(metrics, topology, acceptance)
    if failures:
        raise ValueError(f"NeuS-Facto output is below the locked acceptance threshold: {failures}")
    tool = result.get("tool", {})
    if (
        tool.get("source_commit") != PINNED_NERFSTUDIO_COMMIT
        or tool.get("dependency_commit") != PINNED_TCNN_COMMIT
        or tool.get("container_image") != IMAGE
        or IMAGE_ID_PATTERN.fullmatch(str(tool.get("container_image_id", ""))) is None
    ):
        raise ValueError("NeuS-Facto tool identity mismatch")
    config = result["provenance"]["config"]
    expected_config = {
        "adapter": ADAPTER,
        "profile": profile,
        "run_id": result.get("provenance", {}).get("config", {}).get("run_id"),
        "module_ids": ["09"],
        "image": IMAGE,
        "image_id": tool["container_image_id"],
        "scene_contract_sha256": sha256_file(ROOT / "shared-scene.json"),
        "input_manifest_sha256": sha256_file(run_dir / "input/manifest.json"),
        "source_commit": PINNED_NERFSTUDIO_COMMIT,
        "dependency_commit": PINNED_TCNN_COMMIT,
        **PROFILE_CONFIG[profile],
        "seed": 260925,
        "camera_optimizer": "off",
        "mono_prior": False,
        "inside_outside": True,
        "tf32": False,
        "container_user_environment": {"USER": "surflo"},
        "support": SUPPORT_CONTRACT,
        "cuda_cache": CUDA_CACHE_POLICY,
        "lpips_backbone": _lpips_checkpoint_record(),
        "adapter_execution_contract_sha256": _adapter_execution_contract_sha256(),
        "entrypoint_command": _entrypoint_command(profile),
        "evaluation_software": {
            "python": platform.python_version(),
            "numpy": np.__version__,
        },
        "acceptance": acceptance,
    }
    if config != expected_config:
        raise ValueError("NeuS-Facto config identity binding mismatch")
    if hashlib.sha256(canonical_json(config)).hexdigest() != result["provenance"]["config_sha256"]:
        raise ValueError("NeuS-Facto config hash mismatch")
    implementation = {name: sha256_file(ROOT / name) for name in REFERENCE_IMPLEMENTATION}
    if result["provenance"].get("implementation_sha256") != implementation:
        raise ValueError("NeuS-Facto implementation identity mismatch")
    if result["provenance"].get("artifacts_sha256") != _hash_tree(run_dir):
        raise ValueError("NeuS-Facto artifact hash mismatch")
    if summary.get("mesh_vertices") != topology["mesh_vertices"] or summary.get("mesh_faces") != topology["mesh_faces"]:
        raise ValueError("NeuS-Facto training summary topology mismatch")
    return result


def run_neus_reference(cache_root: Path, profile: str, run_id: str) -> Path:
    validate_run_id(run_id)
    if profile not in PROFILE_CONFIG:
        raise ValueError(f"unknown profile: {profile}")
    engine = os.environ.get("SURFLO_PATHWAY_CONTAINER_ENGINE", "docker")
    image_id = _inspect_image(engine, IMAGE)
    gpu_hardware = _gpu_hardware(engine)
    if Path(engine).name == "docker" and not gpu_hardware:
        raise ValueError("unable to inventory GPU hardware for the real NeuS-Facto reference")
    gpu_device = selected_gpu_device(require_health=Path(engine).name == "docker")
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_root = cache_root.resolve(strict=True)
    lpips_checkpoint_record = _lpips_checkpoint_record()
    lpips_checkpoint = _lpips_checkpoint_path(cache_root, lpips_checkpoint_record)
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
        generate_implicit_surface_scene(
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
            gpu_device,
        )
        completed, peak_gpu = _run_monitored(command, staging / "container.cid")
        (staging / "adapter.log").write_text(
            completed.stdout + completed.stderr, encoding="utf-8"
        )
        if completed.returncode != 0:
            raise ValueError(
                f"NeuS-Facto adapter failed ({completed.returncode}): {completed.stderr.strip()}"
            )
        if Path(engine).name == "docker" and peak_gpu <= 0:
            raise ValueError("unable to measure compute memory for NeuS-Facto GPU optimization")
        summary = _validate_runtime_identity(staging, profile)
        metrics, topology = _evaluate_outputs(staging, profile)
        _write_visualizations(staging, metrics)
        acceptance = _adapter_record()["acceptance"][profile]
        failures = _acceptance_failures(metrics, topology, acceptance)
        if failures:
            raise ValueError(f"NeuS-Facto output is below the locked acceptance threshold: {failures}")
        (staging / "report.md").write_text(
            _report(profile, metrics, topology), encoding="utf-8"
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
            "extraction_seconds": summary["extraction_seconds"],
            "training_seconds": summary["training_seconds"],
            "training_steps_per_second": summary["training_steps_per_second"],
        }
        write_json(staging / "output/resource-summary.json", resources)
        config = {
            "adapter": ADAPTER,
            "profile": profile,
            "run_id": run_id,
            "module_ids": ["09"],
            "image": IMAGE,
            "image_id": image_id,
            "scene_contract_sha256": sha256_file(ROOT / "shared-scene.json"),
            "input_manifest_sha256": sha256_file(staging / "input/manifest.json"),
            "source_commit": PINNED_NERFSTUDIO_COMMIT,
            "dependency_commit": PINNED_TCNN_COMMIT,
            **PROFILE_CONFIG[profile],
            "seed": 260925,
            "camera_optimizer": "off",
            "mono_prior": False,
            "inside_outside": True,
            "tf32": False,
            "container_user_environment": {"USER": "surflo"},
            "support": SUPPORT_CONTRACT,
            "cuda_cache": CUDA_CACHE_POLICY,
            "lpips_backbone": lpips_checkpoint_record,
            "adapter_execution_contract_sha256": _adapter_execution_contract_sha256(),
            "entrypoint_command": _entrypoint_command(profile),
            "evaluation_software": {
                "python": platform.python_version(),
                "numpy": np.__version__,
            },
            "acceptance": acceptance,
        }
        result = {
            "schema_version": 1,
            "adapter": ADAPTER,
            "module_ids": ["09"],
            "profile": profile,
            "status": "complete",
            "network_mode": "offline",
            "metrics": metrics,
            "topology": topology,
            "support": SUPPORT_CONTRACT,
            "acceptance": acceptance,
            "tool": {
                "name": "Nerfstudio NeuS-Facto",
                "version": "neus-facto",
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
        ensure_finite(result, "NeuS-Facto reference result")
        write_json(staging / "result.json", result)
        validate_neus_reference_result(staging)
        final_parent.mkdir()
        os.replace(staging, final)
        return final
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
