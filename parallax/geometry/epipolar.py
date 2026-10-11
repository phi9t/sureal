"""Two-view epipolar geometry and calibrated relative pose recovery."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from geometry.triangulate import triangulate_points


FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class RelativePose:
    rotation: FloatArray
    translation: FloatArray
    essential: FloatArray


def _points2(value: ArrayLike, name: str, *, min_count: int = 8) -> FloatArray:
    points = np.asarray(value, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError(f"{name} must have shape (N, 2)")
    if len(points) < min_count:
        raise ValueError(f"{name} must contain at least {min_count} points")
    return points


def _normalize_points(points: FloatArray) -> tuple[FloatArray, FloatArray]:
    mean = points.mean(axis=0)
    centered = points - mean
    distances = np.linalg.norm(centered, axis=1)
    mean_distance = float(np.mean(distances))
    if mean_distance <= 1e-15:
        raise ValueError("point normalization is degenerate")
    scale = np.sqrt(2.0) / mean_distance
    transform = np.array(
        [
            [scale, 0.0, -scale * mean[0]],
            [0.0, scale, -scale * mean[1]],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    homogeneous = np.c_[points, np.ones(len(points), dtype=np.float64)]
    normalized = (transform @ homogeneous.T).T
    return normalized[:, :2], transform


def _rank2(matrix: FloatArray) -> FloatArray:
    left, values, right = np.linalg.svd(matrix)
    values[-1] = 0.0
    return left @ np.diag(values) @ right


def fundamental_from_correspondences(
    points1: ArrayLike,
    points2: ArrayLike,
) -> FloatArray:
    """Estimate a rank-2 fundamental matrix with Hartley-normalized 8-point DLT."""
    left = _points2(points1, "points1", min_count=1)
    right = _points2(points2, "points2", min_count=1)
    if left.shape != right.shape:
        raise ValueError("point arrays must have the same shape")
    normalized1, transform1 = _normalize_points(left)
    normalized2, transform2 = _normalize_points(right)
    x1 = normalized1[:, 0]
    y1 = normalized1[:, 1]
    x2 = normalized2[:, 0]
    y2 = normalized2[:, 1]
    system = np.column_stack(
        (
            x2 * x1,
            x2 * y1,
            x2,
            y2 * x1,
            y2 * y1,
            y2,
            x1,
            y1,
            np.ones(len(left), dtype=np.float64),
        )
    )
    _, _, right_vectors = np.linalg.svd(system)
    fundamental = right_vectors[-1].reshape(3, 3)
    fundamental = _rank2(fundamental)
    denormalized = transform2.T @ fundamental @ transform1
    norm = float(np.linalg.norm(denormalized))
    if norm <= 1e-15:
        raise ValueError("fundamental estimate is degenerate")
    return denormalized / norm


def _calibrated_points(points: FloatArray, intrinsic: ArrayLike) -> FloatArray:
    inverse = np.linalg.inv(np.asarray(intrinsic, dtype=np.float64))
    homogeneous = np.c_[points, np.ones(len(points), dtype=np.float64)]
    normalized = (inverse @ homogeneous.T).T
    return normalized[:, :2] / normalized[:, 2, None]


def essential_from_correspondences(
    points1: ArrayLike,
    points2: ArrayLike,
    K1: ArrayLike,
    K2: ArrayLike,
) -> FloatArray:
    """Estimate an essential matrix from calibrated pixel correspondences."""
    left = _points2(points1, "points1")
    right = _points2(points2, "points2")
    if left.shape != right.shape:
        raise ValueError("point arrays must have the same shape")
    essential = fundamental_from_correspondences(
        _calibrated_points(left, K1),
        _calibrated_points(right, K2),
    )
    u, _, vt = np.linalg.svd(essential)
    if np.linalg.det(u) < 0.0:
        u[:, -1] *= -1.0
    if np.linalg.det(vt) < 0.0:
        vt[-1] *= -1.0
    essential = u @ np.diag([1.0, 1.0, 0.0]) @ vt
    norm = float(np.linalg.norm(essential))
    if norm <= 1e-15:
        raise ValueError("essential estimate is degenerate")
    return essential / norm


def essential_from_fundamental(
    fundamental: ArrayLike,
    K1: ArrayLike,
    K2: ArrayLike,
) -> FloatArray:
    """Project a pixel fundamental matrix onto the essential manifold."""
    essential = (
        np.asarray(K2, dtype=np.float64).T
        @ np.asarray(fundamental, dtype=np.float64)
        @ np.asarray(K1, dtype=np.float64)
    )
    u, _, vt = np.linalg.svd(essential)
    if np.linalg.det(u) < 0.0:
        u[:, -1] *= -1.0
    if np.linalg.det(vt) < 0.0:
        vt[-1] *= -1.0
    projected = u @ np.diag([1.0, 1.0, 0.0]) @ vt
    norm = float(np.linalg.norm(projected))
    if norm <= 1e-15:
        raise ValueError("essential estimate is degenerate")
    return projected / norm


def decompose_essential(essential: ArrayLike) -> list[tuple[FloatArray, FloatArray]]:
    """Return the four calibrated relative-pose candidates for an essential matrix."""
    matrix = np.asarray(essential, dtype=np.float64)
    if matrix.shape != (3, 3):
        raise ValueError("essential must have shape (3, 3)")
    u, _, vt = np.linalg.svd(matrix)
    if np.linalg.det(u) < 0.0:
        u[:, -1] *= -1.0
    if np.linalg.det(vt) < 0.0:
        vt[-1] *= -1.0
    w = np.array(
        [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    rotations = [u @ w @ vt, u @ w.T @ vt]
    translation = u[:, 2]
    candidates: list[tuple[FloatArray, FloatArray]] = []
    for rotation in rotations:
        if np.linalg.det(rotation) < 0.0:
            rotation = -rotation
        for sign in (1.0, -1.0):
            candidates.append((rotation, sign * translation))
    return candidates


def estimate_relative_pose(
    points1: ArrayLike,
    points2: ArrayLike,
    K1: ArrayLike,
    K2: ArrayLike,
    *,
    essential: ArrayLike | None = None,
) -> RelativePose:
    """Estimate calibrated pose from correspondences, selecting by cheirality."""
    left = _points2(points1, "points1")
    right = _points2(points2, "points2")
    if left.shape != right.shape:
        raise ValueError("point arrays must have the same shape")
    matrix = (
        essential_from_correspondences(left, right, K1, K2)
        if essential is None
        else np.asarray(essential, dtype=np.float64)
    )
    best: tuple[int, float, FloatArray, FloatArray] | None = None
    for rotation, translation in decompose_essential(matrix):
        points = triangulate_points(
            left,
            right,
            K1,
            np.eye(3),
            np.zeros(3),
            K2,
            rotation,
            translation,
        )
        depth1 = points[:, 2]
        depth2 = (rotation @ points.T).T[:, 2] + translation[2]
        positive = (depth1 > 0.0) & (depth2 > 0.0)
        median_depth = float(np.median(depth1[positive])) if np.any(positive) else -np.inf
        score = (int(np.sum(positive)), median_depth)
        if best is None or score > (best[0], best[1]):
            best = (score[0], score[1], rotation, translation)
    if best is None or best[0] == 0:
        raise ValueError("essential decomposition has no cheirality-valid pose")
    translation = best[3]
    norm = float(np.linalg.norm(translation))
    if norm <= 1e-15:
        raise ValueError("relative translation is degenerate")
    return RelativePose(best[2], translation / norm, matrix)


def symmetric_epipolar_distances(
    fundamental: ArrayLike,
    points1: ArrayLike,
    points2: ArrayLike,
) -> FloatArray:
    """Return the symmetric point-to-epipolar-line distance for each match."""
    left = _points2(points1, "points1")
    right = _points2(points2, "points2")
    if left.shape != right.shape:
        raise ValueError("point arrays must have the same shape")
    matrix = np.asarray(fundamental, dtype=np.float64)
    homogeneous1 = np.c_[left, np.ones(len(left), dtype=np.float64)]
    homogeneous2 = np.c_[right, np.ones(len(right), dtype=np.float64)]
    lines2 = (matrix @ homogeneous1.T).T
    lines1 = (matrix.T @ homogeneous2.T).T
    numerator = np.sum(homogeneous2 * (matrix @ homogeneous1.T).T, axis=1) ** 2
    denominator = (
        1.0 / np.sum(lines1[:, :2] * lines1[:, :2], axis=1)
        + 1.0 / np.sum(lines2[:, :2] * lines2[:, :2], axis=1)
    )
    return np.sqrt(numerator * denominator)
