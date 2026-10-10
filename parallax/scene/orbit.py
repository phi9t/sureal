"""Deterministic textured-planes scene viewed by orbiting cameras."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from pipeline.contracts import canonical_json, sha256_file
from scene.ground_truth import export_ground_truth


FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class OrbitProfile:
    width: int
    height: int
    focal_px: float
    azimuth_degrees: tuple[float, ...]
    orbit_radius_m: float
    sample_stride_pixels: int


@dataclass(frozen=True)
class Plane:
    name: str
    z_m: float
    x_min_m: float
    x_max_m: float
    y_min_m: float
    y_max_m: float
    normal: tuple[float, float, float]
    texture_scale: float
    phase: float


ORBIT_PROFILES = {
    "smoke": OrbitProfile(
        width=64,
        height=48,
        focal_px=70.0,
        azimuth_degrees=(-15.0, 0.0, 15.0),
        orbit_radius_m=4.8,
        sample_stride_pixels=1,
    ),
    "full": OrbitProfile(
        width=128,
        height=96,
        focal_px=130.0,
        azimuth_degrees=(-24.0, -16.0, -8.0, 0.0, 8.0, 16.0, 24.0),
        orbit_radius_m=4.8,
        sample_stride_pixels=2,
    ),
}


def _planes() -> tuple[Plane, ...]:
    return (
        Plane(
            "background",
            -0.45,
            -8.0,
            8.0,
            -5.0,
            5.0,
            (0.0, 0.0, 1.0),
            8.0,
            0.0,
        ),
        Plane(
            "left-card",
            0.12,
            -1.55,
            -0.20,
            -0.78,
            0.62,
            (0.0, 0.0, 1.0),
            13.0,
            0.7,
        ),
        Plane(
            "right-card",
            0.38,
            0.16,
            1.62,
            -0.58,
            0.82,
            (0.0, 0.0, 1.0),
            11.0,
            1.9,
        ),
        Plane(
            "top-strip",
            0.22,
            -0.92,
            0.94,
            0.48,
            1.18,
            (0.0, 0.0, 1.0),
            17.0,
            2.8,
        ),
        Plane(
            "lower-tile",
            0.58,
            -0.62,
            0.72,
            -1.16,
            -0.44,
            (0.0, 0.0, 1.0),
            15.0,
            4.1,
        ),
    )


def _intrinsic_matrix(profile: OrbitProfile) -> FloatArray:
    return np.array(
        [
            [profile.focal_px, 0.0, (profile.width - 1.0) / 2.0],
            [0.0, profile.focal_px, (profile.height - 1.0) / 2.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )


def _camera_to_world(azimuth_degrees: float, radius: float) -> FloatArray:
    angle = np.deg2rad(float(azimuth_degrees))
    effective_radius = radius + 0.35 * np.sin(angle + 0.4)
    center = np.array(
        [effective_radius * np.sin(angle), 0.18, effective_radius * np.cos(angle)],
        dtype=np.float64,
    )
    target = np.array([0.0, 0.0, 0.12], dtype=np.float64)
    forward = target - center
    forward /= np.linalg.norm(forward)
    world_up = np.array([0.0, 1.0, 0.0], dtype=np.float64)
    right = np.cross(forward, world_up)
    right /= np.linalg.norm(right)
    down = np.cross(forward, right)
    transform = np.eye(4, dtype=np.float64)
    transform[:3, :3] = np.column_stack((right, down, forward))
    transform[:3, 3] = center
    return transform


def _texture(plane: Plane, x: FloatArray, y: FloatArray) -> NDArray[np.uint8]:
    scaled_x = (x - plane.x_min_m + plane.phase) * plane.texture_scale
    scaled_y = (y - plane.y_min_m - plane.phase) * plane.texture_scale
    checker = (
        np.floor(scaled_x * 0.65).astype(np.int64)
        + np.floor(scaled_y * 0.65).astype(np.int64)
    ) % 2
    value = (
        118.0
        + 48.0 * np.sin(scaled_x)
        + 36.0 * np.cos(1.37 * scaled_y)
        + 28.0 * checker
    )
    return np.clip(value, 0.0, 255.0).astype(np.uint8)


def _render_frame(
    profile: OrbitProfile,
    K: FloatArray,
    camera_to_world: FloatArray,
) -> tuple[NDArray[np.uint8], FloatArray, FloatArray]:
    columns, rows = np.meshgrid(
        np.arange(profile.width, dtype=np.float64),
        np.arange(profile.height, dtype=np.float64),
    )
    ray_camera = np.stack(
        (
            (columns - K[0, 2]) / K[0, 0],
            (rows - K[1, 2]) / K[1, 1],
            np.ones_like(columns),
        ),
        axis=-1,
    )
    rotation_camera_to_world = camera_to_world[:3, :3]
    ray_world = ray_camera @ rotation_camera_to_world.T
    center = camera_to_world[:3, 3]
    image = np.zeros((profile.height, profile.width), dtype=np.uint8)
    depth = np.full((profile.height, profile.width), np.inf, dtype=np.float64)
    normals = np.zeros((profile.height, profile.width, 3), dtype=np.float64)

    for plane in _planes():
        denominator = ray_world[..., 2]
        plane_depth = (plane.z_m - center[2]) / denominator
        x = center[0] + plane_depth * ray_world[..., 0]
        y = center[1] + plane_depth * ray_world[..., 1]
        hit = (
            (plane_depth > 0.0)
            & np.isfinite(plane_depth)
            & (x >= plane.x_min_m)
            & (x <= plane.x_max_m)
            & (y >= plane.y_min_m)
            & (y <= plane.y_max_m)
            & (plane_depth < depth)
        )
        image[hit] = _texture(plane, x[hit], y[hit])
        depth[hit] = plane_depth[hit]
        normals[hit] = np.asarray(plane.normal, dtype=np.float64)
    if np.any(~np.isfinite(depth)):
        raise ValueError("orbit scene planes do not cover the camera view")
    return image, depth, normals


def _tree_digest(root: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    paths = sorted(path for path in root.rglob("*") if path.is_file())
    for path in paths:
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return len(paths), digest.hexdigest()


def generate_orbit_scene(destination: Path, profile: str) -> dict[str, Any]:
    """Render one orbit profile and export exact per-view ground truth."""
    if profile not in ORBIT_PROFILES:
        raise ValueError(f"unknown orbit profile: {profile}")
    config = ORBIT_PROFILES[profile]
    K = _intrinsic_matrix(config)
    frames: list[dict[str, Any]] = []
    for azimuth in config.azimuth_degrees:
        camera_to_world = _camera_to_world(azimuth, config.orbit_radius_m)
        rotation = camera_to_world[:3, :3].T
        center = camera_to_world[:3, 3]
        translation = -rotation @ center
        image, depth, normals = _render_frame(config, K, camera_to_world)
        frames.append(
            {
                "azimuth_degrees": azimuth,
                "R_world_to_camera": rotation,
                "t_world_to_camera_m": translation,
                "camera_center_world_m": center,
                "image": image,
                "depth": depth,
                "normals": normals,
            }
        )
    scene = {
        "name": "orbit-textured-planes",
        "plane_count": len(_planes()),
        "planes": [plane.__dict__ for plane in _planes()],
        "camera_motion": "azimuth orbit with changing rotation and translation",
    }
    return export_ground_truth(
        Path(destination),
        profile=profile,
        width=config.width,
        height=config.height,
        K=K,
        frames=frames,
        sample_stride=config.sample_stride_pixels,
        scene=scene,
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--profile", choices=sorted(ORBIT_PROFILES), required=True)
    result.add_argument("--output", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    manifest = generate_orbit_scene(args.output, args.profile)
    artifact_count, artifact_tree_sha256 = _tree_digest(args.output)
    summary = {
        "profile": args.profile,
        "frame_count": len(manifest["frames"]),
        "surface_sample_count": manifest["surface_truth"]["sample_count"],
        "artifact_count": artifact_count,
        "artifact_tree_sha256": artifact_tree_sha256,
        "manifest_sha256": sha256_file(args.output / "manifest.json"),
    }
    print(canonical_json(summary).decode("ascii"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
