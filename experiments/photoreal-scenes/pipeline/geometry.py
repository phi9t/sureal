#!/usr/bin/env python3
"""Camera, sampling, and rendered-buffer geometry used by Blender and tests."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-12:
        raise ValueError("cannot normalize a zero-length vector")
    return vector / norm


def look_at_opencv(
    *,
    eye: np.ndarray,
    target: np.ndarray,
    width: int,
    height: int,
    fov_degrees: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Create +x-right, +y-down, +z-forward pinhole camera matrices."""
    eye = np.asarray(eye, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    forward = _normalize(target - eye)
    right = _normalize(np.cross(forward, np.asarray([0.0, 0.0, 1.0])))
    down = -_normalize(np.cross(right, forward))
    rotation = np.stack([right, down, forward], axis=0)
    translation = -(rotation @ eye)
    extrinsics = np.concatenate([rotation, translation[:, None]], axis=1)
    focal = 0.5 * float(width) / np.tan(np.deg2rad(fov_degrees) / 2.0)
    intrinsics = np.asarray(
        [
            [focal, 0.0, (width - 1.0) / 2.0],
            [0.0, focal, (height - 1.0) / 2.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    return intrinsics, extrinsics


def opencv_extrinsics_from_blender(matrix_world: np.ndarray) -> np.ndarray:
    """Convert a Blender camera world matrix to OpenCV world-to-camera."""
    matrix_world = np.asarray(matrix_world, dtype=np.float64)
    if matrix_world.shape != (4, 4):
        raise ValueError("Blender camera matrix_world must be 4x4")
    blender_world_to_camera = np.linalg.inv(matrix_world)
    blender_to_opencv = np.diag([1.0, -1.0, -1.0, 1.0])
    return (blender_to_opencv @ blender_world_to_camera)[:3]


def blender_matrix_from_opencv(extrinsics: np.ndarray) -> np.ndarray:
    """Convert OpenCV world-to-camera extrinsics to Blender matrix_world."""
    extrinsics = np.asarray(extrinsics, dtype=np.float64)
    if extrinsics.shape != (3, 4):
        raise ValueError("OpenCV extrinsics must be 3x4")
    opencv_world_to_camera = np.eye(4, dtype=np.float64)
    opencv_world_to_camera[:3] = extrinsics
    blender_to_opencv = np.diag([1.0, -1.0, -1.0, 1.0])
    return np.linalg.inv(blender_to_opencv @ opencv_world_to_camera)


def camera_center(extrinsics: np.ndarray) -> np.ndarray:
    extrinsics = np.asarray(extrinsics, dtype=np.float64)
    return -(extrinsics[:, :3].T @ extrinsics[:, 3])


def world_to_camera(points: np.ndarray, extrinsics: np.ndarray) -> np.ndarray:
    points = np.asarray(points, dtype=np.float64)
    extrinsics = np.asarray(extrinsics, dtype=np.float64)
    return points @ extrinsics[:, :3].T + extrinsics[:, 3]


def allocate_surface_samples(
    areas: np.ndarray, *, total: int, minimum: int
) -> np.ndarray:
    """Allocate an exact count with a minimum and area-weighted remainder."""
    areas = np.asarray(areas, dtype=np.float64)
    if areas.ndim != 1 or areas.size == 0:
        raise ValueError("areas must be a non-empty vector")
    if not np.all(np.isfinite(areas)) or np.any(areas < 0.0):
        raise ValueError("areas must be finite and non-negative")
    if total < minimum * areas.size:
        raise ValueError("total is too small for the per-object minimum")
    allocation = np.full(areas.size, int(minimum), dtype=np.int64)
    remainder = int(total - allocation.sum())
    weights = (
        areas / areas.sum()
        if float(areas.sum()) > 0.0
        else np.full(areas.size, 1.0 / areas.size)
    )
    raw = weights * remainder
    extras = np.floor(raw).astype(np.int64)
    allocation += extras
    left = int(total - allocation.sum())
    order = np.argsort(-(raw - extras), kind="stable")
    allocation[order[:left]] += 1
    return allocation


def visibility_from_buffers(
    points: np.ndarray,
    point_object_ids: np.ndarray,
    intrinsics: np.ndarray,
    extrinsics: np.ndarray,
    camera_depth: np.ndarray,
    object_ids: np.ndarray,
    *,
    scene_scale: float,
) -> np.ndarray:
    """Test first-surface visibility against rendered depth and object IDs."""
    points = np.asarray(points, dtype=np.float64)
    point_object_ids = np.asarray(point_object_ids, dtype=np.int64)
    camera_depth = np.asarray(camera_depth)
    object_ids = np.asarray(object_ids)
    height, width = camera_depth.shape
    camera_points = world_to_camera(points, extrinsics)
    z = camera_points[:, 2]
    safe_z = np.maximum(z, 1e-12)
    projected_x = intrinsics[0, 0] * camera_points[:, 0] / safe_z + intrinsics[0, 2]
    projected_y = intrinsics[1, 1] * camera_points[:, 1] / safe_z + intrinsics[1, 2]
    pixel_x = np.rint(projected_x).astype(np.int64)
    pixel_y = np.rint(projected_y).astype(np.int64)
    in_frame = (
        (z > 0.0)
        & (pixel_x >= 0)
        & (pixel_x < width)
        & (pixel_y >= 0)
        & (pixel_y < height)
    )
    visible = np.zeros(points.shape[0], dtype=bool)
    indices = np.flatnonzero(in_frame)
    if indices.size == 0:
        return visible
    rendered_depth = camera_depth[pixel_y[indices], pixel_x[indices]].astype(np.float64)
    rendered_ids = np.rint(object_ids[pixel_y[indices], pixel_x[indices]]).astype(np.int64)
    tolerance = np.maximum.reduce(
        [
            np.full(indices.size, 1e-5),
            # A sampled surface point and a pixel-center first hit are not
            # coincident at finite resolution.  The exact object-ID gate
            # prevents this scale-aware pixel-footprint tolerance from
            # leaking visibility across occluders.
            np.full(indices.size, abs(float(scene_scale)) * 2e-3),
            np.abs(rendered_depth) * 1e-4,
        ]
    )
    visible[indices] = (
        (rendered_depth > 0.0)
        & (rendered_ids == point_object_ids[indices])
        & (np.abs(rendered_depth - z[indices]) <= tolerance)
    )
    return visible


def visibility_from_views(
    points: np.ndarray,
    point_object_ids: np.ndarray,
    views: Iterable[
        tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]
    ],
    *,
    scene_scale: float,
) -> np.ndarray:
    visible = np.zeros(len(points), dtype=bool)
    for intrinsics, extrinsics, depth, object_ids in views:
        pending = np.flatnonzero(~visible)
        if pending.size == 0:
            break
        visible[pending] = visibility_from_buffers(
            np.asarray(points)[pending],
            np.asarray(point_object_ids)[pending],
            intrinsics,
            extrinsics,
            depth,
            object_ids,
            scene_scale=scene_scale,
        )
    return visible


def triangle_areas_and_normals(
    vertices: np.ndarray, triangles: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    vertices = np.asarray(vertices, dtype=np.float64)
    triangles = np.asarray(triangles, dtype=np.int64)
    edges_a = vertices[triangles[:, 1]] - vertices[triangles[:, 0]]
    edges_b = vertices[triangles[:, 2]] - vertices[triangles[:, 0]]
    cross = np.cross(edges_a, edges_b)
    lengths = np.linalg.norm(cross, axis=1)
    normals = np.zeros_like(cross)
    valid = lengths > 1e-15
    normals[valid] = cross[valid] / lengths[valid, None]
    return 0.5 * lengths, normals


def sample_triangle_surface(
    vertices: np.ndarray,
    triangles: np.ndarray,
    triangle_object_ids: np.ndarray,
    *,
    total: int,
    minimum: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Stratify by object and sample each object's triangles by world area."""
    areas, triangle_normals = triangle_areas_and_normals(vertices, triangles)
    object_ids = np.unique(np.asarray(triangle_object_ids, dtype=np.int32))
    object_areas = np.asarray(
        [areas[triangle_object_ids == object_id].sum() for object_id in object_ids]
    )
    counts = allocate_surface_samples(object_areas, total=total, minimum=minimum)
    rng = np.random.default_rng(seed)
    point_parts: list[np.ndarray] = []
    normal_parts: list[np.ndarray] = []
    id_parts: list[np.ndarray] = []
    for object_id, count in zip(object_ids, counts, strict=True):
        candidates = np.flatnonzero(triangle_object_ids == object_id)
        candidate_areas = areas[candidates]
        if float(candidate_areas.sum()) <= 0.0:
            raise ValueError(f"object {object_id} has no positive-area triangles")
        chosen = rng.choice(candidates, size=int(count), p=candidate_areas / candidate_areas.sum())
        triangle_vertices = vertices[triangles[chosen]]
        u = rng.random(int(count))
        v = rng.random(int(count))
        sqrt_u = np.sqrt(u)
        barycentric = np.stack(
            [1.0 - sqrt_u, sqrt_u * (1.0 - v), sqrt_u * v], axis=1
        )
        point_parts.append((triangle_vertices * barycentric[:, :, None]).sum(axis=1))
        normal_parts.append(triangle_normals[chosen])
        id_parts.append(np.full(int(count), object_id, dtype=np.int32))
    return (
        np.concatenate(point_parts).astype(np.float32),
        np.concatenate(normal_parts).astype(np.float32),
        np.concatenate(id_parts),
    )
