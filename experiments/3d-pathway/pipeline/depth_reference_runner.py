"""Offline Depth Anything V2 maintained-reference execution for module 08."""

from __future__ import annotations

import math
from typing import Any

import numpy as np


ADAPTER = "depth-anything-v2"
IMAGE = "surflo-pathway-neural-rendering:1"
PINNED_SOURCE_COMMIT = "a561b849ebae10a6f5ef49e26c83cbbcd36c71bf"
CHECKPOINT_ID = "depth-anything-v2-metric-hypersim-small"
CHECKPOINT_REVISION = "3bc65d4e14a6786a61acec16453c50e12bf5f338"
CHECKPOINT_SHA256 = "b782898d8a3e8be1f639de33837ed85e9b4b73e40f8f5e5cd99067588d722545"
CHECKPOINT_BYTES = 99_222_290


def _depth_metrics(prediction: np.ndarray, truth: np.ndarray) -> dict[str, Any]:
    prediction = np.asarray(prediction)
    truth = np.asarray(truth)
    if prediction.ndim != 2 or prediction.shape != truth.shape:
        raise ValueError("depth prediction and truth must have identical HxW shapes")
    valid = np.isfinite(prediction) & (prediction > 0.0) & np.isfinite(truth) & (truth > 0.0)
    valid_pixels = int(np.count_nonzero(valid))
    if valid_pixels < 2:
        raise ValueError("depth evaluation requires at least two valid positive pixels")
    predicted = prediction[valid].astype(np.float64)
    target = truth[valid].astype(np.float64)
    residual = predicted - target
    design = np.column_stack((predicted, np.ones_like(predicted)))
    coefficients, _, rank, _ = np.linalg.lstsq(design, target, rcond=None)
    if rank < 2 or not np.isfinite(coefficients).all():
        raise ValueError("affine depth alignment is degenerate")
    scale, shift = (float(value) for value in coefficients)
    aligned = scale * predicted + shift
    ratios = np.maximum(predicted / target, target / predicted)
    metrics = {
        "valid_pixels": valid_pixels,
        "valid_pixel_fraction": float(valid_pixels / truth.size),
        "raw_rmse_m": float(np.sqrt(np.mean(residual * residual))),
        "raw_abs_rel": float(np.mean(np.abs(residual) / target)),
        "raw_delta1": float(np.mean(ratios < 1.25)),
        "affine_aligned_rmse_m": float(np.sqrt(np.mean((aligned - target) ** 2))),
        "affine_aligned_abs_rel": float(np.mean(np.abs(aligned - target) / target)),
        "affine_scale": scale,
        "affine_shift_m": shift,
    }
    if not all(math.isfinite(value) for value in metrics.values()):
        raise ValueError("depth metrics must be finite")
    return metrics
