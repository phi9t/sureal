"""TSDF fusion primitives."""

from __future__ import annotations


def fuse_tsdf(
    previous: float,
    previous_weight: float,
    observation: float,
    observation_weight: float,
) -> tuple[float, float]:
    if previous_weight < 0.0 or observation_weight < 0.0:
        raise ValueError("TSDF weights must be non-negative")
    total = previous_weight + observation_weight
    if total == 0.0:
        return 0.0, 0.0
    return (previous * previous_weight + observation * observation_weight) / total, total
