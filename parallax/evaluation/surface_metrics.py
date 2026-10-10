"""Surface and depth-map metrics for reconstructed geometry."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.spatial import cKDTree


FloatArray = NDArray[np.float64]


def _points(value: ArrayLike) -> FloatArray:
    points = np.asarray(value, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError("point clouds must have shape (N, 3)")
    if len(points) == 0:
        raise ValueError("point clouds must not be empty")
    return points


def nearest_distances(source: ArrayLike, target: ArrayLike) -> FloatArray:
    """Return each source point's Euclidean distance to the target cloud."""
    left = _points(source)
    right = _points(target)
    distances, _ = cKDTree(right).query(left, k=1)
    return np.asarray(distances, dtype=np.float64)


def surface_metrics(
    prediction: ArrayLike,
    truth: ArrayLike,
    *,
    tau: float,
) -> dict[str, float]:
    """Return Chamfer, accuracy, completeness and F-score at ``tau``."""
    if tau <= 0.0:
        raise ValueError("tau must be positive")
    pred_to_truth = nearest_distances(prediction, truth)
    truth_to_pred = nearest_distances(truth, prediction)
    accuracy = float(np.mean(pred_to_truth))
    completeness = float(np.mean(truth_to_pred))
    precision = float(np.mean(pred_to_truth <= tau))
    recall = float(np.mean(truth_to_pred <= tau))
    f_score = 0.0
    if precision + recall > 0.0:
        f_score = float(2.0 * precision * recall / (precision + recall))
    return {
        "accuracy": accuracy,
        "completeness": completeness,
        "chamfer_distance": float(0.5 * (accuracy + completeness)),
        "precision": precision,
        "recall": recall,
        "f_score": f_score,
        "tau": float(tau),
    }


def _valid_depths(
    prediction: ArrayLike,
    truth: ArrayLike,
    valid_mask: ArrayLike | None,
) -> tuple[FloatArray, FloatArray]:
    predicted = np.asarray(prediction, dtype=np.float64)
    expected = np.asarray(truth, dtype=np.float64)
    if predicted.shape != expected.shape:
        raise ValueError("depth maps must have the same shape")
    valid = np.isfinite(predicted) & np.isfinite(expected) & (predicted > 0.0) & (
        expected > 0.0
    )
    if valid_mask is not None:
        valid &= np.asarray(valid_mask, dtype=bool)
    if not np.any(valid):
        raise ValueError("at least one valid positive depth is required")
    return predicted[valid], expected[valid]


def depth_absrel(
    prediction: ArrayLike,
    truth: ArrayLike,
    valid_mask: ArrayLike | None = None,
) -> float:
    """Return mean absolute relative camera-axis depth error."""
    predicted, expected = _valid_depths(prediction, truth, valid_mask)
    return float(np.mean(np.abs(predicted - expected) / expected))


def depth_delta_less_than(
    prediction: ArrayLike,
    truth: ArrayLike,
    *,
    threshold: float = 1.25,
    valid_mask: ArrayLike | None = None,
) -> float:
    """Return the fraction of valid pixels with max depth ratio below threshold."""
    if threshold <= 1.0:
        raise ValueError("threshold must be greater than 1")
    predicted, expected = _valid_depths(prediction, truth, valid_mask)
    ratio = np.maximum(predicted / expected, expected / predicted)
    return float(np.mean(ratio < threshold))


def depth_metrics(
    prediction: ArrayLike,
    truth: ArrayLike,
    valid_mask: ArrayLike | None = None,
) -> dict[str, float]:
    """Return the standard depth-map metrics used by the Parallax modules."""
    return {
        "absrel": depth_absrel(prediction, truth, valid_mask),
        "delta_lt_1_25": depth_delta_less_than(
            prediction,
            truth,
            valid_mask=valid_mask,
        ),
    }
