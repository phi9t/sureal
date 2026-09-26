"""Controlled two-hypothesis samplers for point- versus scene-level stochasticity."""

from __future__ import annotations

import numpy as np


def _summary(assignments: np.ndarray) -> dict[str, float]:
    if assignments.ndim != 2 or assignments.shape[1] < 2:
        raise ValueError("assignments must contain multiple points per sample")
    fraction_b = assignments.mean(axis=1)
    coherence = np.maximum(fraction_b, 1.0 - fraction_b)
    dominant = (fraction_b >= 0.5).astype(np.int64)
    return {
        "within_sample_coherence": float(coherence.mean()),
        "hypothesis_coverage": float(len(np.unique(dominant)) / 2.0),
        "evidence_consistency": 1.0,
        "hybrid_sample_fraction": float(np.mean((fraction_b > 0.05) & (fraction_b < 0.95))),
    }


def compare_ambiguous_samplers(samples: int, points_per_sample: int, seed: int) -> dict[str, dict[str, float]]:
    if samples < 2 or points_per_sample < 2:
        raise ValueError("the ambiguity experiment needs at least two samples and two points")
    rng = np.random.default_rng(seed)
    independent = rng.integers(0, 2, size=(samples, points_per_sample), endpoint=False)
    scene_latents = rng.integers(0, 2, size=(samples, 1), endpoint=False)
    shared = np.repeat(scene_latents, points_per_sample, axis=1)
    return {
        "independent_points": _summary(independent),
        "shared_scene_latent": _summary(shared),
    }
