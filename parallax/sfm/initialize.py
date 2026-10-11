"""Initial-pair selection for incremental SfM."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from numpy.typing import ArrayLike, NDArray

from features.match import MatchDiagnostics, match_descriptors_locally
from geometry.epipolar import (
    RelativePose,
    estimate_relative_pose,
    essential_from_correspondences,
    refine_relative_pose,
    symmetric_epipolar_distances,
)
from geometry.ransac import ransac


FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class SfmView:
    view_id: str
    image: FloatArray
    intrinsic: FloatArray
    keypoints: FloatArray
    descriptors: FloatArray
    descriptor_radius: int


@dataclass(frozen=True)
class PairMatch:
    left_index: int
    right_index: int
    left_view_id: str
    right_view_id: str
    left_feature_indices: NDArray[np.int64]
    right_feature_indices: NDArray[np.int64]
    left_points: FloatArray
    right_points: FloatArray
    inlier_mask: NDArray[np.bool_]
    pose: RelativePose
    diagnostics: MatchDiagnostics
    ransac_iterations: int

    @property
    def inlier_count(self) -> int:
        return int(np.sum(self.inlier_mask))


def _coarse_displacement_center(
    left: SfmView,
    right: SfmView,
    *,
    image_width: float,
    image_height: float,
) -> FloatArray:
    """Estimate the dominant image displacement without pose metadata."""
    coarse = match_descriptors_locally(
        left.keypoints,
        left.descriptors,
        right.keypoints,
        right.descriptors,
        search_radius_x=max(16.0, 0.20 * image_width),
        search_radius_y=max(12.0, 0.20 * image_height),
        ratio=0.75,
    )
    if len(coarse.matches) < 8:
        return np.zeros(2, dtype=np.float64)
    deltas = right.keypoints[coarse.matches[:, 1]] - left.keypoints[coarse.matches[:, 0]]
    bins, counts = np.unique(np.rint(deltas).astype(np.int64), axis=0, return_counts=True)
    peak = bins[int(np.argmax(counts))].astype(np.float64)
    near_peak = np.all(np.abs(deltas - peak) <= 2.0, axis=1)
    if int(np.sum(near_peak)) < 8:
        return np.median(deltas, axis=0).astype(np.float64)
    return np.median(deltas[near_peak], axis=0).astype(np.float64)


def _normalized_patch_at(
    image: np.ndarray,
    point: np.ndarray,
    *,
    radius: int,
) -> np.ndarray | None:
    x, y = (float(point[0]), float(point[1]))
    height, width = image.shape
    if (
        x - radius < 0.0
        or x + radius > width - 1.0
        or y - radius < 0.0
        or y + radius > height - 1.0
    ):
        return None
    columns, rows = np.meshgrid(
        np.arange(-radius, radius + 1, dtype=np.float64) + x,
        np.arange(-radius, radius + 1, dtype=np.float64) + y,
    )
    left_column = np.floor(columns).astype(np.int64)
    top_row = np.floor(rows).astype(np.int64)
    right_column = np.minimum(left_column + 1, width - 1)
    bottom_row = np.minimum(top_row + 1, height - 1)
    wx = columns - left_column
    wy = rows - top_row
    patch = (
        (1.0 - wx) * (1.0 - wy) * image[top_row, left_column]
        + wx * (1.0 - wy) * image[top_row, right_column]
        + (1.0 - wx) * wy * image[bottom_row, left_column]
        + wx * wy * image[bottom_row, right_column]
    )
    vector = patch.reshape(-1).astype(np.float64)
    vector -= float(np.mean(vector))
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-12:
        return None
    return vector / norm


def _refine_right_points_subpixel(
    image1: np.ndarray,
    image2: np.ndarray,
    points1: np.ndarray,
    points2: np.ndarray,
    *,
    radius: int,
) -> np.ndarray:
    refined = points2.astype(np.float64).copy()
    offsets = (
        np.array([-1.0, 0.0]),
        np.array([0.0, -1.0]),
        np.array([0.0, 0.0]),
        np.array([0.0, 1.0]),
        np.array([1.0, 0.0]),
    )
    for index, (left_point, right_point) in enumerate(zip(points1, points2)):
        reference = _normalized_patch_at(image1, left_point, radius=radius)
        if reference is None:
            continue
        costs: dict[tuple[float, float], float] = {}
        for offset in offsets:
            candidate = _normalized_patch_at(image2, right_point + offset, radius=radius)
            if candidate is None:
                break
            costs[(float(offset[0]), float(offset[1]))] = float(
                np.sum((reference - candidate) ** 2)
            )
        else:
            center = costs[(0.0, 0.0)]
            dx_denom = costs[(-1.0, 0.0)] - 2.0 * center + costs[(1.0, 0.0)]
            dy_denom = costs[(0.0, -1.0)] - 2.0 * center + costs[(0.0, 1.0)]
            dx = (
                0.5 * (costs[(-1.0, 0.0)] - costs[(1.0, 0.0)]) / dx_denom
                if abs(dx_denom) > 1e-12
                else 0.0
            )
            dy = (
                0.5 * (costs[(0.0, -1.0)] - costs[(0.0, 1.0)]) / dy_denom
                if abs(dy_denom) > 1e-12
                else 0.0
            )
            refined[index] = right_point + np.array(
                [
                    float(np.clip(dx, -0.75, 0.75)),
                    float(np.clip(dy, -0.75, 0.75)),
                ],
                dtype=np.float64,
            )
    return refined


def _match_window(
    image_width: float,
    image_height: float,
    center: FloatArray,
) -> tuple[float, float, float, float]:
    radius_x = max(5.0, min(5.0, 0.08 * float(image_width)))
    radius_y = max(6.0, min(6.0, 0.12 * float(image_height)))
    center_x, center_y = (float(center[0]), float(center[1]))
    return (
        max(-float(image_width), center_x - radius_x),
        min(float(image_width), center_x + radius_x),
        max(-float(image_height), center_y - radius_y),
        min(float(image_height), center_y + radius_y),
    )


def match_view_pair(
    views: list[SfmView],
    left_index: int,
    right_index: int,
    *,
    search_fraction: float = 0.05,
    match_ratio: float = 0.80,
    max_quality_matches: int = 700,
    ransac_threshold_px: float = 0.75,
    max_trials: int = 420,
) -> PairMatch:
    """Match two views with symmetric image-space bounds and estimate pose."""
    left = views[left_index]
    right = views[right_index]
    width = float(left.intrinsic[0, 2] * 2.0 + 1.0)
    height = float(left.intrinsic[1, 2] * 2.0 + 1.0)
    del search_fraction
    center = _coarse_displacement_center(
        left,
        right,
        image_width=width,
        image_height=height,
    )
    min_x, max_x, min_y, max_y = _match_window(width, height, center)
    matched = match_descriptors_locally(
        left.keypoints,
        left.descriptors,
        right.keypoints,
        right.descriptors,
        search_radius_x=max(abs(min_x), abs(max_x)),
        search_radius_y=max(abs(min_y), abs(max_y)),
        min_delta_x=min_x,
        max_delta_x=max_x,
        min_delta_y=min_y,
        max_delta_y=max_y,
        ratio=match_ratio,
    )
    matches = matched.matches
    if len(matches) < 8:
        raise ValueError(
            f"SfM initialization needs at least 8 matches; found {len(matches)}"
        )
    distances = np.linalg.norm(
        left.descriptors[matches[:, 0]] - right.descriptors[matches[:, 1]],
        axis=1,
    )
    matches = matches[np.argsort(distances)[:max_quality_matches]]
    left_points = left.keypoints[matches[:, 0]]
    right_points = _refine_right_points_subpixel(
        left.image,
        right.image,
        left_points,
        right.keypoints[matches[:, 1]],
        radius=min(left.descriptor_radius, right.descriptor_radius),
    )
    indices = np.arange(len(matches), dtype=np.int64)
    inverse_left = np.linalg.inv(left.intrinsic)
    inverse_right = np.linalg.inv(right.intrinsic)

    def fit(sample: np.ndarray) -> FloatArray:
        return essential_from_correspondences(
            left_points[sample],
            right_points[sample],
            left.intrinsic,
            right.intrinsic,
        )

    def residuals(model: FloatArray, sample: np.ndarray) -> FloatArray:
        fundamental = inverse_right.T @ model @ inverse_left
        return symmetric_epipolar_distances(
            fundamental,
            left_points[sample],
            right_points[sample],
        )

    result = ransac(
        indices,
        sample_size=8,
        fit_model=fit,
        residuals=residuals,
        threshold=ransac_threshold_px,
        max_trials=max_trials,
        seed=260925 + left_index * 1009 + right_index,
        min_inliers=8,
    )
    pose = estimate_relative_pose(
        left_points[result.inlier_mask],
        right_points[result.inlier_mask],
        left.intrinsic,
        right.intrinsic,
        essential=result.model,
    )
    pose = refine_relative_pose(
        pose,
        left_points[result.inlier_mask],
        right_points[result.inlier_mask],
        left.intrinsic,
        right.intrinsic,
        max_nfev=60,
    )
    return PairMatch(
        left_index,
        right_index,
        left.view_id,
        right.view_id,
        matches[:, 0].astype(np.int64),
        matches[:, 1].astype(np.int64),
        left_points,
        right_points,
        result.inlier_mask,
        pose,
        matched.diagnostics,
        result.iterations,
    )


def choose_initial_pair(
    views: list[SfmView],
    candidate_pairs: Iterable[tuple[int, int]] | None = None,
) -> PairMatch:
    """Return the pair with the largest robust epipolar inlier count."""
    if len(views) < 2:
        raise ValueError("incremental SfM needs at least two views")
    pairs = list(candidate_pairs or ((index, index + 1) for index in range(len(views) - 1)))
    best: PairMatch | None = None
    errors: list[str] = []
    for left_index, right_index in pairs:
        try:
            candidate = match_view_pair(views, left_index, right_index)
        except (ValueError, np.linalg.LinAlgError) as error:
            errors.append(f"{left_index}-{right_index}: {error}")
            continue
        if best is None or (
            candidate.inlier_count,
            -candidate.ransac_iterations,
        ) > (
            best.inlier_count,
            -best.ransac_iterations,
        ):
            best = candidate
    if best is None:
        detail = "; ".join(errors) if errors else "no candidate pairs"
        raise ValueError(f"no initial pair could be estimated: {detail}")
    return best
