#!/usr/bin/env python3
"""Train, query, extract, and render the pinned NeuS-Facto reference."""

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
from skimage import measure
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


def _query_sdf(field: torch.nn.Module, points: np.ndarray, batch: int = 262144) -> np.ndarray:
    values = np.empty(len(points), dtype=np.float32)
    field.eval()
    with torch.no_grad():
        for start in range(0, len(points), batch):
            sample = torch.from_numpy(points[start : start + batch]).cuda()
            values[start : start + len(sample)] = (
                field.forward_geonetwork(sample)[:, 0].detach().float().cpu().numpy()
            )
    return values


def _query_grid(field: torch.nn.Module, resolution: int) -> np.ndarray:
    axis = np.linspace(-1.0, 1.0, resolution, dtype=np.float32)
    grid = np.empty((resolution, resolution, resolution), dtype=np.float32)
    slab = max(1, min(8, 524288 // (resolution * resolution)))
    for start in range(0, resolution, slab):
        xx, yy, zz = np.meshgrid(axis[start : start + slab], axis, axis, indexing="ij")
        points = np.stack((xx, yy, zz), axis=-1).reshape(-1, 3)
        grid[start : start + len(xx)] = _query_sdf(field, points).reshape(xx.shape)
    return grid


def _point_gradients(field: torch.nn.Module, points: np.ndarray, batch: int = 65536) -> np.ndarray:
    gradients = np.empty_like(points, dtype=np.float32)
    field.eval()
    for start in range(0, len(points), batch):
        sample = torch.from_numpy(points[start : start + batch]).cuda().requires_grad_(True)
        sdf = field.forward_geonetwork(sample)[:, 0]
        gradient = torch.autograd.grad(sdf.sum(), sample, create_graph=False)[0]
        gradients[start : start + len(sample)] = gradient.detach().float().cpu().numpy()
    return gradients


def _extract(field: torch.nn.Module, resolution: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    grid = _query_grid(field, resolution)
    vertices, faces, _, _ = measure.marching_cubes(
        grid,
        level=0.0,
        spacing=(2.0 / (resolution - 1),) * 3,
        allow_degenerate=False,
    )
    vertices = vertices.astype(np.float32) - np.float32(1.0)
    gradients = _point_gradients(field, vertices)
    lengths = np.linalg.norm(gradients, axis=1, keepdims=True)
    if not np.isfinite(lengths).all() or np.any(lengths <= 0.0):
        raise RuntimeError("non-finite or zero SDF gradients at extracted vertices")
    # The pinned NeuS field uses positive-inside SDFs, so its gradient points
    # inward. Export the conventional outward-oriented surface normal.
    normals = (-gradients / lengths).astype(np.float32)
    return grid, vertices, normals, faces.astype(np.int32)


def _write_ply(path: Path, points: np.ndarray, normals: np.ndarray, faces: np.ndarray) -> None:
    with path.open("w", encoding="ascii", newline="\n") as stream:
        stream.write(
            "ply\nformat ascii 1.0\n"
            f"element vertex {len(points)}\n"
            "property float x\nproperty float y\nproperty float z\n"
            "property float nx\nproperty float ny\nproperty float nz\n"
            f"element face {len(faces)}\n"
            "property list uchar int vertex_indices\nend_header\n"
        )
        np.savetxt(stream, np.concatenate((points, normals), axis=1), fmt="%.8g")
        for face in faces:
            stream.write(f"3 {int(face[0])} {int(face[1])} {int(face[2])}\n")


def _environment_gates(trainer: object) -> dict[str, bool]:
    capability = torch.cuda.get_device_capability(0)
    if capability != (10, 0):
        raise RuntimeError(f"NeuS-Facto reference requires compute capability 10.0, got {capability}")

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
    loss = sum(loss_dict.values())
    loss.backward()
    gradients = [
        parameter.grad
        for parameter in trainer.pipeline.model.parameters()
        if parameter.grad is not None
    ]
    neus_gate = bool(gradients) and all(torch.isfinite(value).all().item() for value in gradients)
    trainer.optimizers.zero_grad_all()
    if not neus_gate:
        raise RuntimeError("NeuS-Facto forward/backward gate failed")

    initial_grid = _query_grid(trainer.pipeline.model.field, 32)
    extracted = measure.marching_cubes(initial_grid, level=0.0, allow_degenerate=False)
    extraction_gate = len(extracted[0]) > 0 and len(extracted[1]) > 0
    if not extraction_gate:
        raise RuntimeError("32-cube SDF extraction gate failed")
    return {
        "compute_capability_10_0": True,
        "tcnn_forward_backward": bool(tcnn_gate),
        "neus_facto_forward_backward": bool(neus_gate),
        "sdf_extraction_32": bool(extraction_gate),
    }


def _target_camera(frame: dict[str, object], intrinsics: dict[str, object]) -> Cameras:
    c2w = np.asarray(frame["camera_to_world_model"], dtype=np.float32).copy()
    c2w[:3, 1:3] *= -1.0
    return Cameras(
        fx=float(intrinsics["fx"]),
        fy=float(intrinsics["fy"]),
        cx=float(intrinsics["cx"]),
        cy=float(intrinsics["cy"]),
        height=int(intrinsics["height"]),
        width=int(intrinsics["width"]),
        camera_to_worlds=torch.from_numpy(c2w[:3, :4]).unsqueeze(0),
        camera_type=CameraType.PERSPECTIVE,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iterations", type=int, required=True)
    parser.add_argument("--rays-per-batch", type=int, required=True)
    parser.add_argument("--extraction-resolution", type=int, required=True)
    args = parser.parse_args()
    args.input = args.input.resolve(strict=True)
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((args.input / "manifest.json").read_text())
    if manifest["scene_seed"] != SEED or args.iterations <= 0 or args.rays_per_batch <= 0:
        raise ValueError("invalid locked NeuS-Facto execution configuration")

    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

    config = copy.deepcopy(method_configs["neus-facto"])
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
    config.pipeline.datamanager.dataparser.include_mono_prior = False
    config.pipeline.datamanager.dataparser.include_foreground_mask = False
    config.pipeline.datamanager.dataparser.downscale_factor = 1
    config.pipeline.datamanager.dataparser.auto_orient = False
    config.pipeline.model.eval_num_rays_per_chunk = 4096
    config.pipeline.model.sdf_field.inside_outside = True
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

    extraction_started = time.perf_counter()
    grid, vertices, normals, faces = _extract(
        trainer.pipeline.model.field, args.extraction_resolution
    )
    extraction_seconds = time.perf_counter() - extraction_started
    np.save(args.output / "field.sdf_grid.float32.npy", grid.astype(np.float32), allow_pickle=False)
    np.savez(args.output / "mesh.npz", points=vertices, normals=normals, faces=faces)
    _write_ply(args.output / "mesh.ply", vertices, normals, faces)

    rng = np.random.default_rng(SEED)
    field_samples = rng.uniform(-1.0, 1.0, size=(4096, 3)).astype(np.float32)
    gradient_norms = np.linalg.norm(
        _point_gradients(trainer.pipeline.model.field, field_samples), axis=1
    ).astype(np.float32)
    np.save(args.output / "field.gradient_norms.float32.npy", gradient_norms, allow_pickle=False)

    render_dir = args.output / "target-renders"
    render_dir.mkdir()
    for frame in manifest["target_frames"]:
        camera = _target_camera(frame, manifest["intrinsics"])
        with torch.no_grad():
            outputs = trainer.pipeline.model.get_outputs_for_camera(camera)
        rgb = np.clip(outputs["rgb"].detach().float().cpu().numpy() * 255.0, 0.0, 255.0).round().astype(np.uint8)
        depth = outputs["depth"].detach().float().cpu().numpy().squeeze(-1).astype(np.float32)
        normal = outputs["normal"].detach().float().cpu().numpy().astype(np.float32)
        np.save(render_dir / f"{frame['id']}.rgb.npy", rgb, allow_pickle=False)
        np.save(render_dir / f"{frame['id']}.depth.npy", depth, allow_pickle=False)
        np.save(render_dir / f"{frame['id']}.normal.npy", normal, allow_pickle=False)

    sweep_resolutions = sorted({64, min(128, args.extraction_resolution), args.extraction_resolution})
    with (args.output / "failure_sweep.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["factor", "value", "image_supported", "interpretation"],
        )
        writer.writeheader()
        for resolution in sweep_resolutions:
            if resolution == args.extraction_resolution:
                surface_grid = grid
            else:
                surface_grid = _query_grid(trainer.pipeline.model.field, resolution)
            sweep_vertices, sweep_faces, _, _ = measure.marching_cubes(
                surface_grid, level=0.0, allow_degenerate=False
            )
            writer.writerow(
                {
                    "factor": "extraction_resolution",
                    "value": resolution,
                    "image_supported": "true",
                    "interpretation": f"vertices={len(sweep_vertices)};faces={len(sweep_faces)}",
                }
            )
        writer.writerow(
            {
                "factor": "hidden_counterfactual",
                "value": "sphere-vs-box",
                "image_supported": "false",
                "interpretation": "identical context evidence cannot select an unseen object",
            }
        )

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
            "method": "neus-facto",
            "iterations": args.iterations,
            "rays_per_batch": args.rays_per_batch,
            "extraction_resolution": args.extraction_resolution,
            "training_seconds": training_seconds,
            "training_steps_per_second": args.iterations / training_seconds,
            "extraction_seconds": extraction_seconds,
            "mesh_vertices": len(vertices),
            "mesh_faces": len(faces),
            "camera_optimizer": "off",
            "mono_prior": False,
            "inside_outside": True,
            "tf32": False,
            "seed": SEED,
        },
    )


if __name__ == "__main__":
    main()
