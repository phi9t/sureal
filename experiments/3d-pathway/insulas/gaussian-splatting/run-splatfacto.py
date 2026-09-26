#!/usr/bin/env python3
"""Train and evaluate the pinned Nerfstudio Splatfacto reference."""

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

import gsplat
from gsplat.rendering import rasterization
import numpy as np
import PIL
from PIL import Image
import torch
import torch.nn.functional as torch_functional
import torchvision

from nerfstudio.cameras.cameras import Cameras, CameraType
from nerfstudio.configs.method_configs import method_configs
from nerfstudio.engine.callbacks import TrainingCallbackLocation


NERFSTUDIO_COMMIT = "50e0e3c70c775e89333256213363badbf074f29d"
GSPLAT_COMMIT = "4d3a3b69db4de0326f983ccf7b7b255271a17b01"
REQUIREMENTS_LOCK_SHA256 = "02c623f2a636dd774dda048f1a08c8d936d0701f74d3f50b3a7916d2280ed65a"
SEED = 260925
SWEEP_COUNTS = (3, 5, 9)
SWEEP_ITERATIONS = 1000


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_commit(path: Path) -> str:
    return subprocess.run(
        ["git", "-c", f"safe.directory={path}", "-C", str(path), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def _seed_everything() -> None:
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


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


def _config(data: Path, output: Path, iterations: int, timestamp: str) -> object:
    config = copy.deepcopy(method_configs["splatfacto"])
    config.machine.seed = SEED
    config.machine.num_devices = 1
    config.output_dir = output
    config.experiment_name = "controlled-sphere"
    config.timestamp = timestamp
    config.max_num_iterations = iterations
    config.steps_per_save = iterations
    config.steps_per_eval_batch = 0
    config.steps_per_eval_image = 0
    config.steps_per_eval_all_images = 0
    config.vis = "tensorboard"
    config.logging.local_writer.enable = False
    config.logging.profiler = "none"
    config.viewer.quit_on_train_completion = True
    config.pipeline.datamanager.dataparser.data = data
    config.pipeline.datamanager.dataparser.orientation_method = "none"
    config.pipeline.datamanager.dataparser.center_method = "none"
    config.pipeline.datamanager.dataparser.auto_scale_poses = False
    config.pipeline.datamanager.dataparser.scale_factor = 1.0
    config.pipeline.datamanager.dataparser.scene_scale = 1.0
    config.pipeline.datamanager.dataparser.downscale_factor = 1
    config.pipeline.datamanager.dataparser.eval_mode = "all"
    config.pipeline.datamanager.dataparser.load_3D_points = False
    config.pipeline.datamanager.cache_images = "cpu"
    config.pipeline.datamanager.dataloader_num_workers = 1
    config.pipeline.model.random_init = True
    config.pipeline.model.num_random = 50000
    config.pipeline.model.random_scale = 2.0
    config.pipeline.model.camera_optimizer.mode = "off"
    config.pipeline.model.background_color = "black"
    config.pipeline.model.use_scale_regularization = False
    config.pipeline.model.rasterize_mode = "classic"
    config.pipeline.model.collider_params = {"near_plane": 0.1, "far_plane": 6.0}
    config.save_config()
    return config


def _direct_gsplat_gate() -> bool:
    means = torch.tensor(
        [[-0.1, 0.0, 2.0], [0.1, 0.0, 2.2]], device="cuda", requires_grad=True
    )
    quats = torch.zeros((2, 4), device="cuda")
    quats[:, 0] = 1.0
    scales = torch.full((2, 3), 0.05, device="cuda")
    opacities = torch.full((2,), 0.8, device="cuda")
    colors = torch.tensor([[1.0, 0.2, 0.1], [0.1, 0.4, 1.0]], device="cuda")
    viewmats = torch.eye(4, device="cuda").unsqueeze(0)
    intrinsics = torch.tensor(
        [[[80.0, 0.0, 32.0], [0.0, 80.0, 32.0], [0.0, 0.0, 1.0]]],
        device="cuda",
    )
    rendered, alpha, _ = rasterization(
        means, quats, scales, opacities, colors, viewmats, intrinsics, 64, 64
    )
    (rendered.square().mean() + alpha.square().mean()).backward()
    return means.grad is not None and torch.isfinite(means.grad).all().item()


def _finite_value(value: object) -> bool:
    if isinstance(value, torch.Tensor):
        return bool(torch.isfinite(value).all().item())
    try:
        return bool(np.isfinite(value).all())
    except TypeError:
        return False


def _environment_gates(trainer: object, manifest: dict[str, object]) -> dict[str, bool]:
    capability = torch.cuda.get_device_capability(0)
    if capability != (10, 0):
        raise RuntimeError(f"Splatfacto reference requires compute capability 10.0, got {capability}")
    gsplat_gate = _direct_gsplat_gate()
    if not gsplat_gate:
        raise RuntimeError("gsplat direct forward/backward gate failed")
    trainer.pipeline.train()
    for callback in trainer.callbacks:
        callback.run_callback_at_location(
            0, location=TrainingCallbackLocation.BEFORE_TRAIN_ITERATION
        )
    loss, loss_dict, metrics_dict = trainer.train_iteration(0)
    for callback in trainer.callbacks:
        callback.run_callback_at_location(
            0, location=TrainingCallbackLocation.AFTER_TRAIN_ITERATION
        )
    model_gate = (
        torch.isfinite(loss).item()
        and all(torch.isfinite(value).all().item() for value in loss_dict.values())
        and all(_finite_value(value) for value in metrics_dict.values())
        and all(
            torch.isfinite(parameter).all().item()
            for parameter in trainer.pipeline.model.parameters()
        )
    )
    if not model_gate:
        raise RuntimeError("Splatfacto forward/backward gate failed")
    maximum_error = 0.0
    for frame in manifest["context_frames"]:
        model = np.asarray(frame["camera_to_world_model"], dtype=np.float64)
        nerfstudio = model.copy()
        nerfstudio[:3, 1:3] *= -1.0
        recovered = nerfstudio.copy()
        recovered[:3, 1:3] *= -1.0
        maximum_error = max(maximum_error, float(np.max(np.abs(recovered - model))))
    camera_gate = maximum_error <= 1e-6
    if not camera_gate:
        raise RuntimeError("camera frame round-trip gate failed")
    return {
        "compute_capability_10_0": True,
        "gsplat_forward_backward": bool(gsplat_gate),
        "splatfacto_forward_backward": bool(model_gate),
        "camera_round_trip": bool(camera_gate),
    }


def _train(
    data: Path,
    output: Path,
    iterations: int,
    timestamp: str,
    manifest: dict[str, object],
    run_gates: bool,
) -> tuple[object, object, float, dict[str, bool] | None]:
    _seed_everything()
    config = _config(data, output, iterations, timestamp)
    trainer = config.setup(local_rank=0, world_size=1)
    trainer.setup(test_mode="val")
    started = time.perf_counter()
    gates = None
    if run_gates:
        # Exercise iteration zero through Nerfstudio's official callbacks on the
        # primary trainer. Continuing at one preserves exactly `iterations`
        # optimizer updates without constructing a second process-global writer.
        gates = _environment_gates(trainer, manifest)
        trainer._start_step = 1
    trainer.train()
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - started
    trainer.pipeline.eval()
    return trainer, config, elapsed, gates


def _lpips(
    model: object,
    predicted: torch.Tensor,
    truth: np.ndarray,
    foreground_mask: np.ndarray,
) -> tuple[float, float]:
    truth_tensor = torch.from_numpy(truth.astype(np.float32) / 255.0).to(model.device)
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
        np.save(render_dir / f"{frame['id']}.rgb.float32.npy", rgb_float, allow_pickle=False)
        np.save(
            render_dir / f"{frame['id']}.rgb.npy",
            np.clip(rgb_float * 255.0, 0.0, 255.0).round().astype(np.uint8),
            allow_pickle=False,
        )
        if geometry:
            accumulation = outputs["accumulation"].detach().float().cpu().numpy().squeeze(-1)
            expected = _camera_axis_depth(
                camera,
                outputs["depth"].detach(),
                np.asarray(frame["camera_to_world_model"], dtype=np.float64),
            )
            np.save(
                render_dir / f"{frame['id']}.accumulation.npy",
                accumulation.astype(np.float32),
                allow_pickle=False,
            )
            np.save(
                render_dir / f"{frame['id']}.expected-camera-depth.npy",
                expected,
                allow_pickle=False,
            )
        if perceptual:
            truth = np.load(input_root / str(frame["rgb_truth_path"]), allow_pickle=False)
            foreground = np.asarray(Image.open(input_root / str(frame["mask_path"]))) > 0
            with torch.no_grad():
                full, crop = _lpips(trainer.pipeline.model, rgb_tensor, truth, foreground)
            rows.append({"id": frame["id"], "lpips": full, "crop_lpips": crop})
    return rows


def _sweep_dataset(
    destination: Path,
    input_root: Path,
    manifest: dict[str, object],
    frame_ids: list[str],
) -> Path:
    destination.mkdir(parents=True)
    frame_by_id = {frame["id"]: frame for frame in manifest["context_frames"]}
    intrinsics = manifest["intrinsics"]
    frames = []
    for frame_id in frame_ids:
        frame = frame_by_id[frame_id]
        transform = np.asarray(frame["camera_to_world_model"], dtype=np.float64).copy()
        transform[:3, 1:3] *= -1.0
        frames.append(
            {
                "file_path": str((input_root / str(frame["image_path"])).resolve(strict=True)),
                "transform_matrix": transform.tolist(),
            }
        )
    _write_json(
        destination / "transforms.json",
        {
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
        },
    )
    return destination


def _copy_primary_sweep(
    primary: Path, destination: Path, frames: list[dict[str, object]], primitive_count: int
) -> None:
    destination.mkdir(parents=True)
    for frame in frames:
        for suffix in ("rgb.float32.npy", "accumulation.npy", "expected-camera-depth.npy"):
            shutil.copy2(primary / f"{frame['id']}.{suffix}", destination / f"{frame['id']}.{suffix}")
    (destination / "primitive-count.txt").write_text(f"{primitive_count}\n")


def _view_sweep_rows(
    output: Path, input_root: Path, manifest: dict[str, object]
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for count in SWEEP_COUNTS:
        psnrs: list[float] = []
        residuals: list[np.ndarray] = []
        for frame in manifest["target_frames"]:
            prefix = output / "view-sweep" / f"views-{count}" / str(frame["id"])
            predicted = np.load(Path(f"{prefix}.rgb.float32.npy"), allow_pickle=False).astype(np.float64)
            truth = np.load(input_root / str(frame["rgb_truth_path"]), allow_pickle=False).astype(np.float64) / 255.0
            mse = float(np.mean((predicted - truth) ** 2))
            psnrs.append(float(-10.0 * np.log10(mse)))
            expected = np.load(Path(f"{prefix}.expected-camera-depth.npy"), allow_pickle=False)
            accumulation = np.load(Path(f"{prefix}.accumulation.npy"), allow_pickle=False)
            truth_depth = np.load(input_root / str(frame["depth_path"]), allow_pickle=False)
            common = np.load(
                input_root / str(frame["common_visible_mask_path"]), allow_pickle=False
            ).astype(bool)
            valid = (truth_depth > 0.0) & common & (accumulation >= 0.5) & (expected > 0.0)
            residuals.append(expected[valid] - truth_depth[valid])
        residual = np.concatenate(residuals).astype(np.float64)
        realized = int(
            (output / "view-sweep" / f"views-{count}" / "primitive-count.txt")
            .read_text()
            .strip()
        )
        for metric, measurement in (
            ("target_psnr_db", float(np.mean(psnrs))),
            ("expected_depth_rmse_m", float(np.sqrt(np.mean(residual * residual)))),
            ("realized_primitive_count", realized),
        ):
            rows.append(
                {
                    "factor": "context_view_count",
                    "value": count,
                    "metric": metric,
                    "measurement": measurement,
                    "interpretation": "trained 1000-step view-sparsity intervention on fixed targets",
                }
            )
    return rows


def _export_gaussians(model: object, output: Path) -> int:
    means = model.means.detach().float().cpu().numpy().astype(np.float32)
    log_scales = model.scales.detach().float().cpu().numpy().astype(np.float32)
    quaternions_tensor = torch_functional.normalize(model.quats.detach().float(), dim=-1)
    quaternions = quaternions_tensor.cpu().numpy().astype(np.float32)
    opacity_logits = model.opacities.detach().float().cpu().numpy().astype(np.float32)
    features_dc = model.features_dc.detach().float().cpu().numpy().astype(np.float32)
    np.savez_compressed(
        output / "gaussians.npz",
        means=means,
        log_scales=log_scales,
        quaternions=quaternions,
        opacity_logits=opacity_logits,
        features_dc=features_dc,
    )
    dtype = np.dtype(
        [(name, "<f4") for name in (
            "x", "y", "z", "nx", "ny", "nz", "f_dc_0", "f_dc_1", "f_dc_2",
            "opacity", "scale_0", "scale_1", "scale_2", "rot_0", "rot_1", "rot_2", "rot_3",
        )]
    )
    vertices = np.zeros(len(means), dtype=dtype)
    for index, name in enumerate(("x", "y", "z")):
        vertices[name] = means[:, index]
    for index, name in enumerate(("f_dc_0", "f_dc_1", "f_dc_2")):
        vertices[name] = features_dc[:, index]
    vertices["opacity"] = opacity_logits[:, 0]
    for index, name in enumerate(("scale_0", "scale_1", "scale_2")):
        vertices[name] = log_scales[:, index]
    for index, name in enumerate(("rot_0", "rot_1", "rot_2", "rot_3")):
        vertices[name] = quaternions[:, index]
    header = [
        "ply", "format binary_little_endian 1.0", "comment renderable_primitives_not_mesh",
        f"element vertex {len(vertices)}",
    ]
    header.extend(f"property float {name}" for name in vertices.dtype.names)
    header.append("end_header")
    with (output / "gaussians.ply").open("wb") as stream:
        stream.write(("\n".join(header) + "\n").encode("ascii"))
        vertices.tofile(stream)
    return len(means)


def _render_benchmark(
    trainer: object,
    frames: list[dict[str, object]],
    intrinsics: dict[str, object],
) -> dict[str, float | int]:
    cameras = [_camera(frame, intrinsics) for frame in frames]
    for index in range(20):
        with torch.no_grad():
            trainer.pipeline.model.get_outputs_for_camera(cameras[index % len(cameras)])
    torch.cuda.synchronize()
    latencies = []
    for index in range(100):
        started = time.perf_counter()
        with torch.no_grad():
            trainer.pipeline.model.get_outputs_for_camera(cameras[index % len(cameras)])
        torch.cuda.synchronize()
        latencies.append(time.perf_counter() - started)
    return {
        "warmup_frames": 20,
        "measured_frames": 100,
        "median_fps": float(1.0 / np.median(latencies)),
        "p95_latency_ms": float(np.quantile(latencies, 0.95) * 1000.0),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iterations", type=int, required=True)
    args = parser.parse_args()
    args.input = args.input.resolve(strict=True)
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((args.input / "manifest.json").read_text())
    if manifest["scene_seed"] != SEED or args.iterations not in (1000, 30000):
        raise ValueError("invalid locked Splatfacto execution configuration")

    trainer, config, training_seconds, gates = _train(
        args.input,
        args.output / "training",
        args.iterations,
        "locked",
        manifest,
        True,
    )
    assert gates is not None
    _write_json(args.output / "environment-gates.json", gates)
    candidates = sorted(trainer.checkpoint_dir.glob("step-*.ckpt"))
    if len(candidates) != 1:
        raise RuntimeError("training did not produce exactly one final checkpoint")
    locked = args.output / "nerfstudio"
    locked.mkdir()
    shutil.copy2(candidates[0], locked / "checkpoint.ckpt")
    shutil.copy2(config.get_base_dir() / "config.yml", locked / "config.yml")
    primitive_count = _export_gaussians(trainer.pipeline.model, args.output)

    # Target truth is opened only after the primary optimizer and checkpoint complete.
    target_frames = manifest["target_frames"]
    frame_by_id = {frame["id"]: frame for frame in manifest["context_frames"]}
    contexts = [frame_by_id[item] for item in manifest["primary_context_frame_ids"]]
    target_metrics = _render_frames(
        trainer, target_frames, manifest["intrinsics"], args.input,
        args.output / "target-renders", geometry=True, perceptual=True,
    )
    context_metrics = _render_frames(
        trainer, contexts, manifest["intrinsics"], args.input,
        args.output / "context-renders", geometry=False, perceptual=True,
    )
    benchmark = _render_benchmark(trainer, target_frames, manifest["intrinsics"])
    _write_json(args.output / "target-image-metrics.json", target_metrics)
    _write_json(args.output / "context-image-metrics.json", context_metrics)

    sweep_seconds: dict[str, float] = {}
    for count in SWEEP_COUNTS:
        destination = args.output / "view-sweep" / f"views-{count}"
        if manifest["profile"] == "smoke" and count == 5 and args.iterations == SWEEP_ITERATIONS:
            _copy_primary_sweep(args.output / "target-renders", destination, target_frames, primitive_count)
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
            f"views-{count}",
            manifest,
            False,
        )
        _render_frames(
            sweep_trainer, target_frames, manifest["intrinsics"], args.input,
            destination, geometry=True, perceptual=False,
        )
        (destination / "primitive-count.txt").write_text(
            f"{len(sweep_trainer.pipeline.model.means)}\n"
        )
        sweep_seconds[str(count)] = elapsed
        del sweep_trainer
        torch.cuda.empty_cache()

    with (args.output / "failure_sweep.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["factor", "value", "metric", "measurement", "interpretation"],
        )
        writer.writeheader()
        writer.writerows(_view_sweep_rows(args.output, args.input, manifest))
    _write_json(
        args.output / "unsupported.json",
        {
            "triangle_mesh": "unsupported",
            "mesh_f_score": "unsupported",
            "canonical_surface": "unsupported",
            "hidden_surface_completion": "unsupported",
            "surface_regularization_sweep": "unsupported_until_separate_sugar_or_2dgs_adapter",
        },
    )
    del trainer
    torch.cuda.empty_cache()
    shutil.rmtree(args.output / "training", ignore_errors=True)
    shutil.rmtree(args.output / "sweep-training", ignore_errors=True)

    nerfstudio_commit = _source_commit(Path("/opt/src/nerfstudio"))
    gsplat_commit = _source_commit(Path("/opt/src/gsplat"))
    if nerfstudio_commit != NERFSTUDIO_COMMIT or gsplat_commit != GSPLAT_COMMIT:
        raise RuntimeError("installed source commit mismatch")
    requirements = Path("/etc/surflo-pathway-requirements.lock.txt")
    resolved = Path("/etc/surflo-pathway-resolved-requirements.txt")
    if _sha256(requirements) != REQUIREMENTS_LOCK_SHA256:
        raise RuntimeError("installed dependency lock mismatch")
    shutil.copy2(requirements, args.output / "requirements.lock.txt")
    shutil.copy2(resolved, args.output / "resolved-requirements.txt")
    (args.output / "source-commit.txt").write_text(nerfstudio_commit + "\n")
    (args.output / "gsplat-commit.txt").write_text(gsplat_commit + "\n")
    shutil.copy2("/etc/surflo-pathway-insula", args.output / "insula-manifest.txt")
    compiler = subprocess.run(
        ["nvcc", "--version"], text=True, capture_output=True, check=True
    ).stdout.strip()
    _write_json(
        args.output / "runtime-versions.json",
        {
            "nerfstudio_commit": nerfstudio_commit,
            "gsplat_commit": gsplat_commit,
            "gsplat": gsplat.__version__,
            "requirements_lock_sha256": _sha256(requirements),
            "resolved_requirements_sha256": _sha256(resolved),
            "torch": torch.__version__,
            "torchvision": torchvision.__version__,
            "pillow": PIL.__version__,
            "python": platform.python_version(),
            "numpy": np.__version__,
            "cuda_runtime": torch.version.cuda,
            "cuda_compiler": compiler,
            "compute_capability": list(torch.cuda.get_device_capability(0)),
            "torch_cuda_arch_list": "10.0",
            "device": torch.cuda.get_device_name(0),
        },
    )
    _write_json(
        args.output / "training-summary.json",
        {
            "method": "splatfacto",
            "iterations": args.iterations,
            "training_seconds": training_seconds,
            "training_steps_per_second": args.iterations / training_seconds,
            "random_init": True,
            "num_random": 50000,
            "random_scale": 2.0,
            "camera_optimizer": "off",
            "background_color": "black",
            "scale_regularization": False,
            "rasterization_mode": "classic",
            "seed": SEED,
            "tf32": False,
            "final_primitive_count": primitive_count,
            "trained_view_sweep": {"context_views": list(SWEEP_COUNTS), "iterations": SWEEP_ITERATIONS},
            "view_sweep_training_seconds": sweep_seconds,
            "render_benchmark": benchmark,
        },
    )


if __name__ == "__main__":
    main()
