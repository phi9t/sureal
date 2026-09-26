"""Deterministic calibrated imagery for maintained reference adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from contracts import canonical_json, sha256_file


def _texture(seed: int, size: int = 1024) -> np.ndarray:
    rng = np.random.default_rng(seed)
    raw = rng.integers(0, 256, size=(size, size), dtype=np.uint16)
    smooth = sum(np.roll(np.roll(raw, y, axis=0), x, axis=1) for y in range(-2, 3) for x in range(-2, 3)) // 25
    return smooth.astype(np.uint8)


def _sample(texture: np.ndarray, x: np.ndarray, y: np.ndarray, scale: float) -> np.ndarray:
    height, width = texture.shape
    columns = np.mod(np.floor(x * scale).astype(np.int64), width)
    rows = np.mod(np.floor(y * scale).astype(np.int64), height)
    return texture[rows, columns]


def _render(width: int, height: int, intrinsics: dict[str, float], fixture: dict[str, Any], camera_x: float, textures: list[np.ndarray]) -> np.ndarray:
    columns, rows = np.meshgrid(np.arange(width), np.arange(height))
    ray_x = (columns - intrinsics["cx"]) / intrinsics["fx"]
    ray_y = (rows - intrinsics["cy"]) / intrinsics["fy"]
    background_depth = float(fixture["background_depth_m"])
    world_x = camera_x + ray_x * background_depth
    world_y = ray_y * background_depth
    image = _sample(textures[0], world_x, world_y, float(fixture["texture_scale_background"]))

    # A nearly full-frame mosaic prevents the textured background from
    # dominating two-view estimation as one planar homography. Each tile is a
    # real fronto-parallel patch at a different depth, so motion produces
    # distributed parallax rather than a synthetic image-space warp.
    planes = []
    for row, center_y_angle in enumerate(fixture["tile_center_y_angles"]):
        for column, center_x_angle in enumerate(fixture["tile_center_x_angles"]):
            depth = float(fixture["tile_depth_base_m"]) + float(fixture["tile_depth_step_m"]) * ((3 * row + 5 * column) % int(fixture["tile_depth_levels"]))
            half_width = float(fixture["tile_half_width_angle"]) * depth
            half_height = float(fixture["tile_half_height_angle"]) * depth
            center_x = center_x_angle * depth
            center_y = center_y_angle * depth
            planes.append((depth, center_x - half_width, center_x + half_width, center_y - half_height, center_y + half_height, 1 + (row + column) % 3))
    for depth, left, right, bottom, top, texture_index in sorted(planes, reverse=True):
        x = camera_x + ray_x * depth
        y = ray_y * depth
        mask = (x >= left) & (x <= right) & (y >= bottom) & (y <= top)
        sampled = _sample(textures[texture_index], x - left, y - bottom, float(fixture["texture_scale_tiles"]))
        image[mask] = sampled[mask]
    return image


def generate_colmap_scene(destination: Path, scene: dict[str, Any], profile: str) -> dict[str, Any]:
    """Write a small textured multi-depth scene that exercises real SfM."""
    image_dir = destination / "images"
    image_dir.mkdir(parents=True, exist_ok=False)
    intrinsics = scene["cameras"]["intrinsics"]
    fixture = scene["reference_fixture"]
    width, height = int(intrinsics["width"]), int(intrinsics["height"])
    camera_xs = fixture[f"camera_x_{profile}_m"]
    textures = [_texture(int(scene["seed"]) + index) for index in range(int(fixture["texture_count"]))]
    K = [[float(intrinsics["fx"]), 0.0, float(intrinsics["cx"])], [0.0, float(intrinsics["fy"]), float(intrinsics["cy"])], [0.0, 0.0, 1.0]]
    rotation = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    frames = []
    for index, camera_x in enumerate(camera_xs):
        image = _render(width, height, intrinsics, fixture, float(camera_x), textures)
        path = image_dir / f"frame-{index:03d}.pgm"
        path.write_bytes(f"P5\n{width} {height}\n255\n".encode("ascii") + image.tobytes())
        frames.append({
            "name": path.name,
            "K": K,
            "R_world_to_camera": rotation,
            "t_world_to_camera_m": [-float(camera_x), 0.0, 0.0],
            "camera_center_m": [float(camera_x), 0.0, 0.0],
            "sha256": sha256_file(path),
        })
    manifest = {
        "schema_version": 1,
        "profile": profile,
        "camera_model": "PINHOLE",
        "intrinsics": {key: intrinsics[key] for key in ("width", "height", "fx", "fy", "cx", "cy")},
        "world_frame": scene["world_frame"],
        "camera_frame": scene["camera_frame"],
        "fixture": fixture,
        "frames": frames,
        "scene_seed": scene["seed"],
    }
    (destination / "scene-manifest.json").write_bytes(canonical_json(manifest))
    return manifest
