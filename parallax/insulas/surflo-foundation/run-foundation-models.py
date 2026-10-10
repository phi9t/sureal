#!/usr/bin/env python3
"""Run exact local VGGT and DA3 checkpoints on RGB-only pathway evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time
from typing import Any


VGGT_METHOD = "vggt/direct"
DA3_METHOD = "da3-base/camera-head"
VGGT_SOURCE_COMMIT = "a288dd0f14786c93483e45524328726ab7b1b4ce"
DA3_SOURCE_COMMIT = "3d835ec1a5802d64a8b8b15f817a1ab54809bfe4"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--vggt-model", type=Path, required=True)
    parser.add_argument("--da3-model", type=Path, required=True)
    parser.add_argument("--vggt-source", type=Path, required=True)
    parser.add_argument("--da3-source", type=Path, required=True)
    parser.add_argument("--model-lock", type=Path, required=True)
    parser.add_argument("--environment-manifest", type=Path, required=True)
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unproject_depth(depth, intrinsics, extrinsics):
    import numpy as np

    depth = np.asarray(depth, dtype=np.float32)
    intrinsics = np.asarray(intrinsics, dtype=np.float32)
    extrinsics = np.asarray(extrinsics, dtype=np.float32)
    height, width = depth.shape[-2:]
    rows, columns = np.meshgrid(
        np.arange(height, dtype=np.float32),
        np.arange(width, dtype=np.float32),
        indexing="ij",
    )
    result = []
    for index in range(len(depth)):
        camera = np.stack(
            (
                (columns - intrinsics[index, 0, 2])
                * depth[index]
                / intrinsics[index, 0, 0],
                (rows - intrinsics[index, 1, 2])
                * depth[index]
                / intrinsics[index, 1, 1],
                depth[index],
            ),
            axis=-1,
        )
        rotation = extrinsics[index, :3, :3]
        translation = extrinsics[index, :3, 3]
        result.append((camera - translation) @ rotation)
    return np.asarray(result, dtype=np.float32)


def _upstream_unprojection_parity() -> dict[str, dict[str, float | str]]:
    """Execute both pinned upstream helpers against the canonical integer lattice."""
    import numpy as np
    import torch

    from depth_anything_3.utils.geometry import unproject_depth as da3_unproject_depth
    from vggt.utils.geometry import unproject_depth_map_to_point_map

    depth = np.full((1, 2, 3), 2.0, dtype=np.float32)
    intrinsics = np.asarray(
        [[[2.0, 0.0, 0.25], [0.0, 4.0, -0.5], [0.0, 0.0, 1.0]]],
        dtype=np.float32,
    )
    extrinsics = np.eye(4, dtype=np.float32)[None]
    extrinsics[0, :3, 3] = np.asarray([0.3, -0.2, 0.4], dtype=np.float32)
    canonical = _unproject_depth(depth, intrinsics, extrinsics)
    vggt = unproject_depth_map_to_point_map(
        depth[..., None], extrinsics[:, :3], intrinsics
    )
    c2w = np.linalg.inv(extrinsics)
    da3 = da3_unproject_depth(
        torch.from_numpy(depth[None, ..., None]),
        torch.from_numpy(intrinsics[None]),
        torch.from_numpy(c2w[None]),
    )[0].cpu().numpy()
    origin = "integer pixel centers (0,0) through (W-1,H-1)"
    return {
        VGGT_METHOD: {
            "helper": "vggt.utils.geometry.unproject_depth_map_to_point_map",
            "pixel_coordinate_origin": origin,
            "max_abs_error": float(np.max(np.abs(canonical - vggt))),
        },
        DA3_METHOD: {
            "helper": "depth_anything_3.utils.geometry.unproject_depth",
            "pixel_coordinate_origin": origin,
            "max_abs_error": float(np.max(np.abs(canonical - da3))),
        },
    }


def _validity(depth, points, confidence) -> dict[str, Any]:
    import numpy as np

    depth = np.asarray(depth)
    points = np.asarray(points)
    return {
        "total_pixels": int(depth.size),
        "finite_depth": int(np.count_nonzero(np.isfinite(depth))),
        "positive_depth": int(np.count_nonzero(np.isfinite(depth) & (depth > 0.0))),
        "finite_points": int(np.count_nonzero(np.isfinite(points).all(axis=-1))),
        "in_frame_points": int(np.prod(depth.shape)),
        "finite_confidence": int(np.count_nonzero(np.isfinite(confidence))),
        "confidence_threshold": None,
        "confidence_selected": int(np.size(confidence)),
        "sky_mask_status": "unsupported",
        "background_mask_status": "unsupported-model-side",
        "evaluation_mask_status": "evaluator-only; not mounted into inference container",
    }


def _checkpoint_contract(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "repository": record["repository"],
        "revision": record["revision"],
        "license": record["license"],
        "files": record["files"],
    }


def _input_contract(
    case: dict[str, Any],
    manifest: dict[str, Any],
    processed_size,
    *,
    geometric_transform: str,
    normalization: str,
) -> dict[str, Any]:
    return {
        "ordered_image_sha256": case["image_sha256"],
        "ordered_frame_ids": case["frame_ids"],
        "original_size_hw": manifest["original_size_hw"],
        "processed_size_hw": list(processed_size),
        "exif_orientation_action": "none; repository-generated RGB PNG",
        "reference_view_index_before_reorder": 0,
        "reference_view_index_after_reorder": 0,
        "final_order": "exactly the declared input order",
        "geometric_transform": geometric_transform,
        "normalization": normalization,
    }


def _track_contract(
    case: dict[str, Any],
    processed_size,
    queries,
    tracks,
    visibility,
    confidence,
) -> dict[str, Any]:
    arrays = {
        "track_queries": (queries, "reference-frame query xy coordinates"),
        "tracks": (tracks, "predicted xy coordinates for every frame and query"),
        "track_visibility": (visibility, "per-frame visibility scores"),
        "track_confidence": (confidence, "per-frame track confidence scores"),
    }
    return {
        "status": "measured",
        "query_frame": {"index": 0, "frame_id": case["frame_ids"][0]},
        "coordinate_convention": {
            "order": "xy",
            "space": "processed input image pixels",
            "origin": "(0,0) is the center of the upper-left pixel",
            "pixel_center_lattice": "integer centers 0..W-1 and 0..H-1",
        },
        "resolution_hw": [int(processed_size[0]), int(processed_size[1])],
        "arrays": {
            name: {
                "archive_member": name,
                "shape": list(value.shape),
                "dtype": str(value.dtype),
                "semantics": semantics,
            }
            for name, (value, semantics) in arrays.items()
        },
        "visibility": {
            "domain": "sigmoid score in [0,1]",
            "threshold": None,
            "semantics": "model estimate that the query is visible in each frame",
        },
        "confidence": {
            "domain": "sigmoid score in [0,1]",
            "threshold": None,
            "semantics": "model confidence in each predicted track coordinate",
        },
    }


def _canonical_extrinsics(extrinsics):
    import numpy as np

    extrinsics = np.asarray(extrinsics, dtype=np.float32)
    if extrinsics.ndim != 3 or extrinsics.shape[-2:] not in {(3, 4), (4, 4)}:
        raise ValueError(f"unexpected world-to-camera shape: {extrinsics.shape}")
    if extrinsics.shape[-2:] == (3, 4):
        result = np.broadcast_to(np.eye(4, dtype=np.float32), (len(extrinsics), 4, 4)).copy()
        result[:, :3, :] = extrinsics
        return result
    return extrinsics


def _geometry_checks(depth, points, extrinsics, intrinsics) -> dict[str, float]:
    import numpy as np

    depth = np.asarray(depth, dtype=np.float64)
    points = np.asarray(points, dtype=np.float64)
    extrinsics = np.asarray(extrinsics, dtype=np.float64)
    intrinsics = np.asarray(intrinsics, dtype=np.float64)
    if depth.ndim != 3 or points.shape != (*depth.shape, 3):
        raise ValueError("depth and pointmap shapes disagree")
    height, width = depth.shape[-2:]
    rows, columns = np.meshgrid(
        np.arange(height, dtype=np.float64),
        np.arange(width, dtype=np.float64),
        indexing="ij",
    )
    maximum_pixel_error = 0.0
    maximum_depth_error = 0.0
    for index in range(len(depth)):
        camera = points[index] @ extrinsics[index, :3, :3].T + extrinsics[index, :3, 3]
        positive = camera[..., 2] > 0.0
        projected_x = intrinsics[index, 0, 0] * camera[..., 0] / camera[..., 2] + intrinsics[index, 0, 2]
        projected_y = intrinsics[index, 1, 1] * camera[..., 1] / camera[..., 2] + intrinsics[index, 1, 2]
        maximum_pixel_error = max(
            maximum_pixel_error,
            float(np.max(np.abs(projected_x[positive] - columns[positive]))),
            float(np.max(np.abs(projected_y[positive] - rows[positive]))),
        )
        maximum_depth_error = max(
            maximum_depth_error,
            float(np.max(np.abs(camera[..., 2][positive] - depth[index][positive]))),
        )
    return {
        "depth_point_z_max_error": maximum_depth_error,
        "depth_point_reprojection_max_px": maximum_pixel_error,
    }


def _direct_point_checks(points, extrinsics, intrinsics) -> dict[str, float | int]:
    import numpy as np

    points = np.asarray(points, dtype=np.float64)
    extrinsics = np.asarray(extrinsics, dtype=np.float64)
    intrinsics = np.asarray(intrinsics, dtype=np.float64)
    height, width = points.shape[1:3]
    rows, columns = np.meshgrid(
        np.arange(height, dtype=np.float64),
        np.arange(width, dtype=np.float64),
        indexing="ij",
    )
    errors = []
    positive = 0
    for index in range(len(points)):
        camera = points[index] @ extrinsics[index, :3, :3].T + extrinsics[index, :3, 3]
        valid = np.isfinite(camera).all(axis=-1) & (camera[..., 2] > 0.0)
        positive += int(np.count_nonzero(valid))
        if np.any(valid):
            x = intrinsics[index, 0, 0] * camera[..., 0] / camera[..., 2] + intrinsics[index, 0, 2]
            y = intrinsics[index, 1, 1] * camera[..., 1] / camera[..., 2] + intrinsics[index, 1, 2]
            errors.append(np.sqrt((x[valid] - columns[valid]) ** 2 + (y[valid] - rows[valid]) ** 2))
    values = np.concatenate(errors)
    return {
        "direct_point_positive_depth_count": positive,
        "direct_point_reprojection_mean_px": float(np.mean(values)),
        "direct_point_reprojection_max_px": float(np.max(values)),
    }


def _save_archive(path: Path, **arrays: Any) -> None:
    import numpy as np

    for name, value in arrays.items():
        array = np.asarray(value)
        if array.dtype.kind in "fc" and not np.isfinite(array).all():
            raise ValueError(f"non-finite model output: {name}")
    np.savez_compressed(path, **arrays)


def _vggt_cases(manifest: dict[str, Any], input_root: Path, output_root: Path, model_path: Path):
    import numpy as np
    import torch

    from vggt.models.vggt import VGGT
    from vggt.utils.load_fn import load_and_preprocess_images
    from vggt.utils.pose_enc import pose_encoding_to_extri_intri

    started = time.perf_counter()
    model = VGGT.from_pretrained(str(model_path)).to("cuda").eval()
    torch.cuda.synchronize()
    load_seconds = time.perf_counter() - started
    torch.cuda.reset_peak_memory_stats()
    cases: dict[str, Any] = {}
    for case in manifest["cases"]:
        case_started = time.perf_counter()
        image_paths = [str(input_root / path) for path in case["image_paths"]]
        preprocessing_started = time.perf_counter()
        images = load_and_preprocess_images(image_paths, mode="crop")
        preprocessing_seconds = time.perf_counter() - preprocessing_started
        height, width = images.shape[-2:]
        query_x, query_y = torch.meshgrid(
            torch.linspace(0.1 * width, 0.9 * width, 4),
            torch.linspace(0.1 * height, 0.9 * height, 4),
            indexing="xy",
        )
        queries = torch.stack((query_x.reshape(-1), query_y.reshape(-1)), dim=-1).cuda()
        images = images.cuda()
        torch.cuda.synchronize()
        network_started = time.perf_counter()
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            prediction = model(images, query_points=queries)
        torch.cuda.synchronize()
        network_seconds = time.perf_counter() - network_started
        decode_started = time.perf_counter()
        extrinsics, intrinsics = pose_encoding_to_extri_intri(
            prediction["pose_enc"], images.shape[-2:]
        )
        depth = prediction["depth"][0, ..., 0].float().cpu().numpy()
        extrinsics_array = _canonical_extrinsics(extrinsics[0].float().cpu().numpy())
        intrinsics_array = intrinsics[0].float().cpu().numpy()
        pointmap_depth = _unproject_depth(depth, intrinsics_array, extrinsics_array)
        direct = prediction["world_points"][0].float().cpu().numpy()
        confidence = prediction["depth_conf"][0].float().cpu().numpy()
        tracks = prediction["track"][0].float().cpu().numpy()
        visibility = prediction["vis"][0].float().cpu().numpy()
        track_confidence = prediction["conf"][0].float().cpu().numpy()
        decoding_seconds = time.perf_counter() - decode_started
        archive = f"{VGGT_METHOD.replace('/', '-')}-{case['id']}.npz"
        checks = _geometry_checks(depth, pointmap_depth, extrinsics_array, intrinsics_array)
        checks.update(_direct_point_checks(direct, extrinsics_array, intrinsics_array))
        export_started = time.perf_counter()
        _save_archive(
            output_root / archive,
            confidence=confidence.astype(np.float32),
            depth=depth.astype(np.float32),
            extrinsics_w2c=extrinsics_array.astype(np.float32),
            intrinsics_px=intrinsics_array.astype(np.float32),
            pointmap_depth=pointmap_depth.astype(np.float32),
            pointmap_direct=direct.astype(np.float32),
            track_confidence=track_confidence.astype(np.float32),
            track_queries=queries.float().cpu().numpy().astype(np.float32),
            track_visibility=visibility.astype(np.float32),
            tracks=tracks.astype(np.float32),
        )
        export_seconds = time.perf_counter() - export_started
        total_seconds = time.perf_counter() - case_started
        cases[case["id"]] = {
            "archive": archive,
            "frame_ids": case["frame_ids"],
            "original_size_hw": manifest["original_size_hw"],
            "processed_size_hw": [height, width],
            "preprocessing": "official crop loader: width=518 aspect-preserving bicubic resize; height rounded to patch multiple; center crop above 518; cross-image white padding if needed",
            "inputs": _input_contract(
                case,
                manifest,
                [height, width],
                geometric_transform="official width-518 crop-mode resize/crop/pad path",
                normalization="PIL RGB to torch float tensor in [0,1]; no channel mean/std normalization",
            ),
            "reference_view_index": 0,
            "optimization": "none",
            "camera_convention": "OpenCV world-to-camera",
            "depth_semantics": "camera-z relative scale",
            "canonical_pointmap": "depth unprojection",
            "pixel_coordinate_origin": "integer pixel centers (0,0) through (W-1,H-1)",
            "direct_pointmap_present": True,
            "tracks_present": True,
            "tracks": _track_contract(
                case,
                [height, width],
                queries.float().cpu().numpy().astype(np.float32),
                tracks.astype(np.float32),
                visibility.astype(np.float32),
                track_confidence.astype(np.float32),
            ),
            "confidence": {
                "raw_head": "depth_conf",
                "shape": list(confidence.shape),
                "domain": "positive model score; not cross-model calibrated",
                "threshold": None,
            },
            "validity": _validity(depth, pointmap_depth, confidence),
            "gauge": {
                "reference": "learned shared world frame anchored by the first input",
                "metric_scale": False,
                "alignment_applied": "none",
                "optimization": "none",
            },
            "checks": checks,
            "runtime_seconds": {
                "preprocessing": preprocessing_seconds,
                "network": network_seconds,
                "decoding_unprojection": decoding_seconds,
                "export": export_seconds,
                "total": total_seconds,
            },
        }
    return cases, load_seconds, int(torch.cuda.max_memory_allocated())


def _da3_cases(manifest: dict[str, Any], input_root: Path, output_root: Path, model_path: Path):
    import numpy as np
    import torch

    from depth_anything_3.api import DepthAnything3

    started = time.perf_counter()
    model = DepthAnything3.from_pretrained(str(model_path)).to("cuda").eval()
    torch.cuda.synchronize()
    load_seconds = time.perf_counter() - started
    torch.cuda.reset_peak_memory_stats()
    cases: dict[str, Any] = {}
    for case in manifest["cases"]:
        case_started = time.perf_counter()
        image_paths = [str(input_root / path) for path in case["image_paths"]]
        preprocessing_started = time.perf_counter()
        imgs_cpu, extrinsics_input, intrinsics_input = model._preprocess_inputs(
            image_paths,
            None,
            None,
            504,
            "upper_bound_resize",
        )
        images, extrinsics_tensor, intrinsics_tensor = model._prepare_model_inputs(
            imgs_cpu, extrinsics_input, intrinsics_input
        )
        normalized_extrinsics = model._normalize_extrinsics(
            extrinsics_tensor.clone() if extrinsics_tensor is not None else None
        )
        torch.cuda.synchronize()
        preprocessing_seconds = time.perf_counter() - preprocessing_started
        network_started = time.perf_counter()
        raw_output = model._run_model_forward(
            images,
            normalized_extrinsics,
            intrinsics_tensor,
            [],
            False,
            False,
            "first",
        )
        torch.cuda.synchronize()
        network_seconds = time.perf_counter() - network_started
        decode_started = time.perf_counter()
        prediction = model._convert_to_prediction(raw_output)
        prediction = model._align_to_input_extrinsics_intrinsics(
            extrinsics_input, intrinsics_input, prediction, True
        )
        prediction = model._add_processed_images(prediction, imgs_cpu)
        depth = np.asarray(prediction.depth, dtype=np.float32)
        extrinsics_array = _canonical_extrinsics(prediction.extrinsics)
        intrinsics_array = np.asarray(prediction.intrinsics, dtype=np.float32)
        pointmap_depth = _unproject_depth(depth, intrinsics_array, extrinsics_array)
        confidence = (
            np.asarray(prediction.conf, dtype=np.float32)
            if prediction.conf is not None
            else np.ones_like(depth, dtype=np.float32)
        )
        decoding_seconds = time.perf_counter() - decode_started
        archive = f"{DA3_METHOD.replace('/', '-')}-{case['id']}.npz"
        checks = _geometry_checks(depth, pointmap_depth, extrinsics_array, intrinsics_array)
        export_started = time.perf_counter()
        _save_archive(
            output_root / archive,
            confidence=confidence,
            depth=depth,
            extrinsics_w2c=extrinsics_array,
            intrinsics_px=intrinsics_array,
            pointmap_depth=pointmap_depth.astype(np.float32),
        )
        export_seconds = time.perf_counter() - export_started
        total_seconds = time.perf_counter() - case_started
        cases[case["id"]] = {
            "archive": archive,
            "frame_ids": case["frame_ids"],
            "original_size_hw": manifest["original_size_hw"],
            "processed_size_hw": list(depth.shape[-2:]),
            "preprocessing": "504px upper-bound aspect-preserving resize; dimensions rounded to patch multiple",
            "inputs": _input_contract(
                case,
                manifest,
                depth.shape[-2:],
                geometric_transform="504px upper-bound aspect-preserving resize with patch-multiple dimensions",
                normalization="ImageNet RGB mean=[0.485,0.456,0.406], std=[0.229,0.224,0.225]",
            ),
            "reference_view_index": 0,
            "optimization": "none",
            "camera_convention": "OpenCV world-to-camera",
            "depth_semantics": "camera-z relative scale",
            "canonical_pointmap": "depth unprojection",
            "pixel_coordinate_origin": "integer pixel centers (0,0) through (W-1,H-1)",
            "direct_pointmap_present": False,
            "tracks_present": False,
            "tracks": {"status": "unsupported"},
            "confidence": {
                "raw_head": "prediction.conf",
                "shape": list(confidence.shape),
                "domain": "raw model confidence; not cross-model calibrated",
                "threshold": None,
            },
            "validity": _validity(depth, pointmap_depth, confidence),
            "gauge": {
                "reference": "learned shared world frame with fixed first-image reference selection",
                "metric_scale": False,
                "alignment_applied": "none",
                "optimization": "none",
            },
            "checks": checks,
            "runtime_seconds": {
                "preprocessing": preprocessing_seconds,
                "network": network_seconds,
                "decoding_unprojection": decoding_seconds,
                "export": export_seconds,
                "total": total_seconds,
            },
        }
    return cases, load_seconds, int(torch.cuda.max_memory_allocated())


def _loaded_module_files() -> list[dict[str, Any]]:
    records = []
    seen = set()
    for module in sys.modules.values():
        value = getattr(module, "__file__", None)
        if not value:
            continue
        path = Path(value)
        try:
            resolved = path.resolve(strict=True)
        except (FileNotFoundError, OSError):
            continue
        key = str(resolved)
        if key in seen or not resolved.is_file():
            continue
        seen.add(key)
        records.append(
            {
                "path": key,
                "byte_size": resolved.stat().st_size,
                "sha256": _sha256(resolved),
            }
        )
    return sorted(records, key=lambda item: item["path"])


def main() -> int:
    args = _parser().parse_args()
    import numpy as np
    import torch
    import torchvision

    if args.output.exists() and any(args.output.iterdir()):
        raise FileExistsError(f"output directory is not empty: {args.output}")
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((args.input / "manifest.json").read_text())
    lock = json.loads(args.model_lock.read_text())
    environment_lock = lock["environment"]
    environment_manifest = json.loads(args.environment_manifest.read_text())
    if (
        environment_manifest["tree_sha256"] != environment_lock["tree_sha256"]
        or environment_manifest["file_count"] != environment_lock["file_count"]
        or environment_manifest["byte_size"] != environment_lock["byte_size"]
    ):
        raise ValueError("foundation environment manifest does not match its lock")
    torch.manual_seed(260925)
    np.random.seed(260925)
    torch.backends.cudnn.benchmark = False
    torch.backends.cuda.matmul.allow_tf32 = False
    total_started = time.perf_counter()
    upstream_unprojection_parity = _upstream_unprojection_parity()
    vggt_cases, vggt_load, vggt_peak = _vggt_cases(
        manifest, args.input, args.output, args.vggt_model
    )
    da3_cases, da3_load, da3_peak = _da3_cases(
        manifest, args.input, args.output, args.da3_model
    )
    torch.cuda.synchronize()
    nvcc = subprocess.run(
        ["nvcc", "--version"], text=True, capture_output=True, check=False
    )
    source_contracts = {
        VGGT_METHOD: {
            "repository": lock["models"]["vggt"]["source_repository"],
            "commit": lock["models"]["vggt"]["source_commit"],
            "license": lock["models"]["vggt"]["source_license"],
            "tree_sha256": lock["models"]["vggt"]["source_archive"]["tree_sha256"],
            "nested_gitlinks": lock["models"]["vggt"]["nested_gitlinks"],
        },
        DA3_METHOD: {
            "repository": lock["models"]["depth-anything-3"]["source_repository"],
            "commit": lock["models"]["depth-anything-3"]["source_commit"],
            "license": lock["models"]["depth-anything-3"]["source_license"],
            "tree_sha256": lock["models"]["depth-anything-3"]["source_tree_sha256"],
            "nested_gitlinks": lock["models"]["depth-anything-3"][
                "nested_gitlinks"
            ],
        },
    }
    result = {
        "schema_version": 2,
        "network_mode": "offline",
        "methods": {
            VGGT_METHOD: {
                "source_commit": VGGT_SOURCE_COMMIT,
                "source": source_contracts[VGGT_METHOD],
                "checkpoint": _checkpoint_contract(lock["models"]["vggt"]),
                "checkpoint_path": str(args.vggt_model),
                "upstream_unprojection_parity": upstream_unprojection_parity[
                    VGGT_METHOD
                ],
                "load_seconds": vggt_load,
                "peak_gpu_memory_bytes": vggt_peak,
                "cases": vggt_cases,
            },
            DA3_METHOD: {
                "source_commit": DA3_SOURCE_COMMIT,
                "source": source_contracts[DA3_METHOD],
                "checkpoint": _checkpoint_contract(
                    lock["models"]["depth-anything-3"]
                ),
                "checkpoint_path": str(args.da3_model),
                "upstream_unprojection_parity": upstream_unprojection_parity[
                    DA3_METHOD
                ],
                "load_seconds": da3_load,
                "peak_gpu_memory_bytes": da3_peak,
                "cases": da3_cases,
            },
        },
        "runtime": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "torchvision": torchvision.__version__,
            "cuda_runtime": torch.version.cuda,
            "device": torch.cuda.get_device_name(0),
            "compute_capability": list(torch.cuda.get_device_capability(0)),
            "deterministic_seed": 260925,
            "cudnn_benchmark": torch.backends.cudnn.benchmark,
            "tf32": torch.backends.cuda.matmul.allow_tf32,
            "dtype": "bfloat16 autocast where supported by model",
            "numpy": np.__version__,
            "attention_backend": {
                "selection": "PyTorch scaled-dot-product attention automatic backend; xformers absent",
                "flash_sdp_enabled": torch.backends.cuda.flash_sdp_enabled(),
                "memory_efficient_sdp_enabled": torch.backends.cuda.mem_efficient_sdp_enabled(),
                "math_sdp_enabled": torch.backends.cuda.math_sdp_enabled(),
            },
            "cuda_compiler": nvcc.stdout.strip() if nvcc.returncode == 0 else "unavailable",
            "total_seconds": time.perf_counter() - total_started,
        },
        "environment": {
            "build_lock": environment_lock["build_lock"],
            "tree_sha256": environment_manifest["tree_sha256"],
            "file_count": environment_manifest["file_count"],
            "byte_size": environment_manifest["byte_size"],
            "manifest_sha256": _sha256(args.environment_manifest),
            "distributions": environment_manifest["distributions"],
            "native_binaries": environment_manifest["native_binaries"],
            "python_executable": {
                "path": sys.executable,
                "sha256": _sha256(Path(sys.executable).resolve()),
            },
            "loaded_module_files": _loaded_module_files(),
        },
    }
    (args.output / "inference-manifest.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    self_rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    child_rss = int(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
    (args.output / "resource-usage.txt").write_text(
        f"Maximum resident set size (kbytes): {max(self_rss, child_rss)}\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
