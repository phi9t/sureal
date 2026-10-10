"""Rigid alignment and coordinate-system helpers."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]


def _points(value: ArrayLike) -> FloatArray:
    array = np.asarray(value, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError("points must have shape (N, 3)")
    return array


def apply_transform(
    points: ArrayLike,
    rotation: ArrayLike,
    translation: ArrayLike,
) -> FloatArray:
    return (
        np.asarray(rotation, dtype=np.float64) @ _points(points).T
    ).T + np.asarray(translation, dtype=np.float64)


def rigid_transform_svd(
    source: ArrayLike,
    target: ArrayLike,
) -> tuple[FloatArray, FloatArray]:
    left = _points(source)
    right = _points(target)
    if left.shape != right.shape or len(left) < 3:
        raise ValueError(
            "paired point arrays must share shape and contain at least three points"
        )
    left_center = left.mean(axis=0)
    right_center = right.mean(axis=0)
    covariance = (left - left_center).T @ (right - right_center)
    u, _, vt = np.linalg.svd(covariance)
    rotation = vt.T @ u.T
    if np.linalg.det(rotation) < 0.0:
        vt[-1] *= -1.0
        rotation = vt.T @ u.T
    translation = right_center - rotation @ left_center
    return rotation, translation


def icp(
    source: ArrayLike,
    target: ArrayLike,
    iterations: int = 20,
) -> tuple[FloatArray, FloatArray, list[float]]:
    source_points = _points(source)
    target_points = _points(target)
    rotation = np.eye(3)
    translation = np.zeros(3)
    history: list[float] = []
    for _ in range(iterations):
        transformed = apply_transform(source_points, rotation, translation)
        distances = np.linalg.norm(
            transformed[:, None, :] - target_points[None, :, :],
            axis=2,
        )
        matches = target_points[np.argmin(distances, axis=1)]
        history.append(float(np.sqrt(np.mean(np.min(distances, axis=1) ** 2))))
        delta_rotation, delta_translation = rigid_transform_svd(
            transformed,
            matches,
        )
        rotation = delta_rotation @ rotation
        translation = delta_rotation @ translation + delta_translation
        if len(history) > 1 and abs(history[-2] - history[-1]) < 1e-12:
            break
    transformed = apply_transform(source_points, rotation, translation)
    distances = np.linalg.norm(
        transformed[:, None, :] - target_points[None, :, :],
        axis=2,
    )
    history.append(float(np.sqrt(np.mean(np.min(distances, axis=1) ** 2))))
    return rotation, translation, history


def normalize_rows(vectors: ArrayLike) -> FloatArray:
    values = np.asarray(vectors, dtype=np.float64)
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    if np.any(norms == 0.0):
        raise ValueError("zero vector cannot be normalized")
    return values / norms


def opencv_opengl_camera_transform(matrix: ArrayLike) -> FloatArray:
    value = np.asarray(matrix, dtype=np.float64)
    if value.shape != (4, 4):
        raise ValueError("camera matrix must have shape (4, 4)")
    axis_flip = np.diag([1.0, -1.0, -1.0, 1.0])
    return axis_flip @ value
