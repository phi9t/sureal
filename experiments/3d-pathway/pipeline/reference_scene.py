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


def _scene_textures(scene: dict[str, Any]) -> list[np.ndarray]:
    fixture = scene["reference_fixture"]
    count = int(fixture["texture_count"])
    if count < 2:
        raise ValueError("reference fixture requires background and tile textures")
    seed = int(scene["seed"])
    tile_size = int(fixture["tile_texture_size"])
    if tile_size <= 0:
        raise ValueError("tile texture size must be positive")
    return [_texture(seed)] + [_texture(seed + index, tile_size) for index in range(1, count)]


def _sample(texture: np.ndarray, x: np.ndarray, y: np.ndarray, scale: float) -> np.ndarray:
    height, width = texture.shape
    columns = np.mod(np.floor(x * scale).astype(np.int64), width)
    rows = np.mod(np.floor(y * scale).astype(np.int64), height)
    return texture[rows, columns]


def _render_with_depth(
    width: int,
    height: int,
    intrinsics: dict[str, float],
    fixture: dict[str, Any],
    camera_x: float,
    textures: list[np.ndarray],
) -> tuple[np.ndarray, np.ndarray]:
    tile_columns = len(fixture["tile_center_x_angles"])
    tile_rows = len(fixture["tile_center_y_angles"])
    if fixture.get("tile_texture_assignment") != "unique-per-tile":
        raise ValueError("reference fixture must assign unique appearance to every tile")
    if len(textures) != 1 + tile_columns * tile_rows:
        raise ValueError("reference fixture texture count does not cover every tile")
    columns, rows = np.meshgrid(np.arange(width), np.arange(height))
    ray_x = (columns - intrinsics["cx"]) / intrinsics["fx"]
    ray_y = (rows - intrinsics["cy"]) / intrinsics["fy"]
    background_depth = float(fixture["background_depth_m"])
    world_x = camera_x + ray_x * background_depth
    world_y = ray_y * background_depth
    image = _sample(textures[0], world_x, world_y, float(fixture["texture_scale_background"]))
    depth_map = np.full((height, width), background_depth, dtype=np.float32)

    # A nearly full-frame mosaic prevents the textured background from
    # dominating two-view estimation as one planar homography. Each tile is a
    # real fronto-parallel patch at a different depth, so motion produces
    # distributed parallax rather than a synthetic image-space warp.
    planes = []
    for row, center_y_angle in enumerate(fixture["tile_center_y_angles"]):
        for column, center_x_angle in enumerate(fixture["tile_center_x_angles"]):
            plane_depth = float(fixture["tile_depth_base_m"]) + float(fixture["tile_depth_step_m"]) * ((3 * row + 5 * column) % int(fixture["tile_depth_levels"]))
            half_width = float(fixture["tile_half_width_angle"]) * plane_depth
            half_height = float(fixture["tile_half_height_angle"]) * plane_depth
            center_x = center_x_angle * plane_depth
            center_y = center_y_angle * plane_depth
            texture_index = 1 + row * tile_columns + column
            planes.append((plane_depth, center_x - half_width, center_x + half_width, center_y - half_height, center_y + half_height, texture_index))
    for plane_depth, left, right, bottom, top, texture_index in sorted(planes, reverse=True):
        x = camera_x + ray_x * plane_depth
        y = ray_y * plane_depth
        mask = (x >= left) & (x <= right) & (y >= bottom) & (y <= top)
        sampled = _sample(textures[texture_index], x - left, y - bottom, float(fixture["texture_scale_tiles"]))
        image[mask] = sampled[mask]
        depth_map[mask] = plane_depth
    return image, depth_map


def _render(
    width: int,
    height: int,
    intrinsics: dict[str, float],
    fixture: dict[str, Any],
    camera_x: float,
    textures: list[np.ndarray],
) -> np.ndarray:
    image, _ = _render_with_depth(width, height, intrinsics, fixture, camera_x, textures)
    return image


def generate_colmap_scene(destination: Path, scene: dict[str, Any], profile: str) -> dict[str, Any]:
    """Write a small textured multi-depth scene that exercises real SfM."""
    image_dir = destination / "images"
    image_dir.mkdir(parents=True, exist_ok=False)
    intrinsics = scene["cameras"]["intrinsics"]
    fixture = scene["reference_fixture"]
    width, height = int(intrinsics["width"]), int(intrinsics["height"])
    camera_xs = fixture[f"camera_x_{profile}_m"]
    textures = _scene_textures(scene)
    K = [[float(intrinsics["fx"]), 0.0, float(intrinsics["cx"])], [0.0, float(intrinsics["fy"]), float(intrinsics["cy"])], [0.0, 0.0, 1.0]]
    rotation = [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]]
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


def _write_xyz_ply(path: Path, points: np.ndarray) -> None:
    header = (
        "ply\n"
        "format ascii 1.0\n"
        f"element vertex {len(points)}\n"
        "property float x\n"
        "property float y\n"
        "property float z\n"
        "end_header\n"
    )
    with path.open("w", encoding="ascii", newline="\n") as stream:
        stream.write(header)
        np.savetxt(stream, points, fmt="%.8g %.8g %.8g")


def _write_pgm(path: Path, image: np.ndarray) -> None:
    image = np.asarray(image)
    if image.ndim != 2 or image.dtype != np.uint8:
        raise ValueError("PGM images must be two-dimensional uint8 arrays")
    height, width = image.shape
    path.write_bytes(f"P5\n{width} {height}\n255\n".encode("ascii") + image.tobytes())


def _crop_and_resize_nearest(values: np.ndarray, scale: float) -> np.ndarray:
    """Center-crop by ``scale`` and map back to the original pixel lattice."""
    if values.ndim != 2 or not 0.0 < scale < 1.0:
        raise ValueError("focal stress requires a 2D input and a crop scale in (0, 1)")
    height, width = values.shape
    crop_height = int(round(height * scale))
    crop_width = int(round(width * scale))
    top = (height - crop_height) // 2
    left = (width - crop_width) // 2
    row_indices = top + np.minimum(
        (np.arange(height, dtype=np.int64) * crop_height) // height, crop_height - 1
    )
    column_indices = left + np.minimum(
        (np.arange(width, dtype=np.int64) * crop_width) // width, crop_width - 1
    )
    return values[np.ix_(row_indices, column_indices)]


def _concave_open_box(
    width: int, height: int, intrinsics: dict[str, float], seed: int
) -> tuple[np.ndarray, np.ndarray]:
    """Render a deterministic stepped recess used only as an OOD stressor."""
    columns, rows = np.meshgrid(np.arange(width), np.arange(height))
    ray_x = (columns - float(intrinsics["cx"])) / float(intrinsics["fx"])
    ray_y = (rows - float(intrinsics["cy"])) / float(intrinsics["fy"])
    outer = (np.abs(ray_x) <= 0.54) & (np.abs(ray_y) <= 0.40)
    opening = (np.abs(ray_x) <= 0.34) & (np.abs(ray_y) <= 0.24)

    depth = np.full((height, width), 6.0, dtype=np.float32)
    depth[outer] = 3.05
    depth[opening] = 5.20

    # The four bands are visible interior walls between the front rim and the
    # recessed back plane.  They make the case concave without defining any
    # truth behind an occluder.
    edge_distance = np.minimum(0.34 - np.abs(ray_x), 0.24 - np.abs(ray_y))
    wall = opening & (edge_distance < 0.055)
    wall_fraction = np.clip(edge_distance / 0.055, 0.0, 1.0)
    depth[wall] = (3.05 + 2.15 * wall_fraction[wall]).astype(np.float32)

    rng = np.random.default_rng(seed + 808)
    noise = rng.integers(0, 37, size=(height, width), dtype=np.uint8).astype(np.int16)
    world_x = ray_x * depth
    world_y = ray_y * depth
    texture = 112.0 + 48.0 * np.sin(world_x * 23.0) + 42.0 * np.cos(world_y * 31.0)
    image = np.clip(texture + noise, 0, 255).astype(np.uint8)
    image[outer & ~opening] = np.clip(image[outer & ~opening].astype(np.int16) + 35, 0, 255)
    image[opening] = np.clip(image[opening].astype(np.int16) - 30, 0, 255)
    return image.astype(np.uint8), depth


def generate_learned_depth_scene(
    destination: Path, scene: dict[str, Any], profile: str
) -> dict[str, Any]:
    """Write deterministic visible-ray inputs for the module 08 depth prior."""
    if profile not in {"smoke", "full"}:
        raise ValueError(f"unknown learned-depth profile: {profile}")
    image_dir = destination / "images"
    depth_dir = destination / "depth"
    image_dir.mkdir(parents=True, exist_ok=False)
    depth_dir.mkdir()
    intrinsics = scene["cameras"]["intrinsics"]
    fixture = scene["reference_fixture"]
    width, height = int(intrinsics["width"]), int(intrinsics["height"])
    all_camera_xs = fixture[f"camera_x_{profile}_m"]
    camera_xs = [all_camera_xs[len(all_camera_xs) // 2]] if profile == "smoke" else all_camera_xs
    textures = _scene_textures(scene)
    cases: list[dict[str, Any]] = []
    rendered: list[tuple[np.ndarray, np.ndarray]] = []

    def add_case(
        case_id: str,
        family: str,
        image: np.ndarray,
        depth: np.ndarray,
        extra: dict[str, Any] | None = None,
    ) -> None:
        image_path = image_dir / f"{case_id}.pgm"
        depth_path = depth_dir / f"{case_id}.depth.npy"
        _write_pgm(image_path, image)
        np.save(depth_path, np.asarray(depth, dtype=np.float32), allow_pickle=False)
        record: dict[str, Any] = {
            "id": case_id,
            "family": family,
            "image_path": image_path.relative_to(destination).as_posix(),
            "depth_path": depth_path.relative_to(destination).as_posix(),
            "image_sha256": sha256_file(image_path),
            "depth_sha256": sha256_file(depth_path),
            "width": width,
            "height": height,
            "truth_semantics": "camera-axis-depth-metres",
            "evaluation_support": "input-visible-pixels",
        }
        if extra:
            record.update(extra)
        cases.append(record)

    for index, camera_x in enumerate(camera_xs):
        image, depth = _render_with_depth(
            width, height, intrinsics, fixture, float(camera_x), textures
        )
        rendered.append((image, depth))
        add_case(
            f"shared-{index:03d}",
            "shared-scene",
            image,
            depth,
            {"camera_x_m": float(camera_x), "effective_focal_scale": 1.0},
        )

    crop_scale = 0.8
    center_image, center_depth = rendered[len(rendered) // 2]
    add_case(
        "focal-crop",
        "focal-crop",
        _crop_and_resize_nearest(center_image, crop_scale),
        _crop_and_resize_nearest(center_depth, crop_scale),
        {
            "source_case_id": cases[len(cases) // 2]["id"],
            "crop_scale": crop_scale,
            "effective_focal_scale": 1.0 / crop_scale,
        },
    )
    ood_image, ood_depth = _concave_open_box(width, height, intrinsics, int(scene["seed"]))
    add_case(
        "ood-concavity",
        "ood-concavity",
        ood_image,
        ood_depth,
        {"geometry": "concave-open-box", "effective_focal_scale": 1.0},
    )

    manifest = {
        "schema_version": 1,
        "profile": profile,
        "prediction_domain": "input-visible-pixels",
        "hidden_scene_truth": "not-defined",
        "case_families": ["shared-scene", "focal-crop", "ood-concavity"],
        "depth_units": "metres",
        "camera_depth_semantics": "positive camera-axis z",
        "intrinsics": {
            key: intrinsics[key] for key in ("width", "height", "fx", "fy", "cx", "cy")
        },
        "scene_seed": scene["seed"],
        "cases": cases,
    }
    (destination / "manifest.json").write_bytes(canonical_json(manifest))
    return manifest


def generate_colmap_mvs_scene(destination: Path, scene: dict[str, Any], profile: str) -> dict[str, Any]:
    """Add metric per-view depths and visible world-surface samples for MVS."""
    manifest = generate_colmap_scene(destination, scene, profile)
    fixture = scene["reference_fixture"]
    intrinsics = manifest["intrinsics"]
    width, height = int(intrinsics["width"]), int(intrinsics["height"])
    stride = int(fixture["ground_truth_sample_stride_pixels"])
    if stride <= 0:
        raise ValueError("ground-truth sample stride must be positive")
    textures = _scene_textures(scene)
    depth_dir = destination / "depth"
    depth_dir.mkdir()
    sample_columns, sample_rows = np.meshgrid(np.arange(0, width, stride), np.arange(0, height, stride))
    surface_parts: list[np.ndarray] = []
    camera_xs = fixture[f"camera_x_{profile}_m"]
    for frame, camera_x in zip(manifest["frames"], camera_xs):
        _, depth = _render_with_depth(width, height, intrinsics, fixture, float(camera_x), textures)
        depth_path = depth_dir / f"{Path(frame['name']).stem}.depth.npy"
        np.save(depth_path, depth, allow_pickle=False)
        frame["depth_name"] = depth_path.relative_to(destination).as_posix()
        frame["depth_sha256"] = sha256_file(depth_path)
        sampled_depth = depth[::stride, ::stride].astype(np.float64)
        camera_x_coordinate = float(camera_x) + (sample_columns - float(intrinsics["cx"])) / float(intrinsics["fx"]) * sampled_depth
        world_y = -(sample_rows - float(intrinsics["cy"])) / float(intrinsics["fy"]) * sampled_depth
        world_z = -sampled_depth
        surface_parts.append(np.column_stack((camera_x_coordinate.ravel(), world_y.ravel(), world_z.ravel())))
    visible_surface = np.concatenate(surface_parts, axis=0)
    truth_path = destination / "ground-truth-visible.ply"
    _write_xyz_ply(truth_path, visible_surface)
    manifest["ground_truth"] = {
        "units": "metres",
        "sample_stride_pixels": stride,
        "visible_surface": {
            "path": truth_path.name,
            "format": "ply-ascii-xyz",
            "vertex_count": int(len(visible_surface)),
            "sha256": sha256_file(truth_path),
        },
    }
    (destination / "scene-manifest.json").write_bytes(canonical_json(manifest))
    return manifest
