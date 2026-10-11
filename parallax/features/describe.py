"""Patch descriptors for deterministic local feature matching."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class PatchDescriptors:
    keypoints: FloatArray
    descriptors: FloatArray


def describe_patches(
    image: ArrayLike,
    keypoints: ArrayLike,
    *,
    radius: int = 4,
) -> PatchDescriptors:
    """Return zero-mean, unit-norm square patch descriptors."""
    if radius <= 0:
        raise ValueError("radius must be positive")
    values = np.asarray(image, dtype=np.float64)
    if values.ndim != 2:
        raise ValueError("image must have shape (H, W)")
    points = np.asarray(keypoints, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("keypoints must have shape (N, 2)")
    height, width = values.shape
    kept: list[FloatArray] = []
    descriptors: list[FloatArray] = []
    for point in points:
        column = int(round(float(point[0])))
        row = int(round(float(point[1])))
        if (
            row - radius < 0
            or row + radius >= height
            or column - radius < 0
            or column + radius >= width
        ):
            continue
        patch = values[
            row - radius : row + radius + 1,
            column - radius : column + radius + 1,
        ]
        vector = patch.reshape(-1).astype(np.float64)
        vector -= float(np.mean(vector))
        norm = float(np.linalg.norm(vector))
        if norm <= 1e-12:
            continue
        kept.append(np.array([float(column), float(row)], dtype=np.float64))
        descriptors.append(vector / norm)
    if not descriptors:
        return PatchDescriptors(
            np.empty((0, 2), dtype=np.float64),
            np.empty((0, (2 * radius + 1) ** 2), dtype=np.float64),
        )
    return PatchDescriptors(
        np.vstack(kept).astype(np.float64),
        np.vstack(descriptors).astype(np.float64),
    )
