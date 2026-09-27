#!/usr/bin/env python3
"""Run exact local VGGT and DA3 checkpoints on RGB-only pathway evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import resource
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
    return parser


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
        np.arange(height, dtype=np.float64) + 0.5,
        np.arange(width, dtype=np.float64) + 0.5,
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

    from surflo.data.utils import load_and_preprocess_images
    from surflo.nn.vggt.models.vggt import VGGT
    from surflo.nn.vggt.utils.pose_enc import pose_encoding_to_extri_intri
    from surflo.utils.geometry import depths_to_points_parallel_batched

    started = time.perf_counter()
    model = VGGT.from_pretrained(str(model_path)).to("cuda").eval()
    torch.cuda.synchronize()
    load_seconds = time.perf_counter() - started
    torch.cuda.reset_peak_memory_stats()
    cases: dict[str, Any] = {}
    for case in manifest["cases"]:
        image_paths = [str(input_root / path) for path in case["image_paths"]]
        preprocessing_started = time.perf_counter()
        images = load_and_preprocess_images(image_paths, mode="crop", target_size=518)
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
        points = depths_to_points_parallel_batched(
            intrinsics, extrinsics, prediction["depth"], to_world=True
        )
        depth = prediction["depth"][0, ..., 0].float().cpu().numpy()
        pointmap_depth = points[0].float().cpu().numpy()
        extrinsics_array = _canonical_extrinsics(extrinsics[0].float().cpu().numpy())
        intrinsics_array = intrinsics[0].float().cpu().numpy()
        direct = prediction["world_points"][0].float().cpu().numpy()
        confidence = prediction["depth_conf"][0].float().cpu().numpy()
        tracks = prediction["track"][0].float().cpu().numpy()
        visibility = prediction["vis"][0].float().cpu().numpy()
        track_confidence = prediction["conf"][0].float().cpu().numpy()
        decoding_seconds = time.perf_counter() - decode_started
        archive = f"{VGGT_METHOD.replace('/', '-')}-{case['id']}.npz"
        checks = _geometry_checks(depth, pointmap_depth, extrinsics_array, intrinsics_array)
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
        cases[case["id"]] = {
            "archive": archive,
            "frame_ids": case["frame_ids"],
            "original_size_hw": manifest["original_size_hw"],
            "processed_size_hw": [height, width],
            "preprocessing": "width=518 aspect-preserving resize; height rounded to patch multiple; no padding for this suite",
            "reference_view_index": 0,
            "optimization": "none",
            "camera_convention": "OpenCV world-to-camera",
            "depth_semantics": "camera-z relative scale",
            "canonical_pointmap": "depth unprojection",
            "direct_pointmap_present": True,
            "tracks_present": True,
            "checks": checks,
            "runtime_seconds": {
                "preprocessing": preprocessing_seconds,
                "network": network_seconds,
                "decoding_export": decoding_seconds,
            },
        }
    return cases, load_seconds, int(torch.cuda.max_memory_allocated())


def _da3_cases(manifest: dict[str, Any], input_root: Path, output_root: Path, model_path: Path):
    import numpy as np
    import torch

    from depth_anything_3.api import DepthAnything3
    from surflo.utils.geometry import depths_to_points_parallel

    started = time.perf_counter()
    model = DepthAnything3.from_pretrained(str(model_path)).to("cuda").eval()
    torch.cuda.synchronize()
    load_seconds = time.perf_counter() - started
    torch.cuda.reset_peak_memory_stats()
    cases: dict[str, Any] = {}
    for case in manifest["cases"]:
        image_paths = [str(input_root / path) for path in case["image_paths"]]
        torch.cuda.synchronize()
        network_started = time.perf_counter()
        prediction = model.inference(
            image_paths,
            process_res=504,
            process_res_method="upper_bound_resize",
            ref_view_strategy="first",
            use_ray_pose=False,
        )
        torch.cuda.synchronize()
        network_seconds = time.perf_counter() - network_started
        decode_started = time.perf_counter()
        depth = np.asarray(prediction.depth, dtype=np.float32)
        extrinsics_array = _canonical_extrinsics(prediction.extrinsics)
        intrinsics_array = np.asarray(prediction.intrinsics, dtype=np.float32)
        depth_tensor = torch.from_numpy(depth).cuda()
        extrinsics_tensor = torch.from_numpy(extrinsics_array[:, :3]).cuda()
        intrinsics_tensor = torch.from_numpy(intrinsics_array).cuda()
        pointmap_depth = depths_to_points_parallel(
            intrinsics_tensor, extrinsics_tensor, depth_tensor, to_world=True
        ).float().cpu().numpy()
        confidence = (
            np.asarray(prediction.conf, dtype=np.float32)
            if prediction.conf is not None
            else np.ones_like(depth, dtype=np.float32)
        )
        decoding_seconds = time.perf_counter() - decode_started
        archive = f"{DA3_METHOD.replace('/', '-')}-{case['id']}.npz"
        checks = _geometry_checks(depth, pointmap_depth, extrinsics_array, intrinsics_array)
        _save_archive(
            output_root / archive,
            confidence=confidence,
            depth=depth,
            extrinsics_w2c=extrinsics_array,
            intrinsics_px=intrinsics_array,
            pointmap_depth=pointmap_depth.astype(np.float32),
        )
        cases[case["id"]] = {
            "archive": archive,
            "frame_ids": case["frame_ids"],
            "original_size_hw": manifest["original_size_hw"],
            "processed_size_hw": list(depth.shape[-2:]),
            "preprocessing": "504px upper-bound aspect-preserving resize; dimensions rounded to patch multiple",
            "reference_view_index": 0,
            "optimization": "none",
            "camera_convention": "OpenCV world-to-camera",
            "depth_semantics": "camera-z relative scale",
            "canonical_pointmap": "depth unprojection",
            "direct_pointmap_present": False,
            "tracks_present": False,
            "checks": checks,
            "runtime_seconds": {
                "preprocessing_and_network": network_seconds,
                "decoding_export": decoding_seconds,
            },
        }
    return cases, load_seconds, int(torch.cuda.max_memory_allocated())


def main() -> int:
    args = _parser().parse_args()
    import numpy as np
    import torch
    import torchvision

    if args.output.exists() and any(args.output.iterdir()):
        raise FileExistsError(f"output directory is not empty: {args.output}")
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((args.input / "manifest.json").read_text())
    torch.manual_seed(260925)
    np.random.seed(260925)
    torch.backends.cudnn.benchmark = False
    torch.backends.cuda.matmul.allow_tf32 = False
    total_started = time.perf_counter()
    vggt_cases, vggt_load, vggt_peak = _vggt_cases(
        manifest, args.input, args.output, args.vggt_model
    )
    da3_cases, da3_load, da3_peak = _da3_cases(
        manifest, args.input, args.output, args.da3_model
    )
    torch.cuda.synchronize()
    result = {
        "schema_version": 1,
        "network_mode": "offline",
        "methods": {
            VGGT_METHOD: {
                "source_commit": VGGT_SOURCE_COMMIT,
                "checkpoint_path": str(args.vggt_model),
                "load_seconds": vggt_load,
                "peak_gpu_memory_bytes": vggt_peak,
                "cases": vggt_cases,
            },
            DA3_METHOD: {
                "source_commit": DA3_SOURCE_COMMIT,
                "checkpoint_path": str(args.da3_model),
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
            "total_seconds": time.perf_counter() - total_started,
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
