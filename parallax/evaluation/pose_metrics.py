"""Pose metrics for reconstruction results with exact camera ground truth."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray

from camera.pinhole import project


FloatArray = NDArray[np.float64]
Camera = tuple[ArrayLike, ArrayLike, ArrayLike]


def _rotation(value: ArrayLike) -> FloatArray:
    rotation = np.asarray(value, dtype=np.float64)
    if rotation.shape != (3, 3):
        raise ValueError("rotation must have shape (3, 3)")
    return rotation


def _vector(value: ArrayLike) -> FloatArray:
    vector = np.asarray(value, dtype=np.float64).reshape(-1)
    if vector.shape != (3,):
        raise ValueError("translation must have shape (3,)")
    return vector


def _points(value: ArrayLike) -> FloatArray:
    points = np.asarray(value, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError("points must have shape (N, 3)")
    if len(points) == 0:
        raise ValueError("points must not be empty")
    return points


def rotation_error_degrees(estimated: ArrayLike, truth: ArrayLike) -> float:
    """Return the geodesic SO(3) error in degrees."""
    delta = _rotation(estimated) @ _rotation(truth).T
    cosine = np.clip((np.trace(delta) - 1.0) * 0.5, -1.0, 1.0)
    angle = float(np.degrees(np.arccos(cosine)))
    return 0.0 if abs(angle) < 1e-12 else angle


def translation_error(estimated: ArrayLike, truth: ArrayLike) -> float:
    """Return Euclidean translation error in metres."""
    return float(np.linalg.norm(_vector(estimated) - _vector(truth)))


def umeyama_sim3(source: ArrayLike, target: ArrayLike) -> tuple[float, FloatArray, FloatArray]:
    """Align ``source`` points to ``target`` as ``scale * R @ source + t``."""
    left = _points(source)
    right = _points(target)
    if left.shape != right.shape or len(left) < 3:
        raise ValueError("paired point arrays must share shape and contain 3+ points")
    left_mean = left.mean(axis=0)
    right_mean = right.mean(axis=0)
    left_centered = left - left_mean
    right_centered = right - right_mean
    covariance = right_centered.T @ left_centered / len(left)
    u, singular_values, vt = np.linalg.svd(covariance)
    sign = np.ones(3)
    if np.linalg.det(u @ vt) < 0.0:
        sign[-1] = -1.0
    rotation = u @ np.diag(sign) @ vt
    variance = float(np.mean(np.sum(left_centered * left_centered, axis=1)))
    if variance <= 0.0:
        raise ValueError("source points must not be identical")
    scale = float(np.sum(singular_values * sign) / variance)
    translation = right_mean - scale * rotation @ left_mean
    return scale, rotation, translation


def ate_sim3(estimated_centers: ArrayLike, truth_centers: ArrayLike) -> float:
    """Return camera-center ATE after Sim(3) Umeyama alignment."""
    scale, rotation, translation = umeyama_sim3(estimated_centers, truth_centers)
    aligned = (scale * (rotation @ _points(estimated_centers).T)).T + translation
    residual = aligned - _points(truth_centers)
    return float(np.sqrt(np.mean(np.sum(residual * residual, axis=1))))


def _camera_tuple(camera: Camera | dict[str, ArrayLike]) -> Camera:
    if isinstance(camera, dict):
        return (
            camera["K"],
            camera["R_world_to_camera"],
            camera["t_world_to_camera_m"],
        )
    return camera


def reprojection_rmse(
    points: ArrayLike,
    observations: ArrayLike,
    cameras: Sequence[Camera | dict[str, ArrayLike]],
) -> float:
    """Return pixel RMSE over finite observations with shape ``(C, N, 2)``."""
    world_points = _points(points)
    observed = np.asarray(observations, dtype=np.float64)
    if observed.shape != (len(cameras), len(world_points), 2):
        raise ValueError("observations must have shape (len(cameras), len(points), 2)")
    residuals = []
    for index, camera in enumerate(cameras):
        K, R, t = _camera_tuple(camera)
        predicted, _ = project(world_points, K, R, t)
        finite = np.all(np.isfinite(observed[index]), axis=1)
        residuals.append((predicted[finite] - observed[index, finite]).reshape(-1))
    if not residuals or sum(len(residual) for residual in residuals) == 0:
        raise ValueError("at least one finite observation is required")
    flat = np.concatenate(residuals)
    return float(np.sqrt(np.mean(flat * flat)))
