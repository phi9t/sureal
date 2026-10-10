"""Pinhole camera projection primitives."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]


def _points(value: ArrayLike) -> FloatArray:
    array = np.asarray(value, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError("points must have shape (N, 3)")
    return array


def project(
    points: ArrayLike,
    K: ArrayLike,
    R: ArrayLike,
    t: ArrayLike,
) -> tuple[FloatArray, FloatArray]:
    world = _points(points)
    intrinsic = np.asarray(K, dtype=np.float64)
    rotation = np.asarray(R, dtype=np.float64)
    translation = np.asarray(t, dtype=np.float64)
    camera = (rotation @ world.T).T + translation
    if np.any(camera[:, 2] <= 0.0):
        raise ValueError("points must lie in front of the camera")
    homogeneous = (intrinsic @ camera.T).T
    return homogeneous[:, :2] / homogeneous[:, 2, None], camera[:, 2].copy()


def unproject(
    pixels: ArrayLike,
    depth: ArrayLike,
    K: ArrayLike,
    R: ArrayLike,
    t: ArrayLike,
) -> FloatArray:
    image = np.asarray(pixels, dtype=np.float64)
    depths = np.asarray(depth, dtype=np.float64).reshape(-1)
    if image.ndim != 2 or image.shape[1] != 2 or len(image) != len(depths):
        raise ValueError("pixels and depth must have shapes (N, 2) and (N,)")
    rays = (
        np.linalg.inv(np.asarray(K, dtype=np.float64))
        @ np.c_[image, np.ones(len(image))].T
    ).T
    camera = rays * depths[:, None]
    rotation = np.asarray(R, dtype=np.float64)
    translation = np.asarray(t, dtype=np.float64)
    return (rotation.T @ (camera - translation).T).T
