"""Descriptor matching with mutual nearest neighbours and Lowe's ratio test."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


IntArray = NDArray[np.int64]


def _descriptors(value: ArrayLike, name: str) -> np.ndarray:
    descriptors = np.asarray(value, dtype=np.float64)
    if descriptors.ndim != 2:
        raise ValueError(f"{name} must have shape (N, D)")
    return descriptors


def _ratio_mask(distances: np.ndarray, ratio: float) -> tuple[np.ndarray, np.ndarray]:
    if distances.shape[1] < 2:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=bool)
    order = np.argsort(distances, axis=1)
    best = order[:, 0]
    best_distance = distances[np.arange(len(distances)), best]
    second_distance = distances[np.arange(len(distances)), order[:, 1]]
    passed = best_distance <= float(ratio) * second_distance
    return best, passed


def match_descriptors(
    descriptors1: ArrayLike,
    descriptors2: ArrayLike,
    *,
    ratio: float = 0.75,
) -> IntArray:
    """Return ``(index_in_first, index_in_second)`` descriptor matches."""
    left = _descriptors(descriptors1, "descriptors1")
    right = _descriptors(descriptors2, "descriptors2")
    if left.shape[1:] != right.shape[1:]:
        raise ValueError("descriptor dimensions must match")
    if len(left) == 0 or len(right) < 2 or len(left) < 2:
        return np.empty((0, 2), dtype=np.int64)
    if ratio <= 0.0:
        raise ValueError("ratio must be positive")
    distances = np.linalg.norm(left[:, None, :] - right[None, :, :], axis=2)
    forward, forward_ratio = _ratio_mask(distances, ratio)
    backward, backward_ratio = _ratio_mask(distances.T, ratio)
    matches: list[tuple[int, int]] = []
    for left_index, right_index in enumerate(forward):
        if (
            forward_ratio[left_index]
            and backward_ratio[right_index]
            and int(backward[right_index]) == left_index
        ):
            matches.append((left_index, int(right_index)))
    return np.asarray(matches, dtype=np.int64).reshape(-1, 2)
