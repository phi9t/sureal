"""Triangulation and single-point reprojection refinement."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

from camera.pinhole import project


FloatArray = NDArray[np.float64]


def triangulate_point(
    pixel1: ArrayLike,
    pixel2: ArrayLike,
    K1: ArrayLike,
    R1: ArrayLike,
    t1: ArrayLike,
    K2: ArrayLike,
    R2: ArrayLike,
    t2: ArrayLike,
) -> FloatArray:
    projection1 = (
        np.asarray(K1, dtype=np.float64)
        @ np.c_[np.asarray(R1, dtype=np.float64), np.asarray(t1, dtype=np.float64)]
    )
    projection2 = (
        np.asarray(K2, dtype=np.float64)
        @ np.c_[np.asarray(R2, dtype=np.float64), np.asarray(t2, dtype=np.float64)]
    )
    u1, v1 = np.asarray(pixel1, dtype=np.float64)
    u2, v2 = np.asarray(pixel2, dtype=np.float64)
    system = np.stack(
        [
            u1 * projection1[2] - projection1[0],
            v1 * projection1[2] - projection1[1],
            u2 * projection2[2] - projection2[0],
            v2 * projection2[2] - projection2[1],
        ]
    )
    _, _, right = np.linalg.svd(system)
    homogeneous = right[-1]
    if abs(homogeneous[3]) < 1e-15:
        raise ValueError("triangulation is degenerate")
    return homogeneous[:3] / homogeneous[3]


def reprojection_residuals(
    point: ArrayLike,
    observations: ArrayLike,
    cameras: list[tuple[ArrayLike, ArrayLike, ArrayLike]],
) -> FloatArray:
    world = np.asarray(point, dtype=np.float64).reshape(1, 3)
    predicted = np.array([project(world, *camera)[0][0] for camera in cameras])
    return (predicted - np.asarray(observations, dtype=np.float64)).reshape(-1)


def reprojection_rmse(
    point: ArrayLike,
    observations: ArrayLike,
    cameras: list[tuple[ArrayLike, ArrayLike, ArrayLike]],
) -> float:
    residuals = reprojection_residuals(point, observations, cameras)
    return float(np.sqrt(np.mean(residuals * residuals)))


def refine_point_gauss_newton(
    initial: ArrayLike,
    observations: ArrayLike,
    cameras: list[tuple[ArrayLike, ArrayLike, ArrayLike]],
    iterations: int = 10,
) -> tuple[FloatArray, list[float]]:
    point = np.asarray(initial, dtype=np.float64).copy()
    history = [reprojection_rmse(point, observations, cameras)]
    epsilon = 1e-6
    damping = 1e-8
    for _ in range(iterations):
        residual = reprojection_residuals(point, observations, cameras)
        jacobian = np.empty((len(residual), 3), dtype=np.float64)
        for axis in range(3):
            shifted = point.copy()
            shifted[axis] += epsilon
            jacobian[:, axis] = (
                reprojection_residuals(shifted, observations, cameras) - residual
            ) / epsilon
        step = np.linalg.solve(
            jacobian.T @ jacobian + damping * np.eye(3),
            -jacobian.T @ residual,
        )
        point += step
        history.append(reprojection_rmse(point, observations, cameras))
        if np.linalg.norm(step) < 1e-12:
            break
    return point, history
