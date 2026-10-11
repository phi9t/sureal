"""Extract triangle meshes from scalar volumes."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]


@dataclass(frozen=True)
class Mesh:
    """Triangle mesh with vertices in world coordinates."""

    vertices: FloatArray
    triangles: IntArray


_CUBE_CORNERS = np.array(
    [
        [0, 0, 0],
        [1, 0, 0],
        [1, 1, 0],
        [0, 1, 0],
        [0, 0, 1],
        [1, 0, 1],
        [1, 1, 1],
        [0, 1, 1],
    ],
    dtype=np.int64,
)

_TETRAHEDRA = (
    (0, 5, 1, 6),
    (0, 1, 2, 6),
    (0, 2, 3, 6),
    (0, 3, 7, 6),
    (0, 7, 4, 6),
    (0, 4, 5, 6),
)


def _as_origin(value: ArrayLike) -> FloatArray:
    origin = np.asarray(value, dtype=np.float64).reshape(-1)
    if origin.shape != (3,) or not np.all(np.isfinite(origin)):
        raise ValueError("origin_m must be a finite vector with shape (3,)")
    return origin


def _interpolate(point_a: FloatArray, point_b: FloatArray, value_a: float, value_b: float, level: float) -> FloatArray:
    denominator = value_b - value_a
    if denominator == 0.0:
        return 0.5 * (point_a + point_b)
    alpha = (level - value_a) / denominator
    return point_a + alpha * (point_b - point_a)


def _triangle_is_degenerate(points: list[FloatArray]) -> bool:
    edge_a = points[1] - points[0]
    edge_b = points[2] - points[0]
    return bool(np.linalg.norm(np.cross(edge_a, edge_b)) <= 1e-14)


def _append_triangle(vertices: list[FloatArray], triangles: list[tuple[int, int, int]], points: list[FloatArray]) -> None:
    if _triangle_is_degenerate(points):
        return
    start = len(vertices)
    vertices.extend(points)
    triangles.append((start, start + 1, start + 2))


def _polygonise_tetrahedron(
    points: FloatArray,
    values: FloatArray,
    *,
    level: float,
    vertices: list[FloatArray],
    triangles: list[tuple[int, int, int]],
) -> None:
    inside = [index for index, value in enumerate(values) if value < level]
    outside = [index for index, value in enumerate(values) if value >= level]
    if len(inside) == 0 or len(inside) == 4:
        return
    if len(inside) == 1:
        inside_index = inside[0]
        triangle = [
            _interpolate(points[inside_index], points[outside_index], values[inside_index], values[outside_index], level)
            for outside_index in outside
        ]
        _append_triangle(vertices, triangles, triangle)
        return
    if len(inside) == 3:
        outside_index = outside[0]
        triangle = [
            _interpolate(points[outside_index], points[inside_index], values[outside_index], values[inside_index], level)
            for inside_index in inside
        ]
        _append_triangle(vertices, triangles, triangle[::-1])
        return

    first_inside, second_inside = inside
    first_outside, second_outside = outside
    quad = [
        _interpolate(points[first_inside], points[first_outside], values[first_inside], values[first_outside], level),
        _interpolate(points[first_inside], points[second_outside], values[first_inside], values[second_outside], level),
        _interpolate(points[second_inside], points[second_outside], values[second_inside], values[second_outside], level),
        _interpolate(points[second_inside], points[first_outside], values[second_inside], values[first_outside], level),
    ]
    _append_triangle(vertices, triangles, [quad[0], quad[1], quad[2]])
    _append_triangle(vertices, triangles, [quad[0], quad[2], quad[3]])


def marching_cubes(
    values: ArrayLike,
    *,
    origin_m: ArrayLike,
    voxel_size_m: float,
    level: float = 0.0,
    valid_mask: ArrayLike | None = None,
) -> Mesh:
    """Extract an iso-surface mesh from a regular scalar grid.

    The implementation decomposes each cube into tetrahedra. That keeps the
    extractor compact, deterministic and free of lookup-table dependencies while
    preserving the marching-cubes contract at the volume boundary.
    """
    scalar = np.asarray(values, dtype=np.float64)
    if scalar.ndim != 3 or min(scalar.shape) < 2:
        raise ValueError("values must be a 3D array with at least two samples per axis")
    if voxel_size_m <= 0.0 or not np.isfinite(voxel_size_m):
        raise ValueError("voxel_size_m must be a finite positive value")
    origin = _as_origin(origin_m)
    mask = None
    if valid_mask is not None:
        mask = np.asarray(valid_mask, dtype=bool)
        if mask.shape != scalar.shape:
            raise ValueError("valid_mask must have the same shape as values")

    vertices: list[FloatArray] = []
    triangles: list[tuple[int, int, int]] = []
    for ix in range(scalar.shape[0] - 1):
        for iy in range(scalar.shape[1] - 1):
            for iz in range(scalar.shape[2] - 1):
                corner_indices = _CUBE_CORNERS + np.array([ix, iy, iz], dtype=np.int64)
                corner_values = scalar[
                    corner_indices[:, 0],
                    corner_indices[:, 1],
                    corner_indices[:, 2],
                ]
                if not np.all(np.isfinite(corner_values)):
                    continue
                if mask is not None and not np.all(mask[corner_indices[:, 0], corner_indices[:, 1], corner_indices[:, 2]]):
                    continue
                if np.all(corner_values >= level) or np.all(corner_values < level):
                    continue
                corner_points = origin + corner_indices.astype(np.float64) * voxel_size_m
                for tetrahedron in _TETRAHEDRA:
                    local = np.asarray(tetrahedron, dtype=np.int64)
                    _polygonise_tetrahedron(
                        corner_points[local],
                        corner_values[local],
                        level=level,
                        vertices=vertices,
                        triangles=triangles,
                    )

    if not vertices:
        return Mesh(
            np.empty((0, 3), dtype=np.float64),
            np.empty((0, 3), dtype=np.int64),
        )
    return Mesh(np.vstack(vertices).astype(np.float64), np.asarray(triangles, dtype=np.int64))
