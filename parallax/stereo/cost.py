"""Photometric costs for plane-sweep stereo."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]


def _image_pair(reference: ArrayLike, candidate: ArrayLike) -> tuple[FloatArray, FloatArray]:
    left = np.asarray(reference, dtype=np.float64)
    right = np.asarray(candidate, dtype=np.float64)
    if left.ndim != 2 or right.ndim != 2 or left.shape != right.shape:
        raise ValueError("stereo costs require two images with the same HxW shape")
    return left, right


def _valid_array(image: FloatArray, valid_mask: ArrayLike | None) -> BoolArray:
    valid = np.isfinite(image)
    if valid_mask is not None:
        mask = np.asarray(valid_mask, dtype=bool)
        if mask.shape != image.shape:
            raise ValueError("valid_mask must match the image shape")
        valid &= mask
    return valid


def _shifted(value: np.ndarray, row_offset: int, column_offset: int) -> tuple[np.ndarray, BoolArray]:
    shifted = np.zeros_like(value)
    valid = np.zeros(value.shape, dtype=bool)
    height, width = value.shape
    source_rows = slice(max(0, row_offset), min(height, height + row_offset))
    source_columns = slice(max(0, column_offset), min(width, width + column_offset))
    target_rows = slice(max(0, -row_offset), min(height, height - row_offset))
    target_columns = slice(max(0, -column_offset), min(width, width - column_offset))
    shifted[target_rows, target_columns] = value[source_rows, source_columns]
    valid[target_rows, target_columns] = True
    return shifted, valid


def zncc_cost(reference: ArrayLike, candidate: ArrayLike, *, window_radius: int = 2, valid_mask: ArrayLike | None = None) -> FloatArray:
    """Return per-pixel zero-mean normalized cross-correlation cost.

    The returned value is ``1 - zncc`` for windows with enough finite samples;
    invalid windows are ``nan`` so callers can ignore them during aggregation.
    """
    if window_radius < 0:
        raise ValueError("window_radius must be non-negative")
    left, right = _image_pair(reference, candidate)
    valid_source = _valid_array(left, None) & _valid_array(right, valid_mask)
    count = np.zeros(left.shape, dtype=np.float64)
    sum_left = np.zeros(left.shape, dtype=np.float64)
    sum_right = np.zeros(left.shape, dtype=np.float64)
    sum_left_squared = np.zeros(left.shape, dtype=np.float64)
    sum_right_squared = np.zeros(left.shape, dtype=np.float64)
    sum_product = np.zeros(left.shape, dtype=np.float64)

    for row_offset in range(-window_radius, window_radius + 1):
        for column_offset in range(-window_radius, window_radius + 1):
            shifted_left, left_window = _shifted(left, row_offset, column_offset)
            shifted_right, right_window = _shifted(right, row_offset, column_offset)
            shifted_valid, valid_window = _shifted(valid_source, row_offset, column_offset)
            valid = shifted_valid & left_window & right_window & valid_window
            values_left = np.where(valid, shifted_left, 0.0)
            values_right = np.where(valid, shifted_right, 0.0)
            count += valid
            sum_left += values_left
            sum_right += values_right
            sum_left_squared += values_left * values_left
            sum_right_squared += values_right * values_right
            sum_product += values_left * values_right

    minimum = max(2, int(0.6 * (2 * window_radius + 1) ** 2))
    mean_left = np.divide(sum_left, count, out=np.zeros_like(sum_left), where=count > 0.0)
    mean_right = np.divide(sum_right, count, out=np.zeros_like(sum_right), where=count > 0.0)
    variance_left = sum_left_squared - count * mean_left * mean_left
    variance_right = sum_right_squared - count * mean_right * mean_right
    covariance = sum_product - count * mean_left * mean_right
    denominator = np.sqrt(np.maximum(variance_left * variance_right, 0.0))
    zncc = np.divide(covariance, denominator, out=np.zeros_like(covariance), where=denominator > 1e-12)
    cost = 1.0 - np.clip(zncc, -1.0, 1.0)
    cost[(count < minimum) | (denominator <= 1e-12)] = np.nan
    return cost


def census_cost(reference: ArrayLike, candidate: ArrayLike, *, radius: int = 2, valid_mask: ArrayLike | None = None) -> FloatArray:
    """Return normalized census-transform Hamming cost per pixel."""
    if radius <= 0:
        raise ValueError("radius must be positive")
    left, right = _image_pair(reference, candidate)
    valid_source = _valid_array(left, None) & _valid_array(right, valid_mask)
    mismatch = np.zeros(left.shape, dtype=np.float64)
    count = np.zeros(left.shape, dtype=np.float64)

    for row_offset in range(-radius, radius + 1):
        for column_offset in range(-radius, radius + 1):
            if row_offset == 0 and column_offset == 0:
                continue
            shifted_left, left_window = _shifted(left, row_offset, column_offset)
            shifted_right, right_window = _shifted(right, row_offset, column_offset)
            shifted_valid, valid_window = _shifted(valid_source, row_offset, column_offset)
            valid = valid_source & shifted_valid & left_window & right_window & valid_window
            left_bit = shifted_left >= left
            right_bit = shifted_right >= right
            mismatch += valid & (left_bit != right_bit)
            count += valid

    cost = np.divide(mismatch, count, out=np.full(left.shape, np.nan, dtype=np.float64), where=count > 0.0)
    return cost
