"""Descriptor matching with mutual nearest neighbours and Lowe's ratio test."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


IntArray = NDArray[np.int64]


@dataclass(frozen=True)
class MatchDiagnostics:
    matches_before_ratio: int
    matches_after_ratio: int
    matches_after_mutual_check: int


@dataclass(frozen=True)
class DescriptorMatches:
    matches: IntArray
    diagnostics: MatchDiagnostics


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
    return match_descriptors_with_diagnostics(
        descriptors1,
        descriptors2,
        ratio=ratio,
    ).matches


def match_descriptors_with_diagnostics(
    descriptors1: ArrayLike,
    descriptors2: ArrayLike,
    *,
    ratio: float = 0.75,
) -> DescriptorMatches:
    """Return descriptor matches with counts from each filtering stage."""
    left = _descriptors(descriptors1, "descriptors1")
    right = _descriptors(descriptors2, "descriptors2")
    if left.shape[1:] != right.shape[1:]:
        raise ValueError("descriptor dimensions must match")
    if len(left) == 0 or len(right) < 2 or len(left) < 2:
        return DescriptorMatches(
            np.empty((0, 2), dtype=np.int64),
            MatchDiagnostics(
                matches_before_ratio=0,
                matches_after_ratio=0,
                matches_after_mutual_check=0,
            ),
        )
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
    matched = np.asarray(matches, dtype=np.int64).reshape(-1, 2)
    return DescriptorMatches(
        matched,
        MatchDiagnostics(
            matches_before_ratio=len(left),
            matches_after_ratio=int(np.sum(forward_ratio)),
            matches_after_mutual_check=len(matched),
        ),
    )


def match_descriptors_locally(
    keypoints1: ArrayLike,
    descriptors1: ArrayLike,
    keypoints2: ArrayLike,
    descriptors2: ArrayLike,
    *,
    search_radius_x: float,
    search_radius_y: float,
    min_delta_x: float | None = None,
    max_delta_x: float | None = None,
    min_delta_y: float | None = None,
    max_delta_y: float | None = None,
    ratio: float = 0.95,
) -> DescriptorMatches:
    """Match descriptors inside a local image window with ratio and mutual checks."""
    left_points = np.asarray(keypoints1, dtype=np.float64)
    right_points = np.asarray(keypoints2, dtype=np.float64)
    left = _descriptors(descriptors1, "descriptors1")
    right = _descriptors(descriptors2, "descriptors2")
    if left_points.ndim != 2 or left_points.shape[1] != 2:
        raise ValueError("keypoints1 must have shape (N, 2)")
    if right_points.ndim != 2 or right_points.shape[1] != 2:
        raise ValueError("keypoints2 must have shape (N, 2)")
    if len(left_points) != len(left) or len(right_points) != len(right):
        raise ValueError("keypoint and descriptor counts must match")
    if left.shape[1:] != right.shape[1:]:
        raise ValueError("descriptor dimensions must match")
    if ratio <= 0.0:
        raise ValueError("ratio must be positive")
    if search_radius_x < 0.0 or search_radius_y < 0.0:
        raise ValueError("search radii must be non-negative")
    minimum_delta_x = (
        -float(search_radius_x) if min_delta_x is None else float(min_delta_x)
    )
    maximum_delta_x = (
        float(search_radius_x) if max_delta_x is None else float(max_delta_x)
    )
    minimum_delta_y = (
        -float(search_radius_y) if min_delta_y is None else float(min_delta_y)
    )
    maximum_delta_y = (
        float(search_radius_y) if max_delta_y is None else float(max_delta_y)
    )
    if minimum_delta_x > maximum_delta_x or minimum_delta_y > maximum_delta_y:
        raise ValueError("minimum deltas must not exceed maximum deltas")
    if len(left) == 0 or len(right) < 2 or len(left) < 2:
        return DescriptorMatches(
            np.empty((0, 2), dtype=np.int64),
            MatchDiagnostics(
                matches_before_ratio=0,
                matches_after_ratio=0,
                matches_after_mutual_check=0,
            ),
        )

    def nearest(
        source_points: np.ndarray,
        source_descriptors: np.ndarray,
        target_points: np.ndarray,
        target_descriptors: np.ndarray,
        *,
        lower_x: float,
        upper_x: float,
        lower_y: float,
        upper_y: float,
    ) -> tuple[np.ndarray, np.ndarray, int, int]:
        best = np.full(len(source_points), -1, dtype=np.int64)
        passed = np.zeros(len(source_points), dtype=bool)
        before_ratio = 0
        after_ratio = 0
        rows: dict[int, list[int]] = {}
        for target_index, target in enumerate(target_points):
            rows.setdefault(int(round(float(target[1]))), []).append(target_index)
        for index, (point, descriptor) in enumerate(
            zip(source_points, source_descriptors)
        ):
            candidate_indices: list[int] = []
            row_start = int(np.floor(point[1] + lower_y))
            row_stop = int(np.ceil(point[1] + upper_y))
            for row in range(row_start, row_stop + 1):
                candidate_indices.extend(rows.get(row, ()))
            if not candidate_indices:
                continue
            possible = np.asarray(candidate_indices, dtype=np.int64)
            deltas = target_points[possible] - point
            candidates = possible[
                (deltas[:, 0] >= lower_x)
                & (deltas[:, 0] <= upper_x)
                & (deltas[:, 1] >= lower_y)
                & (deltas[:, 1] <= upper_y)
            ]
            if len(candidates) < 2:
                continue
            before_ratio += 1
            distances = np.linalg.norm(
                target_descriptors[candidates] - descriptor,
                axis=1,
            )
            order = np.argsort(distances)
            best_distance = float(distances[order[0]])
            second_distance = float(distances[order[1]])
            best[index] = int(candidates[order[0]])
            if best_distance <= float(ratio) * second_distance:
                passed[index] = True
                after_ratio += 1
        return best, passed, before_ratio, after_ratio

    forward, forward_ratio, before_ratio, after_ratio = nearest(
        left_points,
        left,
        right_points,
        right,
        lower_x=minimum_delta_x,
        upper_x=maximum_delta_x,
        lower_y=minimum_delta_y,
        upper_y=maximum_delta_y,
    )
    backward, backward_ratio, _, _ = nearest(
        right_points,
        right,
        left_points,
        left,
        lower_x=-maximum_delta_x,
        upper_x=-minimum_delta_x,
        lower_y=-maximum_delta_y,
        upper_y=-minimum_delta_y,
    )
    matches: list[tuple[int, int]] = []
    for left_index, right_index in enumerate(forward):
        if right_index < 0:
            continue
        if (
            forward_ratio[left_index]
            and backward_ratio[right_index]
            and int(backward[right_index]) == left_index
        ):
            matches.append((left_index, int(right_index)))
    matched = np.asarray(matches, dtype=np.int64).reshape(-1, 2)
    return DescriptorMatches(
        matched,
        MatchDiagnostics(
            matches_before_ratio=before_ratio,
            matches_after_ratio=after_ratio,
            matches_after_mutual_check=len(matched),
        ),
    )
