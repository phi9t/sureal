"""Seeded generic RANSAC primitives."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

import numpy as np
from numpy.typing import ArrayLike, NDArray


Model = TypeVar("Model")


@dataclass(frozen=True)
class RansacResult(Generic[Model]):
    model: Model
    inlier_mask: NDArray[np.bool_]
    score: float
    iterations: int


def ransac(
    data: ArrayLike,
    *,
    sample_size: int,
    fit_model: Callable[[np.ndarray], Model | list[Model] | tuple[Model, ...]],
    residuals: Callable[[Model, np.ndarray], ArrayLike],
    threshold: float,
    max_trials: int,
    seed: int,
    min_inliers: int | None = None,
) -> RansacResult[Model]:
    """Fit a model by seeded random sampling over item indices."""
    items = np.asarray(data)
    count = len(items)
    if sample_size <= 0 or sample_size > count:
        raise ValueError("sample_size must be between 1 and len(data)")
    if max_trials <= 0:
        raise ValueError("max_trials must be positive")
    if threshold < 0.0:
        raise ValueError("threshold must be non-negative")
    minimum = min_inliers if min_inliers is not None else sample_size
    rng = np.random.default_rng(seed)
    best_model: Model | None = None
    best_mask: NDArray[np.bool_] | None = None
    best_score = (-1, -np.inf)
    all_items = items.copy()
    for trial in range(max_trials):
        sample_positions = rng.choice(count, size=sample_size, replace=False)
        sample = all_items[sample_positions]
        try:
            fitted = fit_model(sample)
            candidates = list(fitted) if isinstance(fitted, (list, tuple)) else [fitted]
        except (FloatingPointError, ValueError, np.linalg.LinAlgError):
            continue
        for model in candidates:
            try:
                errors = np.asarray(residuals(model, all_items), dtype=np.float64)
            except (FloatingPointError, ValueError, np.linalg.LinAlgError):
                continue
            if errors.shape != (count,):
                raise ValueError("residuals must return one value per data item")
            inliers = np.isfinite(errors) & (errors <= float(threshold))
            inlier_count = int(np.sum(inliers))
            if inlier_count < minimum:
                continue
            residual_sum = float(np.sum(errors[inliers]))
            score = (inlier_count, -residual_sum)
            if score > best_score:
                best_model = model
                best_mask = inliers
                best_score = score
                if inlier_count == count:
                    return RansacResult(model, inliers, residual_sum, trial + 1)
    if best_model is None or best_mask is None:
        raise ValueError("RANSAC failed to find a model")
    inlier_items = all_items[best_mask]
    try:
        refined = fit_model(inlier_items)
        refined_candidates = (
            list(refined) if isinstance(refined, (list, tuple)) else [refined]
        )
        for model in refined_candidates:
            errors = np.asarray(residuals(model, all_items), dtype=np.float64)
            inliers = np.isfinite(errors) & (errors <= float(threshold))
            inlier_count = int(np.sum(inliers))
            if inlier_count < minimum:
                continue
            residual_sum = float(np.sum(errors[inliers]))
            score = (inlier_count, -residual_sum)
            if score >= best_score:
                best_model = model
                best_mask = inliers
                best_score = score
    except (FloatingPointError, ValueError, np.linalg.LinAlgError):
        pass
    return RansacResult(best_model, best_mask, -best_score[1], max_trials)
