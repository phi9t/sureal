"""Ground-truth export helpers for deterministic Parallax scenes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from camera.pinhole import unproject
from pipeline.contracts import canonical_json, sha256_file


FloatArray = NDArray[np.float64]


def _write_pgm(path: Path, image: np.ndarray) -> None:
    image = np.asarray(image)
    if image.ndim != 2 or image.dtype != np.uint8:
        raise ValueError("PGM images must be two-dimensional uint8 arrays")
    height, width = image.shape
    path.write_bytes(f"P5\n{width} {height}\n255\n".encode("ascii") + image.tobytes())


def surface_samples_from_depth(
    depth: ArrayLike,
    normals: ArrayLike,
    K: ArrayLike,
    R: ArrayLike,
    t: ArrayLike,
    *,
    stride: int = 1,
) -> tuple[FloatArray, FloatArray]:
    """Back-project valid depth pixels into world points with world normals."""
    if stride <= 0:
        raise ValueError("sample stride must be positive")
    depth_map = np.asarray(depth, dtype=np.float64)
    normal_map = np.asarray(normals, dtype=np.float64)
    if depth_map.ndim != 2:
        raise ValueError("depth must have shape (H, W)")
    if normal_map.shape != depth_map.shape + (3,):
        raise ValueError("normals must have shape (H, W, 3)")
    rows, columns = np.meshgrid(
        np.arange(0, depth_map.shape[0], stride, dtype=np.float64),
        np.arange(0, depth_map.shape[1], stride, dtype=np.float64),
        indexing="ij",
    )
    sampled_depth = depth_map[::stride, ::stride].reshape(-1)
    sampled_normals = normal_map[::stride, ::stride].reshape(-1, 3)
    valid = (
        np.isfinite(sampled_depth)
        & (sampled_depth > 0.0)
        & np.all(np.isfinite(sampled_normals), axis=1)
    )
    pixels = np.column_stack((columns.reshape(-1), rows.reshape(-1)))[valid]
    points = unproject(pixels, sampled_depth[valid], K, R, t)
    unit_normals = sampled_normals[valid]
    lengths = np.linalg.norm(unit_normals, axis=1, keepdims=True)
    if np.any(lengths == 0.0):
        raise ValueError("surface normals must be non-zero")
    return points, unit_normals / lengths


def export_ground_truth(
    destination: Path,
    *,
    profile: str,
    width: int,
    height: int,
    K: ArrayLike,
    frames: list[dict[str, Any]],
    sample_stride: int,
    scene: dict[str, Any],
) -> dict[str, Any]:
    """Write images, poses, depth maps and dense visible-surface samples."""
    destination.mkdir(parents=True, exist_ok=True)
    image_dir = destination / "images"
    depth_dir = destination / "depth"
    normal_dir = destination / "normals"
    surface_dir = destination / "surface"
    for directory in (image_dir, depth_dir, normal_dir, surface_dir):
        directory.mkdir(parents=True, exist_ok=False)

    intrinsic = np.asarray(K, dtype=np.float64)
    manifest_frames: list[dict[str, Any]] = []
    surface_parts: list[FloatArray] = []
    normal_parts: list[FloatArray] = []
    for index, frame in enumerate(frames):
        frame_id = f"frame-{index:03d}"
        image = np.asarray(frame["image"], dtype=np.uint8)
        depth = np.asarray(frame["depth"], dtype=np.float32)
        normals = np.asarray(frame["normals"], dtype=np.float32)
        rotation = np.asarray(frame["R_world_to_camera"], dtype=np.float64)
        translation = np.asarray(frame["t_world_to_camera_m"], dtype=np.float64)
        center = np.asarray(frame["camera_center_world_m"], dtype=np.float64)

        image_path = image_dir / f"{frame_id}.pgm"
        depth_path = depth_dir / f"{frame_id}.depth.npy"
        normal_path = normal_dir / f"{frame_id}.normal.npy"
        points_path = surface_dir / f"{frame_id}.points.npy"
        normals_path = surface_dir / f"{frame_id}.normals.npy"
        _write_pgm(image_path, image)
        np.save(depth_path, depth, allow_pickle=False)
        np.save(normal_path, normals, allow_pickle=False)
        surface_points, surface_normals = surface_samples_from_depth(
            depth,
            normals,
            intrinsic,
            rotation,
            translation,
            stride=sample_stride,
        )
        np.save(points_path, surface_points, allow_pickle=False)
        np.save(normals_path, surface_normals.astype(np.float32), allow_pickle=False)
        surface_parts.append(surface_points)
        normal_parts.append(surface_normals)
        manifest_frames.append(
            {
                "id": frame_id,
                "azimuth_degrees": float(frame["azimuth_degrees"]),
                "K": intrinsic.tolist(),
                "R_world_to_camera": rotation.tolist(),
                "t_world_to_camera_m": translation.tolist(),
                "camera_center_world_m": center.tolist(),
                "image_path": image_path.relative_to(destination).as_posix(),
                "depth_path": depth_path.relative_to(destination).as_posix(),
                "normal_path": normal_path.relative_to(destination).as_posix(),
                "surface_points_path": points_path.relative_to(
                    destination
                ).as_posix(),
                "surface_normals_path": normals_path.relative_to(
                    destination
                ).as_posix(),
                "image_sha256": sha256_file(image_path),
                "depth_sha256": sha256_file(depth_path),
                "normal_sha256": sha256_file(normal_path),
                "surface_points_sha256": sha256_file(points_path),
                "surface_normals_sha256": sha256_file(normals_path),
                "surface_sample_count": int(len(surface_points)),
            }
        )

    all_points = np.concatenate(surface_parts, axis=0)
    all_normals = np.concatenate(normal_parts, axis=0)
    truth_points_path = surface_dir / "points.npy"
    truth_normals_path = surface_dir / "normals.npy"
    np.save(truth_points_path, all_points, allow_pickle=False)
    np.save(truth_normals_path, all_normals.astype(np.float32), allow_pickle=False)

    manifest = {
        "schema_version": 1,
        "profile": profile,
        "scene": scene,
        "intrinsics": {
            "width": int(width),
            "height": int(height),
            "K": intrinsic.tolist(),
            "depth_semantics": "positive camera-axis z in metres",
        },
        "world_frame": "right-handed: +x right, +y up, +z toward the viewer",
        "camera_frame": "OpenCV: +x right, +y down, +z forward",
        "frames": manifest_frames,
        "surface_truth": {
            "points_path": truth_points_path.relative_to(destination).as_posix(),
            "normals_path": truth_normals_path.relative_to(destination).as_posix(),
            "points_sha256": sha256_file(truth_points_path),
            "normals_sha256": sha256_file(truth_normals_path),
            "sample_count": int(len(all_points)),
            "units": "metres",
            "sample_stride_pixels": int(sample_stride),
            "semantics": "union of per-view visible surface samples",
        },
    }
    (destination / "manifest.json").write_bytes(canonical_json(manifest))
    return manifest
