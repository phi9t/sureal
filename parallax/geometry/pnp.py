"""Perspective-n-point pose recovery using DLT plus Gauss-Newton refinement."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]


def _points3(value: ArrayLike) -> FloatArray:
    points = np.asarray(value, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) < 6:
        raise ValueError("points3d must have shape (N, 3) with at least 6 points")
    return points


def _points2(value: ArrayLike, count: int) -> FloatArray:
    points = np.asarray(value, dtype=np.float64)
    if points.shape != (count, 2):
        raise ValueError("pixels must have shape (len(points3d), 2)")
    return points


def rotation_matrix_from_vector(vector: ArrayLike) -> FloatArray:
    """Map an axis-angle vector to SO(3)."""
    omega = np.asarray(vector, dtype=np.float64).reshape(3)
    theta = float(np.linalg.norm(omega))
    skew = np.array(
        [
            [0.0, -omega[2], omega[1]],
            [omega[2], 0.0, -omega[0]],
            [-omega[1], omega[0], 0.0],
        ],
        dtype=np.float64,
    )
    if theta <= 1e-15:
        return np.eye(3) + skew
    unit_skew = skew / theta
    return (
        np.eye(3)
        + np.sin(theta) * unit_skew
        + (1.0 - np.cos(theta)) * (unit_skew @ unit_skew)
    )


def rotation_vector_from_matrix(rotation: ArrayLike) -> FloatArray:
    """Map SO(3) to an axis-angle vector."""
    matrix = np.asarray(rotation, dtype=np.float64)
    cosine = float(np.clip((np.trace(matrix) - 1.0) * 0.5, -1.0, 1.0))
    theta = float(np.arccos(cosine))
    if theta <= 1e-15:
        return np.zeros(3, dtype=np.float64)
    vector = np.array(
        [
            matrix[2, 1] - matrix[1, 2],
            matrix[0, 2] - matrix[2, 0],
            matrix[1, 0] - matrix[0, 1],
        ],
        dtype=np.float64,
    )
    return theta * vector / (2.0 * np.sin(theta))


def _normalized_pixels(pixels: FloatArray, intrinsic: ArrayLike) -> FloatArray:
    inverse = np.linalg.inv(np.asarray(intrinsic, dtype=np.float64))
    homogeneous = np.c_[pixels, np.ones(len(pixels), dtype=np.float64)]
    normalized = (inverse @ homogeneous.T).T
    return normalized[:, :2] / normalized[:, 2, None]


def solve_pnp_dlt(
    points3d: ArrayLike,
    pixels: ArrayLike,
    intrinsic: ArrayLike,
) -> tuple[FloatArray, FloatArray]:
    """Estimate world-to-camera pose from 3D-2D correspondences by DLT."""
    world = _points3(points3d)
    image = _points2(pixels, len(world))
    normalized = _normalized_pixels(image, intrinsic)
    homogeneous = np.c_[world, np.ones(len(world), dtype=np.float64)]
    rows = []
    for point, (x_coord, y_coord) in zip(homogeneous, normalized):
        zero = np.zeros(4, dtype=np.float64)
        rows.append(np.r_[point, zero, -x_coord * point])
        rows.append(np.r_[zero, point, -y_coord * point])
    system = np.vstack(rows)
    _, _, right = np.linalg.svd(system)
    projection = right[-1].reshape(3, 4)
    if np.linalg.det(projection[:, :3]) < 0.0:
        projection = -projection
    left, singular_values, right_t = np.linalg.svd(projection[:, :3])
    rotation = left @ right_t
    if np.linalg.det(rotation) < 0.0:
        left[:, -1] *= -1.0
        rotation = left @ right_t
    scale = float(np.mean(singular_values))
    if scale <= 1e-15:
        raise ValueError("PnP DLT is degenerate")
    translation = projection[:, 3] / scale
    return rotation, translation


def _project_raw(
    points: FloatArray,
    intrinsic: ArrayLike,
    rotation: FloatArray,
    translation: FloatArray,
) -> FloatArray:
    camera = (rotation @ points.T).T + translation
    homogeneous = (np.asarray(intrinsic, dtype=np.float64) @ camera.T).T
    return homogeneous[:, :2] / homogeneous[:, 2, None]


def _residuals(
    params: FloatArray,
    points: FloatArray,
    pixels: FloatArray,
    intrinsic: ArrayLike,
) -> FloatArray:
    rotation = rotation_matrix_from_vector(params[:3])
    translation = params[3:]
    return (_project_raw(points, intrinsic, rotation, translation) - pixels).reshape(-1)


def refine_pnp(
    points3d: ArrayLike,
    pixels: ArrayLike,
    intrinsic: ArrayLike,
    rotation: ArrayLike,
    translation: ArrayLike,
    *,
    iterations: int = 20,
) -> tuple[FloatArray, FloatArray, float]:
    """Refine a DLT pose by minimizing reprojection residuals."""
    world = _points3(points3d)
    image = _points2(pixels, len(world))
    params = np.r_[
        rotation_vector_from_matrix(rotation),
        np.asarray(translation, dtype=np.float64).reshape(3),
    ]
    damping = 1e-6
    epsilon = 1e-6
    residual = _residuals(params, world, image, intrinsic)
    best_loss = float(residual @ residual)
    for _ in range(iterations):
        jacobian = np.empty((len(residual), 6), dtype=np.float64)
        for column in range(6):
            shifted = params.copy()
            shifted[column] += epsilon
            jacobian[:, column] = (
                _residuals(shifted, world, image, intrinsic) - residual
            ) / epsilon
        step = np.linalg.solve(
            jacobian.T @ jacobian + damping * np.eye(6),
            -jacobian.T @ residual,
        )
        candidate = params + step
        candidate_residual = _residuals(candidate, world, image, intrinsic)
        candidate_loss = float(candidate_residual @ candidate_residual)
        if candidate_loss <= best_loss:
            params = candidate
            residual = candidate_residual
            best_loss = candidate_loss
            damping = max(damping * 0.5, 1e-12)
            if np.linalg.norm(step) < 1e-12:
                break
        else:
            damping *= 10.0
    rmse = float(np.sqrt(best_loss / len(residual)))
    return rotation_matrix_from_vector(params[:3]), params[3:].copy(), rmse


def solve_pnp(
    points3d: ArrayLike,
    pixels: ArrayLike,
    intrinsic: ArrayLike,
    *,
    refine: bool = True,
) -> tuple[FloatArray, FloatArray, float]:
    """Recover a world-to-camera pose and final reprojection RMSE."""
    world = _points3(points3d)
    image = _points2(pixels, len(world))
    rotation, translation = solve_pnp_dlt(world, image, intrinsic)
    if refine:
        return refine_pnp(world, image, intrinsic, rotation, translation)
    residual = _residuals(
        np.r_[rotation_vector_from_matrix(rotation), translation],
        world,
        image,
        intrinsic,
    )
    return rotation, translation, float(np.sqrt(float(residual @ residual) / len(residual)))
