#!/usr/bin/env python3
"""Train and evaluate the pinned Nerfstudio Nerfacto reference."""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
from pathlib import Path
import platform
import random
import shutil
import subprocess
import time

import numpy as np
import PIL
from PIL import Image
from scipy import ndimage
import torch
import torchvision
import tinycudann as tcnn

from nerfstudio.cameras.cameras import Cameras, CameraType
from nerfstudio.configs.method_configs import method_configs


NERFSTUDIO_COMMIT = "50e0e3c70c775e89333256213363badbf074f29d"
TCNN_COMMIT = "0109538c37ac0bf613f2bac8de6cda48352feca7"
REQUIREMENTS_LOCK_SHA256 = "02c623f2a636dd774dda048f1a08c8d936d0701f74d3f50b3a7916d2280ed65a"
SEED = 260925
SWEEP_COUNTS = (3, 5, 9)
SWEEP_ITERATIONS = 1000
SWEEP_RAYS = 1024
NERF_SYNTHETIC_SHA256 = "ce4e94e031c099a19ef04cfb6c71f1e47225d97d365be610b476e379a386c25f"
NERF_SYNTHETIC_TREE_SHA256 = "b98a082b13d4b099d54cbcbea474d967cb3f448e9304494ba0749bde874936fe"
CANONICAL_IMAGE_SIZE = 256
CANONICAL_ITERATIONS = 2000
CANONICAL_RAYS = 2048
CANONICAL_TRAIN_INDICES = (0, 6, 13, 19, 26, 33, 39, 46, 52, 59, 66, 72, 79, 85, 92, 99)
CANONICAL_TARGET_INDICES = (0, 66, 132, 199)


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def _source_commit(path: Path) -> str:
    return subprocess.run(
        ["git", "-c", f"safe.directory={path}", "-C", str(path), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _seed_everything() -> None:
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def _query_density(field: torch.nn.Module, points: np.ndarray, batch: int = 262144) -> np.ndarray:
    values = np.empty(len(points), dtype=np.float32)
    field.eval()
    with torch.no_grad():
        for start in range(0, len(points), batch):
            sample = torch.from_numpy(points[start : start + batch]).cuda()
            density = field.density_fn(sample)
            values[start : start + len(sample)] = (
                density.reshape(-1).detach().float().cpu().numpy()
            )
    return values


def _query_density_grid(field: torch.nn.Module, resolution: int) -> np.ndarray:
    axis = np.linspace(-1.0, 1.0, resolution, dtype=np.float32)
    grid = np.empty((resolution, resolution, resolution), dtype=np.float32)
    slab = max(1, min(8, 524288 // (resolution * resolution)))
    for start in range(0, resolution, slab):
        xx, yy, zz = np.meshgrid(axis[start : start + slab], axis, axis, indexing="ij")
        points = np.stack((xx, yy, zz), axis=-1).reshape(-1, 3)
        grid[start : start + len(xx)] = _query_density(field, points).reshape(xx.shape)
    return grid


def _environment_gates(trainer: object) -> dict[str, bool]:
    capability = torch.cuda.get_device_capability(0)
    if capability != (10, 0):
        raise RuntimeError(f"Nerfacto reference requires compute capability 10.0, got {capability}")
    encoding = tcnn.Encoding(
        3,
        {
            "otype": "HashGrid",
            "n_levels": 2,
            "n_features_per_level": 2,
            "log2_hashmap_size": 8,
            "base_resolution": 4,
            "per_level_scale": 2.0,
        },
    )
    encoded_input = torch.rand((16, 3), device="cuda", requires_grad=True)
    encoded = encoding(encoded_input)
    encoded.square().mean().backward()
    tcnn_gate = encoded_input.grad is not None and torch.isfinite(encoded_input.grad).all().item()
    if not tcnn_gate:
        raise RuntimeError("tiny-cuda-nn forward/backward gate failed")

    trainer.pipeline.train()
    _, loss_dict, _ = trainer.pipeline.get_train_loss_dict(step=0)
    sum(loss_dict.values()).backward()
    gradients = [
        parameter.grad
        for parameter in trainer.pipeline.model.parameters()
        if parameter.grad is not None
    ]
    model_gate = bool(gradients) and all(
        torch.isfinite(value).all().item() for value in gradients
    )
    trainer.optimizers.zero_grad_all()
    if not model_gate:
        raise RuntimeError("Nerfacto forward/backward gate failed")

    density = _query_density_grid(trainer.pipeline.model.field, 32)
    density_gate = (
        density.shape == (32, 32, 32)
        and np.isfinite(density).all()
        and np.all(density >= 0.0)
    )
    if not density_gate:
        raise RuntimeError("Nerfacto density query gate failed")
    return {
        "compute_capability_10_0": True,
        "tcnn_forward_backward": bool(tcnn_gate),
        "nerfacto_forward_backward": bool(model_gate),
        "density_query_32": bool(density_gate),
    }


def _camera(frame: dict[str, object], intrinsics: dict[str, object]) -> Cameras:
    camera_to_world = np.asarray(frame["camera_to_world_model"], dtype=np.float32).copy()
    camera_to_world[:3, 1:3] *= -1.0
    return Cameras(
        fx=float(intrinsics["fx"]),
        fy=float(intrinsics["fy"]),
        cx=float(intrinsics["cx"]),
        cy=float(intrinsics["cy"]),
        height=int(intrinsics["height"]),
        width=int(intrinsics["width"]),
        camera_to_worlds=torch.from_numpy(camera_to_world[:3, :4]).unsqueeze(0),
        camera_type=CameraType.PERSPECTIVE,
    )


def _camera_axis_depth(
    camera: Cameras, ray_depth: torch.Tensor, camera_to_world_opencv: np.ndarray
) -> np.ndarray:
    ray_bundle = camera.generate_rays(camera_indices=0, keep_shape=True).to("cuda")
    depth = ray_depth.squeeze(-1).to(ray_bundle.directions.device)
    points = ray_bundle.origins + ray_bundle.directions * depth[..., None]
    points_numpy = points.detach().float().cpu().numpy()
    rotation = camera_to_world_opencv[:3, :3]
    center = camera_to_world_opencv[:3, 3]
    return ((points_numpy - center) @ rotation)[:, :, 2].astype(np.float32)


def _config(
    data: Path,
    output: Path,
    iterations: int,
    rays_per_batch: int,
    timestamp: str,
) -> object:
    config = copy.deepcopy(method_configs["nerfacto"])
    config.machine.seed = SEED
    config.machine.num_devices = 1
    config.output_dir = output
    config.experiment_name = "controlled-sphere"
    config.timestamp = timestamp
    config.max_num_iterations = iterations
    config.steps_per_save = iterations + 1
    config.steps_per_eval_batch = 0
    config.steps_per_eval_image = 0
    config.steps_per_eval_all_images = 0
    config.vis = "tensorboard"
    config.logging.local_writer.enable = False
    config.logging.profiler = "none"
    config.viewer.quit_on_train_completion = True
    config.pipeline.datamanager.train_num_rays_per_batch = rays_per_batch
    config.pipeline.datamanager.eval_num_rays_per_batch = rays_per_batch
    config.pipeline.datamanager.dataparser.data = data
    config.pipeline.datamanager.dataparser.orientation_method = "none"
    config.pipeline.datamanager.dataparser.center_method = "none"
    config.pipeline.datamanager.dataparser.auto_scale_poses = False
    config.pipeline.datamanager.dataparser.scale_factor = 1.0
    config.pipeline.datamanager.dataparser.scene_scale = 1.0
    config.pipeline.datamanager.dataparser.downscale_factor = 1
    config.pipeline.datamanager.dataparser.eval_mode = "all"
    config.pipeline.datamanager.dataloader_num_workers = 1
    config.pipeline.model.camera_optimizer.mode = "off"
    config.pipeline.model.use_appearance_embedding = False
    config.pipeline.model.disable_scene_contraction = True
    config.pipeline.model.near_plane = 0.1
    config.pipeline.model.far_plane = 6.0
    config.pipeline.model.collider_params = {"near_plane": 0.1, "far_plane": 6.0}
    config.pipeline.model.proposal_initial_sampler = "uniform"
    config.save_config()
    return config


def _train(
    data: Path,
    output: Path,
    iterations: int,
    rays_per_batch: int,
    timestamp: str,
    run_gates: bool,
) -> tuple[object, object, float, dict[str, bool] | None]:
    _seed_everything()
    config = _config(data, output, iterations, rays_per_batch, timestamp)
    trainer = config.setup(local_rank=0, world_size=1)
    trainer.setup(test_mode="val")
    gates = _environment_gates(trainer) if run_gates else None
    started = time.perf_counter()
    trainer.train()
    training_seconds = time.perf_counter() - started
    trainer.pipeline.eval()
    return trainer, config, training_seconds, gates


def _lpips(
    model: object,
    predicted: torch.Tensor,
    truth: np.ndarray,
    foreground_mask: np.ndarray,
) -> tuple[float, float]:
    truth_tensor = torch.from_numpy(truth.astype(np.float32) / 255.0).to(model.device)
    predicted = predicted.to(model.device)
    if foreground_mask.shape != truth.shape[:2]:
        raise RuntimeError("truth foreground mask has the wrong shape")
    rows, columns = np.nonzero(foreground_mask)
    if not len(rows):
        raise RuntimeError("truth image has no foreground crop")
    row_slice = slice(int(rows.min()), int(rows.max()) + 1)
    column_slice = slice(int(columns.min()), int(columns.max()) + 1)

    def score(left: torch.Tensor, right: torch.Tensor) -> float:
        return float(
            model.lpips(
                left.permute(2, 0, 1).unsqueeze(0),
                right.permute(2, 0, 1).unsqueeze(0),
            )
        )

    return (
        score(predicted, truth_tensor),
        score(predicted[row_slice, column_slice], truth_tensor[row_slice, column_slice]),
    )


def _render_frames(
    trainer: object,
    frames: list[dict[str, object]],
    intrinsics: dict[str, object],
    input_root: Path,
    render_dir: Path,
    *,
    geometry: bool,
    perceptual: bool,
) -> list[dict[str, object]]:
    render_dir.mkdir(parents=True)
    rows: list[dict[str, object]] = []
    for frame in frames:
        camera = _camera(frame, intrinsics)
        with torch.no_grad():
            outputs = trainer.pipeline.model.get_outputs_for_camera(camera)
        rgb_tensor = outputs["rgb"].detach().float()
        rgb_float = rgb_tensor.cpu().numpy().astype(np.float32)
        rgb = np.clip(rgb_float * 255.0, 0.0, 255.0).round().astype(np.uint8)
        np.save(render_dir / f"{frame['id']}.rgb.npy", rgb, allow_pickle=False)
        np.save(
            render_dir / f"{frame['id']}.rgb.float32.npy",
            rgb_float,
            allow_pickle=False,
        )
        if geometry:
            accumulation = (
                outputs["accumulation"].detach().float().cpu().numpy().squeeze(-1).astype(np.float32)
            )
            camera_to_world = np.asarray(frame["camera_to_world_model"], dtype=np.float64)
            median_camera_depth = _camera_axis_depth(camera, outputs["depth"].detach(), camera_to_world)
            expected_camera_depth = _camera_axis_depth(
                camera, outputs["expected_depth"].detach(), camera_to_world
            )
            np.save(
                render_dir / f"{frame['id']}.accumulation.npy",
                accumulation,
                allow_pickle=False,
            )
            np.save(
                render_dir / f"{frame['id']}.median-camera-depth.npy",
                median_camera_depth,
                allow_pickle=False,
            )
            np.save(
                render_dir / f"{frame['id']}.expected-camera-depth.npy",
                expected_camera_depth,
                allow_pickle=False,
            )
        if perceptual:
            truth = np.load(input_root / str(frame["rgb_truth_path"]), allow_pickle=False)
            foreground_mask = np.asarray(
                Image.open(input_root / str(frame["mask_path"]))
            ) > 0
            with torch.no_grad():
                full_lpips, crop_lpips = _lpips(
                    trainer.pipeline.model,
                    rgb_tensor,
                    truth,
                    foreground_mask,
                )
            rows.append(
                {"id": frame["id"], "lpips": full_lpips, "crop_lpips": crop_lpips}
            )
    return rows


def _sweep_dataset(
    destination: Path,
    input_root: Path,
    manifest: dict[str, object],
    frame_ids: list[str],
) -> Path:
    destination.mkdir(parents=True)
    frames_by_id = {frame["id"]: frame for frame in manifest["context_frames"]}
    intrinsics = manifest["intrinsics"]
    frames = []
    for frame_id in frame_ids:
        frame = frames_by_id[frame_id]
        transform = np.asarray(frame["camera_to_world_model"], dtype=np.float64).copy()
        transform[:3, 1:3] *= -1.0
        frames.append(
            {
                "file_path": str((input_root / str(frame["image_path"])).resolve(strict=True)),
                "transform_matrix": transform.tolist(),
            }
        )
    transforms = {
        "camera_model": "OPENCV",
        "w": int(intrinsics["width"]),
        "h": int(intrinsics["height"]),
        "fl_x": float(intrinsics["fx"]),
        "fl_y": float(intrinsics["fy"]),
        "cx": float(intrinsics["cx"]),
        "cy": float(intrinsics["cy"]),
        "k1": 0.0,
        "k2": 0.0,
        "p1": 0.0,
        "p2": 0.0,
        "orientation_override": "none",
        "center_override": "none",
        "auto_scale_poses": False,
        "scale_factor": 1.0,
        "frames": frames,
    }
    _write_json(destination / "transforms.json", transforms)
    return destination


def _copy_primary_sweep(primary: Path, destination: Path, frames: list[dict[str, object]]) -> None:
    destination.mkdir(parents=True)
    for frame in frames:
        for suffix in ("rgb.float32.npy", "accumulation.npy", "expected-camera-depth.npy"):
            shutil.copy2(primary / f"{frame['id']}.{suffix}", destination / f"{frame['id']}.{suffix}")


def _canonical_source_frame(
    frames: list[dict[str, object]], split: str, index: int
) -> dict[str, object]:
    expected = f"{split}/r_{index}"
    matches = [
        frame
        for frame in frames
        if str(frame.get("file_path", "")).removeprefix("./") == expected
    ]
    if len(matches) != 1:
        raise RuntimeError(f"canonical NeRF example frame inventory mismatch: {expected}")
    return matches[0]


def _canonical_rgb(source: Path) -> np.ndarray:
    with Image.open(source) as image:
        rgba = image.convert("RGBA").resize(
            (CANONICAL_IMAGE_SIZE, CANONICAL_IMAGE_SIZE),
            resample=Image.Resampling.LANCZOS,
        )
        values = np.asarray(rgba, dtype=np.float32) / 255.0
    alpha = values[..., 3:4]
    return (values[..., :3] * alpha + (1.0 - alpha)).astype(np.float32)


def _prepare_canonical_nerf_example(
    source: Path,
    destination: Path,
    archive_sha256: str,
    tree_sha256: str,
) -> tuple[Path, list[dict[str, object]], dict[str, object]]:
    if archive_sha256 != NERF_SYNTHETIC_SHA256 or tree_sha256 != NERF_SYNTHETIC_TREE_SHA256:
        raise RuntimeError("canonical NeRF example asset identity mismatch")
    train_record = json.loads((source / "transforms_train.json").read_text())
    test_record = json.loads((source / "transforms_test.json").read_text())
    train_frames = train_record.get("frames")
    test_frames = test_record.get("frames")
    if (
        not isinstance(train_frames, list)
        or len(train_frames) != 100
        or not isinstance(test_frames, list)
        or len(test_frames) != 200
        or train_record.get("camera_angle_x") != test_record.get("camera_angle_x")
    ):
        raise RuntimeError("canonical NeRF example transforms mismatch")
    destination.mkdir(parents=True)
    images = destination / "images"
    truth = destination.parent / "truth"
    images.mkdir()
    truth.mkdir()
    transformed_train: list[dict[str, object]] = []
    training_ids: list[str] = []
    for ordinal, index in enumerate(CANONICAL_TRAIN_INDICES):
        frame = _canonical_source_frame(train_frames, "train", index)
        frame_id = f"train/r_{index}"
        rgb = _canonical_rgb(source / f"{frame_id}.png")
        image_path = images / f"train-{ordinal:03d}.png"
        Image.fromarray(np.rint(rgb * 255.0).astype(np.uint8), mode="RGB").save(image_path)
        transformed_train.append(
            {
                "file_path": f"images/{image_path.name}",
                "transform_matrix": frame["transform_matrix"],
            }
        )
        training_ids.append(frame_id)
    target_frames: list[dict[str, object]] = []
    target_rows: list[dict[str, str]] = []
    for ordinal, index in enumerate(CANONICAL_TARGET_INDICES):
        frame = _canonical_source_frame(test_frames, "test", index)
        frame_id = f"test/r_{index}"
        rgb = _canonical_rgb(source / f"{frame_id}.png")
        truth_path = truth / f"target-{ordinal:03d}.rgb.float32.npy"
        np.save(truth_path, rgb, allow_pickle=False)
        opencv = np.asarray(frame["transform_matrix"], dtype=np.float64).copy()
        if opencv.shape != (4, 4) or not np.isfinite(opencv).all():
            raise RuntimeError("canonical NeRF example camera transform mismatch")
        opencv[:3, 1:3] *= -1.0
        target_frames.append(
            {"id": frame_id, "camera_to_world_model": opencv.tolist()}
        )
        target_rows.append(
            {
                "id": frame_id,
                "truth_path": f"truth/{truth_path.name}",
                "render_path": f"renders/target-{ordinal:03d}.rgb.float32.npy",
            }
        )
    angle_x = float(train_record["camera_angle_x"])
    focal = 0.5 * CANONICAL_IMAGE_SIZE / np.tan(0.5 * angle_x)
    intrinsics = {
        "width": CANONICAL_IMAGE_SIZE,
        "height": CANONICAL_IMAGE_SIZE,
        "fx": float(focal),
        "fy": float(focal),
        "cx": CANONICAL_IMAGE_SIZE / 2.0,
        "cy": CANONICAL_IMAGE_SIZE / 2.0,
    }
    transforms = {
        "camera_model": "OPENCV",
        "w": CANONICAL_IMAGE_SIZE,
        "h": CANONICAL_IMAGE_SIZE,
        "fl_x": float(focal),
        "fl_y": float(focal),
        "cx": CANONICAL_IMAGE_SIZE / 2.0,
        "cy": CANONICAL_IMAGE_SIZE / 2.0,
        "k1": 0.0,
        "k2": 0.0,
        "p1": 0.0,
        "p2": 0.0,
        "orientation_override": "none",
        "center_override": "none",
        "auto_scale_poses": False,
        "scale_factor": 1.0,
        "frames": transformed_train,
    }
    _write_json(destination / "transforms.json", transforms)
    manifest = {
        "schema_version": 1,
        "asset_id": "nerf-synthetic",
        "archive_sha256": archive_sha256,
        "extraction_tree_sha256": tree_sha256,
        "dataset": "nerf_synthetic/lego",
        "training_frame_ids": training_ids,
        "target_frame_ids": [frame["id"] for frame in target_frames],
        "image_size": [CANONICAL_IMAGE_SIZE, CANONICAL_IMAGE_SIZE],
        "iterations": CANONICAL_ITERATIONS,
        "rays_per_batch": CANONICAL_RAYS,
        "seed": SEED,
        "targets": target_rows,
    }
    return destination, target_frames, {"intrinsics": intrinsics, "manifest": manifest}


def _run_canonical_nerf_example(
    source: Path,
    output: Path,
    archive_sha256: str,
    tree_sha256: str,
) -> dict[str, object]:
    canonical_output = output / "canonical-nerf-example"
    data, target_frames, prepared = _prepare_canonical_nerf_example(
        source,
        canonical_output / "data",
        archive_sha256,
        tree_sha256,
    )
    trainer, _, training_seconds, _ = _train(
        data,
        canonical_output / "training",
        CANONICAL_ITERATIONS,
        CANONICAL_RAYS,
        "canonical-nerf-example",
        False,
    )
    render_dir = canonical_output / "renders"
    render_dir.mkdir()
    for ordinal, frame in enumerate(target_frames):
        camera = _camera(frame, prepared["intrinsics"])
        with torch.no_grad():
            outputs = trainer.pipeline.model.get_outputs_for_camera(camera)
        predicted = outputs["rgb"].detach().float().cpu().numpy().astype(np.float32)
        if predicted.shape != (CANONICAL_IMAGE_SIZE, CANONICAL_IMAGE_SIZE, 3):
            raise RuntimeError("canonical NeRF example render shape mismatch")
        np.save(
            render_dir / f"target-{ordinal:03d}.rgb.float32.npy",
            predicted,
            allow_pickle=False,
        )
    _write_json(canonical_output / "manifest.json", prepared["manifest"])
    del trainer
    torch.cuda.empty_cache()
    shutil.rmtree(canonical_output / "training", ignore_errors=True)
    return {
        "asset_id": "nerf-synthetic",
        "dataset": "nerf_synthetic/lego",
        "iterations": CANONICAL_ITERATIONS,
        "rays_per_batch": CANONICAL_RAYS,
        "training_views": len(CANONICAL_TRAIN_INDICES),
        "target_views": len(CANONICAL_TARGET_INDICES),
        "image_size": CANONICAL_IMAGE_SIZE,
        "training_seconds": training_seconds,
    }


def _sweep_measurements(
    output: Path,
    input_root: Path,
    manifest: dict[str, object],
    density: np.ndarray,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    target_frames = manifest.get("target_frames")
    if not isinstance(target_frames, list):
        raise RuntimeError("view sweep target inventory is missing")
    for count in SWEEP_COUNTS:
        psnrs = []
        residuals = []
        for frame in target_frames:
            prefix = output / "view-sweep" / f"views-{count}" / str(frame["id"])
            predicted = np.load(Path(f"{prefix}.rgb.float32.npy"), allow_pickle=False).astype(np.float64)
            truth = np.load(input_root / str(frame["rgb_truth_path"]), allow_pickle=False).astype(np.float64) / 255.0
            mse = float(np.mean((predicted - truth) ** 2))
            psnrs.append(-10.0 * np.log10(mse))
            expected = np.load(Path(f"{prefix}.expected-camera-depth.npy"), allow_pickle=False)
            accumulation = np.load(Path(f"{prefix}.accumulation.npy"), allow_pickle=False)
            truth_depth = np.load(input_root / str(frame["depth_path"]), allow_pickle=False)
            common = np.load(
                input_root / str(frame["common_visible_mask_path"]), allow_pickle=False
            ).astype(bool)
            valid = (truth_depth > 0.0) & common & (accumulation >= 0.5) & (expected > 0.0)
            residuals.append(expected[valid] - truth_depth[valid])
        residual = np.concatenate(residuals).astype(np.float64)
        rows.extend(
            [
                {
                    "factor": "context_view_count",
                    "value": count,
                    "metric": "target_psnr_db",
                    "measurement": float(np.mean(psnrs)),
                    "interpretation": "trained 1000-step sparse-view fit on fixed targets",
                },
                {
                    "factor": "context_view_count",
                    "value": count,
                    "metric": "expected_depth_rmse_m",
                    "measurement": float(np.sqrt(np.mean(residual * residual))),
                    "interpretation": "common-visible accumulation-qualified rendered depth",
                },
            ]
        )
    component_resolution = min(32, density.shape[0])
    indices = np.linspace(0, density.shape[0] - 1, component_resolution, dtype=np.int64)
    component_grid = density[np.ix_(indices, indices, indices)]
    structure = ndimage.generate_binary_structure(3, 1)
    for threshold in (0.1, 1.0, 10.0, 100.0):
        occupied = density >= threshold
        _, component_count = ndimage.label(component_grid >= threshold, structure=structure)
        rows.extend(
            [
                {
                    "factor": "density_threshold",
                    "value": threshold,
                    "metric": "occupied_fraction",
                    "measurement": float(np.mean(occupied)),
                    "interpretation": "raw density has no canonical surface threshold",
                },
                {
                    "factor": "density_threshold",
                    "value": threshold,
                    "metric": f"component_count_{component_resolution}cube",
                    "measurement": int(component_count),
                    "interpretation": "6-connected diagnostic components on the fixed reduced grid",
                },
            ]
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iterations", type=int, required=True)
    parser.add_argument("--rays-per-batch", type=int, required=True)
    parser.add_argument("--density-resolution", type=int, required=True)
    parser.add_argument("--canonical-input", type=Path)
    parser.add_argument("--canonical-archive-sha256")
    parser.add_argument("--canonical-tree-sha256")
    args = parser.parse_args()
    args.input = args.input.resolve(strict=True)
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((args.input / "manifest.json").read_text())
    if manifest["scene_seed"] != SEED or args.iterations <= 0 or args.rays_per_batch <= 0:
        raise ValueError("invalid locked Nerfacto execution configuration")
    canonical_arguments = (
        args.canonical_input,
        args.canonical_archive_sha256,
        args.canonical_tree_sha256,
    )
    if manifest["profile"] == "full":
        if any(value is None for value in canonical_arguments):
            raise ValueError("full profile requires the locked canonical NeRF example")
        args.canonical_input = args.canonical_input.resolve(strict=True)
    elif any(value is not None for value in canonical_arguments):
        raise ValueError("smoke profile must not consume the canonical NeRF example")

    trainer, config, training_seconds, gates = _train(
        args.input,
        args.output / "training",
        args.iterations,
        args.rays_per_batch,
        "locked",
        True,
    )
    assert gates is not None
    _write_json(args.output / "environment-gates.json", gates)

    checkpoint_candidates = sorted(trainer.checkpoint_dir.glob("step-*.ckpt"))
    if len(checkpoint_candidates) != 1:
        raise RuntimeError("training did not produce exactly one final checkpoint")
    locked_dir = args.output / "nerfstudio"
    locked_dir.mkdir()
    shutil.copy2(checkpoint_candidates[0], locked_dir / "checkpoint.ckpt")
    shutil.copy2(config.get_base_dir() / "config.yml", locked_dir / "config.yml")

    density_started = time.perf_counter()
    density_grid = _query_density_grid(trainer.pipeline.model.field, args.density_resolution)
    density_seconds = time.perf_counter() - density_started
    np.save(args.output / "field.density_grid.float32.npy", density_grid, allow_pickle=False)

    # Target truth is first opened only after the primary optimizer has completed.
    target_frames = manifest["target_frames"]
    frame_by_id = {frame["id"]: frame for frame in manifest["context_frames"]}
    primary_contexts = [frame_by_id[item] for item in manifest["primary_context_frame_ids"]]
    target_metrics = _render_frames(
        trainer,
        target_frames,
        manifest["intrinsics"],
        args.input,
        args.output / "target-renders",
        geometry=True,
        perceptual=True,
    )
    context_metrics = _render_frames(
        trainer,
        primary_contexts,
        manifest["intrinsics"],
        args.input,
        args.output / "context-renders",
        geometry=False,
        perceptual=True,
    )
    _write_json(args.output / "target-image-metrics.json", target_metrics)
    _write_json(args.output / "context-image-metrics.json", context_metrics)
    del trainer
    torch.cuda.empty_cache()

    sweep_seconds: dict[str, float] = {}
    for count in SWEEP_COUNTS:
        sweep_render_dir = args.output / "view-sweep" / f"views-{count}"
        if (
            manifest["profile"] == "smoke"
            and count == 5
            and args.iterations == SWEEP_ITERATIONS
            and args.rays_per_batch == SWEEP_RAYS
        ):
            _copy_primary_sweep(args.output / "target-renders", sweep_render_dir, target_frames)
            sweep_seconds[str(count)] = training_seconds
            continue
        data = _sweep_dataset(
            args.output / "view-sweep-data" / f"views-{count}",
            args.input,
            manifest,
            manifest["view_sweep_context_frame_ids"][str(count)],
        )
        sweep_trainer, _, elapsed, _ = _train(
            data,
            args.output / "sweep-training" / f"views-{count}",
            SWEEP_ITERATIONS,
            SWEEP_RAYS,
            f"views-{count}",
            False,
        )
        _render_frames(
            sweep_trainer,
            target_frames,
            manifest["intrinsics"],
            args.input,
            sweep_render_dir,
            geometry=True,
            perceptual=False,
        )
        sweep_seconds[str(count)] = elapsed
        del sweep_trainer
        torch.cuda.empty_cache()

    rows = _sweep_measurements(args.output, args.input, manifest, density_grid)
    with (args.output / "failure_sweep.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["factor", "value", "metric", "measurement", "interpretation"],
        )
        writer.writeheader()
        writer.writerows(rows)

    canonical_summary = None
    if manifest["profile"] == "full":
        canonical_summary = _run_canonical_nerf_example(
            args.canonical_input,
            args.output,
            args.canonical_archive_sha256,
            args.canonical_tree_sha256,
        )

    shutil.rmtree(args.output / "training", ignore_errors=True)
    shutil.rmtree(args.output / "sweep-training", ignore_errors=True)

    nerfstudio_commit = _source_commit(Path("/opt/src/nerfstudio"))
    tcnn_commit = _source_commit(Path("/opt/src/tiny-cuda-nn"))
    if nerfstudio_commit != NERFSTUDIO_COMMIT or tcnn_commit != TCNN_COMMIT:
        raise RuntimeError("installed source commit mismatch")
    requirements_lock = Path("/etc/surflo-pathway-requirements.lock.txt")
    resolved_requirements = Path("/etc/surflo-pathway-resolved-requirements.txt")
    if _sha256(requirements_lock) != REQUIREMENTS_LOCK_SHA256:
        raise RuntimeError("installed dependency lock mismatch")
    shutil.copy2(requirements_lock, args.output / "requirements.lock.txt")
    shutil.copy2(resolved_requirements, args.output / "resolved-requirements.txt")
    (args.output / "source-commit.txt").write_text(nerfstudio_commit + "\n")
    (args.output / "tcnn-commit.txt").write_text(tcnn_commit + "\n")
    shutil.copy2("/etc/surflo-pathway-insula", args.output / "insula-manifest.txt")
    cuda_compiler = subprocess.run(
        ["nvcc", "--version"], text=True, capture_output=True, check=True
    ).stdout.strip()
    _write_json(
        args.output / "runtime-versions.json",
        {
            "nerfstudio_commit": nerfstudio_commit,
            "tiny_cuda_nn_commit": tcnn_commit,
            "requirements_lock_sha256": _sha256(requirements_lock),
            "resolved_requirements_sha256": _sha256(resolved_requirements),
            "torch": torch.__version__,
            "torchvision": torchvision.__version__,
            "pillow": PIL.__version__,
            "python": platform.python_version(),
            "numpy": np.__version__,
            "cuda_runtime": torch.version.cuda,
            "cuda_compiler": cuda_compiler,
            "compute_capability": list(torch.cuda.get_device_capability(0)),
            "tcnn_cuda_architectures": "100",
            "device": torch.cuda.get_device_name(0),
        },
    )
    _write_json(
        args.output / "training-summary.json",
        {
            "method": "nerfacto",
            "iterations": args.iterations,
            "rays_per_batch": args.rays_per_batch,
            "density_resolution": args.density_resolution,
            "training_seconds": training_seconds,
            "training_steps_per_second": args.iterations / training_seconds,
            "density_query_seconds": density_seconds,
            "camera_optimizer": "off",
            "appearance_embedding": False,
            "scene_contraction": False,
            "near_plane_m": 0.1,
            "far_plane_m": 6.0,
            "proposal_initial_sampler": "uniform",
            "context_split_mode": "all-context-frames-train-and-eval",
            "dataloader_num_workers": 1,
            "tf32": False,
            "seed": SEED,
            "trained_view_sweep": {
                "context_views": list(SWEEP_COUNTS),
                "iterations": SWEEP_ITERATIONS,
                "rays_per_batch": SWEEP_RAYS,
            },
            "view_sweep_training_seconds": sweep_seconds,
            "canonical_nerf_example": canonical_summary,
        },
    )


if __name__ == "__main__":
    main()
