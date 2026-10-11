"""Cross-view depth-map consistency filters."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]


def _depth_map(value: ArrayLike) -> FloatArray:
    depth = np.asarray(value, dtype=np.float64)
    if depth.ndim != 2:
        raise ValueError("depth maps must have shape HxW")
    return depth


def _pixel_grid(height: int, width: int) -> tuple[FloatArray, FloatArray]:
    rows, columns = np.meshgrid(
        np.arange(height, dtype=np.float64),
        np.arange(width, dtype=np.float64),
        indexing="ij",
    )
    return rows, columns


def _bilinear_sample(image: ArrayLike, columns: ArrayLike, rows: ArrayLike) -> tuple[FloatArray, NDArray[np.bool_]]:
    values = np.asarray(image, dtype=np.float64)
    sample_columns = np.asarray(columns, dtype=np.float64)
    sample_rows = np.asarray(rows, dtype=np.float64)
    height, width = values.shape
    valid = (
        np.isfinite(sample_columns)
        & np.isfinite(sample_rows)
        & (sample_columns >= 0.0)
        & (sample_rows >= 0.0)
        & (sample_columns <= width - 1.0)
        & (sample_rows <= height - 1.0)
    )
    column0 = np.floor(np.clip(sample_columns, 0.0, width - 1.0)).astype(np.int64)
    row0 = np.floor(np.clip(sample_rows, 0.0, height - 1.0)).astype(np.int64)
    column1 = np.minimum(column0 + 1, width - 1)
    row1 = np.minimum(row0 + 1, height - 1)
    column_weight = np.clip(sample_columns - column0, 0.0, 1.0)
    row_weight = np.clip(sample_rows - row0, 0.0, 1.0)
    top = (1.0 - column_weight) * values[row0, column0] + column_weight * values[row0, column1]
    bottom = (1.0 - column_weight) * values[row1, column0] + column_weight * values[row1, column1]
    sampled = (1.0 - row_weight) * top + row_weight * bottom
    valid &= np.isfinite(sampled)
    return sampled, valid


def _world_points(view: Any, depth: FloatArray) -> tuple[FloatArray, NDArray[np.bool_]]:
    height, width = depth.shape
    rows, columns = _pixel_grid(height, width)
    finite = np.isfinite(depth) & (depth > 0.0)
    intrinsic_inverse = np.linalg.inv(np.asarray(view.K, dtype=np.float64))
    pixels = np.stack((columns, rows, np.ones_like(columns)), axis=-1).reshape(-1, 3)
    rays = (intrinsic_inverse @ pixels.T).T.reshape(height, width, 3)
    camera = rays * depth[..., None]
    rotation = np.asarray(view.R_world_to_camera, dtype=np.float64)
    translation = np.asarray(view.t_world_to_camera_m, dtype=np.float64)
    world = (rotation.T @ (camera.reshape(-1, 3) - translation).T).T.reshape(height, width, 3)
    return world, finite


def _world_from_pixels(view: Any, columns: FloatArray, rows: FloatArray, depth: FloatArray) -> FloatArray:
    intrinsic_inverse = np.linalg.inv(np.asarray(view.K, dtype=np.float64))
    pixels = np.stack((columns, rows, np.ones_like(columns)), axis=-1).reshape(-1, 3)
    rays = (intrinsic_inverse @ pixels.T).T.reshape(depth.shape + (3,))
    camera = rays * depth[..., None]
    rotation = np.asarray(view.R_world_to_camera, dtype=np.float64)
    translation = np.asarray(view.t_world_to_camera_m, dtype=np.float64)
    return (rotation.T @ (camera.reshape(-1, 3) - translation).T).T.reshape(depth.shape + (3,))


def _project(view: Any, world: FloatArray) -> tuple[FloatArray, FloatArray, FloatArray]:
    rotation = np.asarray(view.R_world_to_camera, dtype=np.float64)
    translation = np.asarray(view.t_world_to_camera_m, dtype=np.float64)
    intrinsic = np.asarray(view.K, dtype=np.float64)
    camera = (rotation @ world.reshape(-1, 3).T).T + translation
    homogeneous = (intrinsic @ camera.T).T
    columns = (homogeneous[:, 0] / homogeneous[:, 2]).reshape(world.shape[:2])
    rows = (homogeneous[:, 1] / homogeneous[:, 2]).reshape(world.shape[:2])
    depth = camera[:, 2].reshape(world.shape[:2])
    return columns, rows, depth


def consistent_depth_mask(
    reference: Any,
    neighbour: Any,
    reference_depth: ArrayLike,
    neighbour_depth: ArrayLike,
    *,
    pixel_tolerance: float = 1.0,
    relative_depth_tolerance: float = 0.03,
) -> NDArray[np.bool_]:
    """Return reference pixels that reproject consistently into ``neighbour``."""
    if pixel_tolerance <= 0.0:
        raise ValueError("pixel_tolerance must be positive")
    if relative_depth_tolerance <= 0.0:
        raise ValueError("relative_depth_tolerance must be positive")
    reference_map = _depth_map(reference_depth)
    neighbour_map = _depth_map(neighbour_depth)
    if reference_map.shape != np.asarray(reference.image).shape:
        raise ValueError("reference depth shape must match the reference image")
    if neighbour_map.shape != np.asarray(neighbour.image).shape:
        raise ValueError("neighbour depth shape must match the neighbour image")

    world, finite = _world_points(reference, reference_map)
    neighbour_columns, neighbour_rows, predicted_neighbour_depth = _project(neighbour, world)
    sampled_depth, sampled_valid = _bilinear_sample(neighbour_map, neighbour_columns, neighbour_rows)
    depth_scale = np.maximum(np.abs(predicted_neighbour_depth), 1e-12)
    depth_consistent = np.abs(sampled_depth - predicted_neighbour_depth) / depth_scale <= relative_depth_tolerance

    neighbour_world = _world_from_pixels(
        neighbour,
        neighbour_columns,
        neighbour_rows,
        sampled_depth,
    )
    back_columns, back_rows, back_depth = _project(reference, neighbour_world)
    rows, columns = _pixel_grid(*reference_map.shape)
    pixel_error = np.sqrt((back_columns - columns) ** 2 + (back_rows - rows) ** 2)
    return (
        finite
        & sampled_valid
        & np.isfinite(back_depth)
        & (back_depth > 0.0)
        & depth_consistent
        & (pixel_error <= pixel_tolerance)
    )
