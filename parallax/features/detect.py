"""Deterministic corner detectors for Parallax feature pipelines."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]


def _image(value: ArrayLike) -> FloatArray:
    image = np.asarray(value, dtype=np.float64)
    if image.ndim != 2:
        raise ValueError("image must have shape (H, W)")
    if min(image.shape) < 3:
        raise ValueError("image must be at least 3x3")
    return image


def _box_sum(image: FloatArray, radius: int) -> FloatArray:
    if radius < 0:
        raise ValueError("radius must be non-negative")
    if radius == 0:
        return image.copy()
    padded = np.pad(image, radius, mode="edge")
    height, width = image.shape
    result = np.empty_like(image, dtype=np.float64)
    for row in range(height):
        for column in range(width):
            window = padded[
                row : row + 2 * radius + 1,
                column : column + 2 * radius + 1,
            ]
            result[row, column] = float(np.sum(window))
    return result


def harris_response(
    image: ArrayLike,
    *,
    window_radius: int = 1,
    k: float = 0.04,
) -> FloatArray:
    """Return a Harris-Stephens corner response for a grayscale image."""
    values = _image(image)
    gradient_y, gradient_x = np.gradient(values)
    xx = _box_sum(gradient_x * gradient_x, window_radius)
    yy = _box_sum(gradient_y * gradient_y, window_radius)
    xy = _box_sum(gradient_x * gradient_y, window_radius)
    determinant = xx * yy - xy * xy
    trace = xx + yy
    return determinant - float(k) * trace * trace


def detect_harris(
    image: ArrayLike,
    *,
    max_keypoints: int = 512,
    quality: float = 0.01,
    min_distance: int = 3,
    border: int = 5,
    window_radius: int = 1,
    k: float = 0.04,
) -> FloatArray:
    """Detect Harris corners as ``(x, y)`` image coordinates."""
    if max_keypoints <= 0:
        raise ValueError("max_keypoints must be positive")
    if min_distance < 0 or border < 0:
        raise ValueError("min_distance and border must be non-negative")
    response = harris_response(image, window_radius=window_radius, k=k)
    height, width = response.shape
    valid = np.zeros_like(response, dtype=bool)
    valid[border : height - border, border : width - border] = True
    peak = float(np.max(response[valid])) if np.any(valid) else 0.0
    if peak <= 0.0:
        return np.empty((0, 2), dtype=np.float64)
    local_maximum = np.ones_like(response, dtype=bool)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            shifted = np.full_like(response, -np.inf, dtype=np.float64)
            source_rows = slice(max(0, -dy), min(height, height - dy))
            source_columns = slice(max(0, -dx), min(width, width - dx))
            target_rows = slice(max(0, dy), min(height, height + dy))
            target_columns = slice(max(0, dx), min(width, width + dx))
            shifted[target_rows, target_columns] = response[
                source_rows,
                source_columns,
            ]
            local_maximum &= response >= shifted
    candidates = np.argwhere(
        valid
        & local_maximum
        & (response >= peak * float(quality))
    )
    order = np.lexsort(
        (
            candidates[:, 1],
            candidates[:, 0],
            -response[candidates[:, 0], candidates[:, 1]],
        )
    )
    accepted: list[tuple[float, float]] = []
    min_distance_squared = float(min_distance * min_distance)
    for row, column in candidates[order]:
        point = np.array([float(column), float(row)], dtype=np.float64)
        if all(
            np.sum((point - np.asarray(existing)) ** 2) >= min_distance_squared
            for existing in accepted
        ):
            accepted.append((float(column), float(row)))
            if len(accepted) == max_keypoints:
                break
    return np.asarray(accepted, dtype=np.float64).reshape(-1, 2)
