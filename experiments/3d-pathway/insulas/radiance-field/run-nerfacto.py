#!/usr/bin/env python3
"""Train and evaluate the pinned Nerfstudio Nerfacto reference."""

from __future__ import annotations

import argparse
import copy
import csv
import json
from pathlib import Path
import platform
import random
import shutil
import subprocess
import time

import numpy as np
import PIL
import torch
import torchvision
import tinycudann as tcnn

from nerfstudio.cameras.cameras import Cameras, CameraType
from nerfstudio.configs.method_configs import method_configs


NERFSTUDIO_COMMIT = "50e0e3c70c775e89333256213363badbf074f29d"
TCNN_COMMIT = "0109538c37ac0bf613f2bac8de6cda48352feca7"
SEED = 260925


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def _source_commit(path: Path) -> str:
    return subprocess.run(
        ["git", "-c", f"safe.directory={path}", "-C", str(path), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def _query_density(field: torch.nn.Module, points: np.ndarray, batch: int = 262144) -> np.ndarray:
    values = np.empty(len(points), dtype=np.float32)
    field.eval()
    with torch.no_grad():
        for start in range(0, len(points), batch):
            sample = torch.from_numpy(points[start : start + batch]).cuda()
            density = field.density_fn(sample)
            values[start : start + len(sample)] = density.reshape(-1).detach().float().cpu().numpy()
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
    model_gate = bool(gradients) and all(torch.isfinite(value).all().item() for value in gradients)
    trainer.optimizers.zero_grad_all()
    if not model_gate:
        raise RuntimeError("Nerfacto forward/backward gate failed")

    density = _query_density_grid(trainer.pipeline.model.field, 32)
    density_gate = density.shape == (32, 32, 32) and np.isfinite(density).all() and np.all(density >= 0.0)
    if not density_gate:
        raise RuntimeError("Nerfacto density query gate failed")
    return {
        "compute_capability_10_0": True,
        "tcnn_forward_backward": bool(tcnn_gate),
        "nerfacto_forward_backward": bool(model_gate),
        "density_query_32": bool(density_gate),
    }


def _target_camera(frame: dict[str, object], intrinsics: dict[str, object]) -> Cameras:
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
    depth = ray_depth.squeeze(-1)
    points = ray_bundle.origins + ray_bundle.directions * depth[..., None]
    points_numpy = points.detach().float().cpu().numpy()
    rotation = camera_to_world_opencv[:3, :3]
    center = camera_to_world_opencv[:3, 3]
    return ((points_numpy - center) @ rotation)[:, :, 2].astype(np.float32)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iterations", type=int, required=True)
    parser.add_argument("--rays-per-batch", type=int, required=True)
    parser.add_argument("--density-resolution", type=int, required=True)
    args = parser.parse_args()
    args.input = args.input.resolve(strict=True)
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((args.input / "manifest.json").read_text())
    if manifest["scene_seed"] != SEED or args.iterations <= 0 or args.rays_per_batch <= 0:
        raise ValueError("invalid locked Nerfacto execution configuration")

    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

    config = copy.deepcopy(method_configs["nerfacto"])
    config.machine.seed = SEED
    config.machine.num_devices = 1
    config.output_dir = args.output / "training"
    config.experiment_name = "controlled-sphere"
    config.timestamp = "locked"
    config.max_num_iterations = args.iterations
    config.steps_per_save = args.iterations + 1
    config.steps_per_eval_batch = 0
    config.steps_per_eval_image = 0
    config.steps_per_eval_all_images = 0
    config.vis = "tensorboard"
    config.logging.local_writer.enable = False
    config.logging.profiler = "none"
    config.viewer.quit_on_train_completion = True
    config.pipeline.datamanager.train_num_rays_per_batch = args.rays_per_batch
    config.pipeline.datamanager.eval_num_rays_per_batch = args.rays_per_batch
    config.pipeline.datamanager.dataparser.data = args.input
    config.pipeline.datamanager.dataparser.orientation_method = "none"
    config.pipeline.datamanager.dataparser.center_method = "none"
    config.pipeline.datamanager.dataparser.auto_scale_poses = False
    config.pipeline.datamanager.dataparser.scale_factor = 1.0
    config.pipeline.datamanager.dataparser.scene_scale = 1.0
    config.pipeline.datamanager.dataparser.downscale_factor = 1
    config.pipeline.model.camera_optimizer.mode = "off"
    config.pipeline.model.use_appearance_embedding = False
    config.pipeline.model.disable_scene_contraction = True
    config.pipeline.model.near_plane = 0.1
    config.pipeline.model.far_plane = 6.0
    config.pipeline.model.collider_params = {"near_plane": 0.1, "far_plane": 6.0}
    config.pipeline.model.proposal_initial_sampler = "uniform"
    config.save_config()

    trainer = config.setup(local_rank=0, world_size=1)
    trainer.setup(test_mode="val")
    gates = _environment_gates(trainer)
    _write_json(args.output / "environment-gates.json", gates)
    training_started = time.perf_counter()
    trainer.train()
    training_seconds = time.perf_counter() - training_started
    trainer.pipeline.eval()

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

    density_thresholds = (0.1, 1.0, 10.0, 100.0)
    with (args.output / "failure_sweep.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["factor", "value", "measurement", "interpretation"],
        )
        writer.writeheader()
        for threshold in density_thresholds:
            writer.writerow(
                {
                    "factor": "density_threshold",
                    "value": threshold,
                    "measurement": float(np.mean(density_grid >= threshold)),
                    "interpretation": "occupied grid fraction; density has no canonical surface threshold",
                }
            )

    render_dir = args.output / "target-renders"
    render_dir.mkdir()
    target_metrics = []
    for frame in manifest["target_frames"]:
        camera = _target_camera(frame, manifest["intrinsics"])
        with torch.no_grad():
            outputs = trainer.pipeline.model.get_outputs_for_camera(camera)
        rgb_float = outputs["rgb"].detach().float().cpu().numpy()
        rgb = np.clip(rgb_float * 255.0, 0.0, 255.0).round().astype(np.uint8)
        accumulation = outputs["accumulation"].detach().float().cpu().numpy().squeeze(-1).astype(np.float32)
        median_ray_depth = outputs["depth"].detach()
        expected_ray_depth = outputs["expected_depth"].detach()
        camera_to_world = np.asarray(frame["camera_to_world_model"], dtype=np.float64)
        median_camera_depth = _camera_axis_depth(camera, median_ray_depth, camera_to_world)
        expected_camera_depth = _camera_axis_depth(camera, expected_ray_depth, camera_to_world)
        np.save(render_dir / f"{frame['id']}.rgb.npy", rgb, allow_pickle=False)
        np.save(render_dir / f"{frame['id']}.rgb.float32.npy", rgb_float.astype(np.float32), allow_pickle=False)
        np.save(render_dir / f"{frame['id']}.accumulation.npy", accumulation, allow_pickle=False)
        np.save(render_dir / f"{frame['id']}.median-camera-depth.npy", median_camera_depth, allow_pickle=False)
        np.save(render_dir / f"{frame['id']}.expected-camera-depth.npy", expected_camera_depth, allow_pickle=False)

        truth_rgb = np.load(args.input / frame["rgb_truth_path"], allow_pickle=False)
        batch = {"image": torch.from_numpy(truth_rgb.astype(np.float32) / 255.0).cuda()}
        with torch.no_grad():
            image_metrics, _ = trainer.pipeline.model.get_image_metrics_and_images(outputs, batch)
        target_metrics.append(
            {
                "id": frame["id"],
                "psnr_db": float(image_metrics["psnr"]),
                "ssim": float(image_metrics["ssim"]),
                "lpips": float(image_metrics["lpips"]),
            }
        )
    _write_json(args.output / "target-image-metrics.json", target_metrics)

    nerfstudio_commit = _source_commit(Path("/opt/src/nerfstudio"))
    tcnn_commit = _source_commit(Path("/opt/src/tiny-cuda-nn"))
    if nerfstudio_commit != NERFSTUDIO_COMMIT or tcnn_commit != TCNN_COMMIT:
        raise RuntimeError("installed source commit mismatch")
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
            "tf32": False,
            "seed": SEED,
        },
    )


if __name__ == "__main__":
    main()
