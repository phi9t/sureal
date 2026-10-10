"""Geometric two-hypothesis fixture for point- versus scene-level randomness."""

from __future__ import annotations

from typing import Any

import numpy as np


EVIDENCE_TOLERANCE_M = 1e-6
COHERENT_SAMPLE_THRESHOLD = 0.95
RMSE_BLOCK_SAMPLES = 256
AMBIGUITY_RANDOM_SEED = 260925
AMBIGUITY_SWEEP_SAMPLES = 64
AMBIGUITY_PROFILE_POINTS = {"smoke": 257, "full": 4097}
AMBIGUITY_ARRAY_SEMANTICS = {
    "observed_truth_xyz": "input-visible occluder points shared by both hypotheses",
    "independent_observed_xyz": "visible points predicted by every independent-point sample",
    "shared_observed_xyz": "visible points predicted by every shared-latent sample",
    "hidden_hypothesis_a_xyz": "complete hidden object in the left alternative",
    "hidden_hypothesis_b_xyz": "complete hidden object in the right alternative",
    "independent_assignments": "per-sample, per-point hidden-hypothesis choices for the first query",
    "independent_repeat_assignments": "fresh per-point choices for a repeated query",
    "shared_scene_latents": "one persistent binary hidden-hypothesis choice per sample",
    "shared_repeat_scene_latents": "scene choices reused for a repeated query",
}


def _observed_occluder() -> np.ndarray:
    """Return the input-visible surface shared by both hidden hypotheses."""
    columns, rows = np.meshgrid(
        np.linspace(-1.2, 1.2, 8, dtype=np.float64),
        np.linspace(-0.8, 0.8, 6, dtype=np.float64),
        indexing="xy",
    )
    return np.stack(
        [columns.ravel(), rows.ravel(), np.zeros(columns.size, dtype=np.float64)],
        axis=-1,
    )


def _hidden_hypotheses(point_count: int) -> tuple[np.ndarray, np.ndarray]:
    """Place the same hidden object to the left or right of an occluder."""
    index = np.arange(point_count, dtype=np.float64)
    phase = index * (np.pi * (3.0 - np.sqrt(5.0)))
    height = 0.55 * ((index + 0.5) / point_count - 0.5)
    radius = 0.18 + 0.025 * np.sin(index * 1.7)
    local = np.stack(
        [radius * np.cos(phase), height, radius * np.sin(phase)],
        axis=-1,
    )
    left = local + np.array([-0.62, 0.0, 0.75], dtype=np.float64)
    right = local + np.array([0.62, 0.0, 0.75], dtype=np.float64)
    return left, right


def generate_ambiguity_fixture(
    samples: int,
    hidden_points_per_sample: int,
    seed: int,
) -> dict[str, np.ndarray]:
    """Sample independent-point and shared-scene alternatives for one fixture.

    The visible occluder is identical in every prediction. Behind it, two
    complete-scene hypotheses place one object at different locations.
    Independent decoding chooses a hypothesis separately for every hidden
    point and repeated query; shared decoding samples one persistent latent.
    """
    if samples < 2 or hidden_points_per_sample < 2:
        raise ValueError("the ambiguity experiment needs at least two samples and two points")

    independent_rng = np.random.default_rng(np.random.SeedSequence([seed, 0]))
    repeat_rng = np.random.default_rng(np.random.SeedSequence([seed, 1]))
    shared_rng = np.random.default_rng(np.random.SeedSequence([seed, 2]))
    observed = _observed_occluder()
    hypothesis_a, hypothesis_b = _hidden_hypotheses(hidden_points_per_sample)
    independent = independent_rng.integers(
        0,
        2,
        size=(samples, hidden_points_per_sample),
        dtype=np.uint8,
    )
    independent_repeat = repeat_rng.integers(
        0,
        2,
        size=(samples, hidden_points_per_sample),
        dtype=np.uint8,
    )
    shared_latents = shared_rng.integers(0, 2, size=samples, dtype=np.uint8)

    observed_predictions = np.broadcast_to(
        observed[None, :, :],
        (samples, *observed.shape),
    ).copy()
    return {
        "observed_truth_xyz": observed,
        "independent_observed_xyz": observed_predictions,
        "shared_observed_xyz": observed_predictions.copy(),
        "hidden_hypothesis_a_xyz": hypothesis_a,
        "hidden_hypothesis_b_xyz": hypothesis_b,
        "independent_assignments": independent,
        "independent_repeat_assignments": independent_repeat,
        "shared_scene_latents": shared_latents,
        "shared_repeat_scene_latents": shared_latents.copy(),
    }


def _binary_entropy(probability: float) -> float:
    if probability <= 0.0 or probability >= 1.0:
        return 0.0
    return float(
        -probability * np.log2(probability)
        - (1.0 - probability) * np.log2(1.0 - probability)
    )


def _validate_fixture(fixture: dict[str, np.ndarray]) -> tuple[int, int]:
    required = {
        "observed_truth_xyz",
        "independent_observed_xyz",
        "shared_observed_xyz",
        "hidden_hypothesis_a_xyz",
        "hidden_hypothesis_b_xyz",
        "independent_assignments",
        "independent_repeat_assignments",
        "shared_scene_latents",
        "shared_repeat_scene_latents",
    }
    if set(fixture) != required:
        missing = sorted(required - set(fixture))
        extra = sorted(set(fixture) - required)
        raise ValueError(f"ambiguity fixture members mismatch: missing={missing}, extra={extra}")

    assignments = np.asarray(fixture["independent_assignments"])
    repeat_assignments = np.asarray(fixture["independent_repeat_assignments"])
    if assignments.ndim != 2 or assignments.shape[0] < 2 or assignments.shape[1] < 2:
        raise ValueError("independent assignments must have shape [samples>=2, points>=2]")
    if repeat_assignments.shape != assignments.shape:
        raise ValueError("repeated independent assignments must match the first query")
    if np.any((assignments != 0) & (assignments != 1)) or np.any(
        (repeat_assignments != 0) & (repeat_assignments != 1)
    ):
        raise ValueError("independent assignments must be binary")

    samples, hidden_points = assignments.shape
    observed = np.asarray(fixture["observed_truth_xyz"], dtype=np.float64)
    if observed.ndim != 2 or observed.shape[1] != 3 or observed.shape[0] < 1:
        raise ValueError("observed truth must have shape [points>=1, 3]")
    if not np.all(np.isfinite(observed)):
        raise ValueError("observed truth contains non-finite points")
    for name in ("independent_observed_xyz", "shared_observed_xyz"):
        predicted = np.asarray(fixture[name], dtype=np.float64)
        if predicted.shape != (samples, observed.shape[0], 3):
            raise ValueError(f"{name} must have shape [samples, observed_points, 3]")
        if not np.all(np.isfinite(predicted)):
            raise ValueError(f"{name} contains non-finite points")

    hypothesis_a = np.asarray(fixture["hidden_hypothesis_a_xyz"], dtype=np.float64)
    hypothesis_b = np.asarray(fixture["hidden_hypothesis_b_xyz"], dtype=np.float64)
    if hypothesis_a.shape != (hidden_points, 3) or hypothesis_b.shape != hypothesis_a.shape:
        raise ValueError("hidden hypotheses must have shape [hidden_points, 3]")
    if not np.all(np.isfinite(hypothesis_a)) or not np.all(np.isfinite(hypothesis_b)):
        raise ValueError("hidden hypotheses contain non-finite points")
    if np.allclose(hypothesis_a, hypothesis_b):
        raise ValueError("hidden hypotheses must be geometrically distinct")

    for name in ("shared_scene_latents", "shared_repeat_scene_latents"):
        latents = np.asarray(fixture[name])
        if latents.shape != (samples,) or np.any((latents != 0) & (latents != 1)):
            raise ValueError(f"{name} must contain one binary latent per sample")
    return samples, hidden_points


def _evidence_metrics(
    predicted: np.ndarray,
    truth: np.ndarray,
) -> tuple[float, float, float]:
    errors = np.linalg.norm(predicted - truth[None, :, :], axis=-1)
    sample_rmse = np.sqrt(np.mean(np.square(errors), axis=1))
    return (
        float(np.sqrt(np.mean(np.square(errors)))),
        float(np.mean(errors <= EVIDENCE_TOLERANCE_M)),
        float(np.max(sample_rmse)),
    )


def _assignment_metrics(
    assignments: np.ndarray,
    repeated_assignments: np.ndarray,
    hypothesis_a: np.ndarray,
    hypothesis_b: np.ndarray,
) -> dict[str, float | int]:
    fraction_b = assignments.mean(axis=1)
    coherence = np.maximum(fraction_b, 1.0 - fraction_b)
    dominant = (fraction_b >= 0.5).astype(np.uint8)
    coherent = coherence >= COHERENT_SAMPLE_THRESHOLD
    coherent_entropy = (
        _binary_entropy(float(dominant[coherent].mean())) if np.any(coherent) else 0.0
    )
    separation_squared = np.sum(np.square(hypothesis_b - hypothesis_a), axis=1)
    separation_mean = float(separation_squared.mean())
    best_rmse_sum = 0.0
    for start in range(0, assignments.shape[0], RMSE_BLOCK_SAMPLES):
        stop = min(start + RMSE_BLOCK_SAMPLES, assignments.shape[0])
        block = assignments[start:stop].astype(np.float64, copy=False)
        mean_squared_to_a = block @ separation_squared / assignments.shape[1]
        mean_squared_to_b = np.maximum(0.0, separation_mean - mean_squared_to_a)
        best_rmse_sum += float(
            np.minimum(np.sqrt(mean_squared_to_a), np.sqrt(mean_squared_to_b)).sum()
        )
    return {
        "sample_count": int(assignments.shape[0]),
        "hidden_points_per_sample": int(assignments.shape[1]),
        "within_sample_coherence": float(coherence.mean()),
        "hypothesis_coverage": float(len(np.unique(dominant)) / 2.0),
        "coherent_hypothesis_coverage": float(
            len(np.unique(dominant[coherent])) / 2.0 if np.any(coherent) else 0.0
        ),
        "hybrid_sample_fraction": float(
            np.mean((fraction_b > 0.05) & (fraction_b < 0.95))
        ),
        "marginal_mode_entropy_bits": _binary_entropy(float(assignments.mean())),
        "coherent_scene_entropy_bits": coherent_entropy,
        "balanced_posterior_frequency_error": float(abs(assignments.mean() - 0.5)),
        "repeat_query_consistency": float(np.mean(assignments == repeated_assignments)),
        "best_hypothesis_rmse_m": best_rmse_sum / assignments.shape[0],
    }


def evaluate_ambiguity_fixture(
    fixture: dict[str, np.ndarray],
) -> dict[str, dict[str, float | int]]:
    """Recompute sampler quality from persisted geometric arrays."""
    samples, hidden_points = _validate_fixture(fixture)
    truth = np.asarray(fixture["observed_truth_xyz"], dtype=np.float64)
    hypothesis_a = np.asarray(fixture["hidden_hypothesis_a_xyz"], dtype=np.float64)
    hypothesis_b = np.asarray(fixture["hidden_hypothesis_b_xyz"], dtype=np.float64)

    independent = _assignment_metrics(
        np.asarray(fixture["independent_assignments"]),
        np.asarray(fixture["independent_repeat_assignments"]),
        hypothesis_a,
        hypothesis_b,
    )
    independent_rmse, independent_consistency, independent_worst_rmse = _evidence_metrics(
        np.asarray(fixture["independent_observed_xyz"], dtype=np.float64),
        truth,
    )
    independent.update(
        {
            "evidence_points_per_sample": int(truth.shape[0]),
            "evidence_rmse_m": independent_rmse,
            "worst_sample_evidence_rmse_m": independent_worst_rmse,
            "evidence_consistency": independent_consistency,
        }
    )

    shared_latents = np.asarray(fixture["shared_scene_latents"], dtype=np.uint8)
    repeated_latents = np.asarray(
        fixture["shared_repeat_scene_latents"], dtype=np.uint8
    )
    shared_rmse, shared_consistency, shared_worst_rmse = _evidence_metrics(
        np.asarray(fixture["shared_observed_xyz"], dtype=np.float64),
        truth,
    )
    shared = {
        "sample_count": samples,
        "hidden_points_per_sample": hidden_points,
        "evidence_points_per_sample": int(truth.shape[0]),
        "within_sample_coherence": 1.0,
        "hypothesis_coverage": float(len(np.unique(shared_latents)) / 2.0),
        "coherent_hypothesis_coverage": float(len(np.unique(shared_latents)) / 2.0),
        "hybrid_sample_fraction": 0.0,
        "marginal_mode_entropy_bits": _binary_entropy(float(shared_latents.mean())),
        "coherent_scene_entropy_bits": _binary_entropy(float(shared_latents.mean())),
        "balanced_posterior_frequency_error": float(abs(shared_latents.mean() - 0.5)),
        "repeat_query_consistency": float(np.mean(shared_latents == repeated_latents)),
        "best_hypothesis_rmse_m": 0.0,
        "evidence_rmse_m": shared_rmse,
        "worst_sample_evidence_rmse_m": shared_worst_rmse,
        "evidence_consistency": shared_consistency,
    }
    return {
        "independent_points": independent,
        "shared_scene_latent": shared,
    }


def generate_ambiguity_failure_sweep(
    sweep_steps: int,
) -> tuple[list[dict[str, str | int | float]], list[float]]:
    """Recompute the resolution sweep and its chart values from the contract."""
    if sweep_steps < 2:
        raise ValueError("the ambiguity failure sweep needs at least two steps")
    point_counts = np.unique(
        np.rint(np.geomspace(17, 16385, sweep_steps)).astype(int)
    )
    rows: list[dict[str, str | int | float]] = []
    coherence: list[float] = []
    reference_shared_latents: np.ndarray | None = None
    for point_count in point_counts:
        fixture = generate_ambiguity_fixture(
            samples=AMBIGUITY_SWEEP_SAMPLES,
            hidden_points_per_sample=int(point_count),
            seed=AMBIGUITY_RANDOM_SEED,
        )
        summaries = evaluate_ambiguity_fixture(fixture)
        independent = summaries["independent_points"]
        shared = summaries["shared_scene_latent"]
        shared_latents = fixture["shared_scene_latents"]
        if reference_shared_latents is None:
            reference_shared_latents = shared_latents.copy()
        resolution_consistency = float(
            np.mean(shared_latents == reference_shared_latents)
        )
        coherence.append(float(independent["within_sample_coherence"]))
        for metric, measurement in (
            ("independent_point_coherence", independent["within_sample_coherence"]),
            ("independent_hybrid_fraction", independent["hybrid_sample_fraction"]),
            (
                "independent_repeat_query_consistency",
                independent["repeat_query_consistency"],
            ),
            ("shared_latent_coherence", shared["within_sample_coherence"]),
            (
                "shared_repeat_query_consistency",
                shared["repeat_query_consistency"],
            ),
            ("shared_resolution_latent_consistency", resolution_consistency),
        ):
            rows.append(
                {
                    "parameter": "points_per_sample",
                    "value": int(point_count),
                    "metric": metric,
                    "measurement": float(measurement),
                }
            )
    return rows, coherence
