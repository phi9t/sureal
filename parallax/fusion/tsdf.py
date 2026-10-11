"""TSDF fusion primitives for calibrated depth maps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
from numpy.typing import ArrayLike, NDArray

from camera.pinhole import unproject


FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]


class CalibratedDepthView(Protocol):
    """The camera fields TSDF fusion needs from a stereo or scene view."""

    view_id: str
    K: FloatArray
    R_world_to_camera: FloatArray
    t_world_to_camera_m: FloatArray


@dataclass(frozen=True)
class TSDFVolume:
    """A regular grid of TSDF samples in world coordinates."""

    origin_m: FloatArray
    voxel_size_m: float
    values: FloatArray
    weights: FloatArray

    @property
    def shape(self) -> tuple[int, int, int]:
        return self.values.shape

    @property
    def observed_voxel_count(self) -> int:
        return int(np.count_nonzero(self.weights > 0.0))


def fuse_tsdf(
    previous: float,
    previous_weight: float,
    observation: float,
    observation_weight: float,
) -> tuple[float, float]:
    if previous_weight < 0.0 or observation_weight < 0.0:
        raise ValueError("TSDF weights must be non-negative")
    total = previous_weight + observation_weight
    if total == 0.0:
        return 0.0, 0.0
    return (previous * previous_weight + observation * observation_weight) / total, total


def _as_corner(value: ArrayLike, name: str) -> FloatArray:
    corner = np.asarray(value, dtype=np.float64).reshape(-1)
    if corner.shape != (3,):
        raise ValueError(f"{name} must have shape (3,)")
    if not np.all(np.isfinite(corner)):
        raise ValueError(f"{name} must be finite")
    return corner


def _as_depth_map(value: ArrayLike) -> FloatArray:
    depth = np.asarray(value, dtype=np.float64)
    if depth.ndim != 2:
        raise ValueError("depth maps must have shape HxW")
    return depth


def _as_mask(value: ArrayLike | None, shape: tuple[int, int]) -> BoolArray | None:
    if value is None:
        return None
    mask = np.asarray(value, dtype=bool)
    if mask.shape != shape:
        raise ValueError("valid_mask must have the same shape as the depth map")
    return mask


def volume_from_bounds(
    minimum_m: ArrayLike,
    maximum_m: ArrayLike,
    *,
    voxel_size_m: float,
) -> TSDFVolume:
    """Create an empty TSDF volume whose grid samples cover the requested bounds."""
    if voxel_size_m <= 0.0 or not np.isfinite(voxel_size_m):
        raise ValueError("voxel_size_m must be a finite positive value")
    minimum = _as_corner(minimum_m, "minimum_m")
    maximum = _as_corner(maximum_m, "maximum_m")
    if np.any(maximum <= minimum):
        raise ValueError("maximum_m must be greater than minimum_m on every axis")
    shape = tuple(np.ceil((maximum - minimum) / voxel_size_m).astype(np.int64) + 1)
    values = np.ones(shape, dtype=np.float64)
    weights = np.zeros(shape, dtype=np.float64)
    return TSDFVolume(minimum, float(voxel_size_m), values, weights)


def bounds_for_points(points: ArrayLike, *, padding_m: float, voxel_size_m: float) -> tuple[FloatArray, FloatArray]:
    """Return voxel-aligned bounds for a point cloud with symmetric padding."""
    if padding_m < 0.0 or not np.isfinite(padding_m):
        raise ValueError("padding_m must be a finite non-negative value")
    cloud = np.asarray(points, dtype=np.float64)
    if cloud.ndim != 2 or cloud.shape[1] != 3 or len(cloud) == 0:
        raise ValueError("points must have shape (N, 3) with at least one point")
    finite = np.all(np.isfinite(cloud), axis=1)
    if not np.any(finite):
        raise ValueError("at least one finite point is required")
    minimum = np.floor((np.min(cloud[finite], axis=0) - padding_m) / voxel_size_m) * voxel_size_m
    maximum = np.ceil((np.max(cloud[finite], axis=0) + padding_m) / voxel_size_m) * voxel_size_m
    return minimum.astype(np.float64), maximum.astype(np.float64)


def volume_sample_points(volume: TSDFVolume) -> FloatArray:
    """Return every TSDF grid sample as world points with shape (N, 3)."""
    axes = [
        volume.origin_m[axis] + np.arange(volume.shape[axis], dtype=np.float64) * volume.voxel_size_m
        for axis in range(3)
    ]
    x, y, z = np.meshgrid(axes[0], axes[1], axes[2], indexing="ij")
    return np.column_stack((x.reshape(-1), y.reshape(-1), z.reshape(-1)))


def depth_surface_points(
    view: CalibratedDepthView,
    depth_m: ArrayLike,
    *,
    valid_mask: ArrayLike | None = None,
    stride: int = 1,
) -> FloatArray:
    """Back-project valid depth samples into world-space surface points."""
    if stride <= 0:
        raise ValueError("stride must be positive")
    depth = _as_depth_map(depth_m)
    mask = np.isfinite(depth) & (depth > 0.0)
    supplied_mask = _as_mask(valid_mask, depth.shape)
    if supplied_mask is not None:
        mask &= supplied_mask
    sampled = np.zeros_like(mask, dtype=bool)
    sampled[::stride, ::stride] = True
    mask &= sampled
    rows, columns = np.nonzero(mask)
    if len(rows) == 0:
        raise ValueError(f"depth map for {view.view_id} has no valid samples")
    pixels = np.column_stack((columns.astype(np.float64), rows.astype(np.float64)))
    return unproject(
        pixels,
        depth[rows, columns],
        view.K,
        view.R_world_to_camera,
        view.t_world_to_camera_m,
    )


def integrate_depth_map(
    volume: TSDFVolume,
    view: CalibratedDepthView,
    depth_m: ArrayLike,
    *,
    truncation_m: float,
    observation_weight: float = 1.0,
    valid_mask: ArrayLike | None = None,
) -> TSDFVolume:
    """Fuse one calibrated depth map into ``volume`` using projective TSDF updates."""
    if truncation_m <= 0.0 or not np.isfinite(truncation_m):
        raise ValueError("truncation_m must be a finite positive value")
    if observation_weight < 0.0 or not np.isfinite(observation_weight):
        raise ValueError("observation_weight must be a finite non-negative value")
    depth = _as_depth_map(depth_m)
    supplied_mask = _as_mask(valid_mask, depth.shape)
    height, width = depth.shape
    points = volume_sample_points(volume)
    rotation = np.asarray(view.R_world_to_camera, dtype=np.float64)
    translation = np.asarray(view.t_world_to_camera_m, dtype=np.float64)
    camera = (rotation @ points.T).T + translation
    z = camera[:, 2]
    in_front = z > 0.0
    intrinsic = np.asarray(view.K, dtype=np.float64)
    projected = (intrinsic @ camera.T).T
    columns = projected[:, 0] / projected[:, 2]
    rows = projected[:, 1] / projected[:, 2]
    nearest_columns = np.rint(columns).astype(np.int64)
    nearest_rows = np.rint(rows).astype(np.int64)
    inside_image = (
        in_front
        & (nearest_columns >= 0)
        & (nearest_columns < width)
        & (nearest_rows >= 0)
        & (nearest_rows < height)
    )
    if not np.any(inside_image):
        return volume

    flat_indices = np.nonzero(inside_image)[0]
    sampled_depth = depth[nearest_rows[flat_indices], nearest_columns[flat_indices]]
    valid = np.isfinite(sampled_depth) & (sampled_depth > 0.0)
    if supplied_mask is not None:
        valid &= supplied_mask[nearest_rows[flat_indices], nearest_columns[flat_indices]]
    flat_indices = flat_indices[valid]
    if len(flat_indices) == 0:
        return volume

    signed_distance = depth[nearest_rows[flat_indices], nearest_columns[flat_indices]] - z[flat_indices]
    in_truncation_band = signed_distance >= -truncation_m
    flat_indices = flat_indices[in_truncation_band]
    signed_distance = signed_distance[in_truncation_band]
    if len(flat_indices) == 0:
        return volume

    observations = np.clip(signed_distance / truncation_m, -1.0, 1.0)
    flat_values = volume.values.reshape(-1)
    flat_weights = volume.weights.reshape(-1)
    old_values = flat_values[flat_indices]
    old_weights = flat_weights[flat_indices]
    total_weights = old_weights + observation_weight
    flat_values[flat_indices] = (old_values * old_weights + observations * observation_weight) / total_weights
    flat_weights[flat_indices] = total_weights
    return volume


def fuse_depth_maps(
    views: list[CalibratedDepthView],
    depth_maps_m: dict[str, ArrayLike],
    *,
    voxel_size_m: float,
    truncation_m: float,
    padding_m: float,
    valid_masks: dict[str, ArrayLike] | None = None,
    bounds_sample_stride: int = 1,
) -> TSDFVolume:
    """Create a TSDF volume and fuse all supplied calibrated depth maps into it."""
    if not views:
        raise ValueError("at least one calibrated view is required")
    surface_parts = []
    masks = valid_masks or {}
    for view in views:
        if view.view_id not in depth_maps_m:
            raise ValueError(f"missing depth map for view {view.view_id}")
        surface_parts.append(
            depth_surface_points(
                view,
                depth_maps_m[view.view_id],
                valid_mask=masks.get(view.view_id),
                stride=bounds_sample_stride,
            )
        )
    minimum, maximum = bounds_for_points(
        np.concatenate(surface_parts, axis=0),
        padding_m=padding_m,
        voxel_size_m=voxel_size_m,
    )
    volume = volume_from_bounds(minimum, maximum, voxel_size_m=voxel_size_m)
    for view in views:
        integrate_depth_map(
            volume,
            view,
            depth_maps_m[view.view_id],
            truncation_m=truncation_m,
            valid_mask=masks.get(view.view_id),
        )
    return volume
