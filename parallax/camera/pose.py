"""Camera pose and epipolar-geometry helpers."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]


def camera_center(R: ArrayLike, t: ArrayLike) -> FloatArray:
    rotation = np.asarray(R, dtype=np.float64)
    return -rotation.T @ np.asarray(t, dtype=np.float64)


def _skew(vector: ArrayLike) -> FloatArray:
    x, y, z = np.asarray(vector, dtype=np.float64)
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])


def fundamental_from_poses(
    K1: ArrayLike,
    R1: ArrayLike,
    t1: ArrayLike,
    K2: ArrayLike,
    R2: ArrayLike,
    t2: ArrayLike,
) -> FloatArray:
    intrinsic1 = np.asarray(K1, dtype=np.float64)
    intrinsic2 = np.asarray(K2, dtype=np.float64)
    rotation1 = np.asarray(R1, dtype=np.float64)
    rotation2 = np.asarray(R2, dtype=np.float64)
    translation1 = np.asarray(t1, dtype=np.float64)
    translation2 = np.asarray(t2, dtype=np.float64)
    relative_rotation = rotation2 @ rotation1.T
    relative_translation = translation2 - relative_rotation @ translation1
    essential = _skew(relative_translation) @ relative_rotation
    fundamental = (
        np.linalg.inv(intrinsic2).T @ essential @ np.linalg.inv(intrinsic1)
    )
    norm = np.linalg.norm(fundamental)
    return fundamental / norm if norm else fundamental


def symmetric_epipolar_distance(
    F: ArrayLike,
    pixel1: ArrayLike,
    pixel2: ArrayLike,
) -> float:
    fundamental = np.asarray(F, dtype=np.float64)
    point1 = np.r_[np.asarray(pixel1, dtype=np.float64), 1.0]
    point2 = np.r_[np.asarray(pixel2, dtype=np.float64), 1.0]
    line2 = fundamental @ point1
    line1 = fundamental.T @ point2
    numerator = float(point2 @ fundamental @ point1) ** 2
    denominator = (
        1.0 / (line1[0] ** 2 + line1[1] ** 2)
        + 1.0 / (line2[0] ** 2 + line2[1] ** 2)
    )
    return float(np.sqrt(numerator * denominator))
