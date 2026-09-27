"""Recompute the Surflo endpoint from the repository's measured evidence."""

from __future__ import annotations

import math
from typing import Any

import numpy as np


PAIRED_NUMERIC_FIELDS = (
    "observed_common_recall",
    "unobserved_common_recall",
    "exclusive_hidden_support_a",
    "exclusive_hidden_support_b",
    "completion_candidate_precision_to_either_hypothesis",
    "camera_rmse_after_observed_alignment",
    "wall_seconds",
    "peak_vram_gib",
)
PAIRED_PROBABILITY_FIELDS = PAIRED_NUMERIC_FIELDS[:5]
SURFLO_METHODS = ("surflo/plain", "surflo/guided-no-densification")
ALLOWED_LABELS = {"unsupported", "hybrid", "scene_a", "scene_b"}
SUPPORT_THRESHOLD = 0.10
HYBRID_MINORITY_RATIO = 0.60

SURFLO_ARRAY_SEMANTICS = {
    "paired_camera_rmse_m": "camera-centre RMSE after alignment using observed evidence only, one value per seed",
    "paired_completion_precision": "fraction of completion candidates close to either complete hidden hypothesis, one value per seed",
    "paired_hidden_support_a": "recall of scene-A-exclusive hidden target-visible surface, one value per seed",
    "paired_hidden_support_b": "recall of scene-B-exclusive hidden target-visible surface, one value per seed",
    "paired_labels": "classification recomputed from the two exclusive hidden-support values",
    "paired_observed_recall": "recall of common context-visible surface, one value per seed",
    "paired_peak_vram_gib": "measured peak VRAM, one value per seed",
    "paired_seeds": "Surflo point-noise seeds used by the paired-scene probe",
    "paired_unobserved_recall": "recall of common surface visible only from target views, one value per seed",
    "paired_wall_seconds": "measured inference wall time, one value per seed",
    "scout_chamfer_mean_norm": "normalized Chamfer for each method on the single Ignatius scout scene",
    "scout_eval_seconds": "evaluation seconds excluding model startup for each scout method",
    "scout_f1": "surface F1 for each method on the single Ignatius scout scene",
    "scout_methods": "method identifiers for the Ignatius scout rows",
    "scout_peak_vram_gib": "peak VRAM for each scout method",
}


def _finite_float(value: Any, location: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"non-numeric Surflo evidence at {location}") from error
    if not math.isfinite(number):
        raise ValueError(f"non-finite Surflo evidence at {location}")
    return number


def _classification(support_a: float, support_b: float) -> str:
    largest = max(support_a, support_b)
    smallest = min(support_a, support_b)
    if largest < SUPPORT_THRESHOLD:
        return "unsupported"
    if smallest / max(largest, 1e-12) >= HYBRID_MINORITY_RATIO:
        return "hybrid"
    return "scene_a" if support_a > support_b else "scene_b"


def _source_arrays(
    paired_source: dict[str, Any], scout_source: dict[str, Any]
) -> dict[str, np.ndarray]:
    if (
        paired_source.get("schema_version") != 1
        or paired_source.get("status") != "pass"
    ):
        raise ValueError("paired-scene source is not a passing schema-v1 result")
    settings = paired_source.get("settings")
    runs = paired_source.get("runs")
    if not isinstance(settings, dict) or not isinstance(runs, list):
        raise ValueError("paired-scene source is missing settings or runs")
    seeds = settings.get("seeds")
    if seeds != [0, 1, 2, 3] or len(runs) != len(seeds):
        raise ValueError("paired-scene source must contain ordered seeds 0,1,2,3")
    if settings.get("num_query_points") != 100_000 or settings.get("num_steps") != 100:
        raise ValueError("paired-scene source settings mismatch")

    numeric: dict[str, list[float]] = {field: [] for field in PAIRED_NUMERIC_FIELDS}
    labels: list[str] = []
    for expected_seed, run in zip(seeds, runs, strict=True):
        if not isinstance(run, dict) or run.get("seed") != expected_seed:
            raise ValueError("paired-scene runs are not ordered by declared seed")
        for field in PAIRED_NUMERIC_FIELDS:
            numeric[field].append(
                _finite_float(run.get(field), f"runs[{expected_seed}].{field}")
            )
        if any(
            not 0.0 <= numeric[field][-1] <= 1.0 for field in PAIRED_PROBABILITY_FIELDS
        ):
            raise ValueError(
                f"paired-scene probability is outside [0,1] at seed {expected_seed}"
            )
        if any(numeric[field][-1] < 0.0 for field in PAIRED_NUMERIC_FIELDS):
            raise ValueError(
                f"paired-scene measurement is negative at seed {expected_seed}"
            )
        support_a = numeric["exclusive_hidden_support_a"][-1]
        support_b = numeric["exclusive_hidden_support_b"][-1]
        label = run.get("label")
        if label not in ALLOWED_LABELS or label != _classification(
            support_a, support_b
        ):
            raise ValueError(
                f"paired-scene classification mismatch at seed {expected_seed}"
            )
        labels.append(label)

    aggregate = paired_source.get("aggregate")
    if not isinstance(aggregate, dict):
        raise ValueError("paired-scene source aggregate is missing")
    expected_aggregate = {
        "labels": labels,
        "mean_observed_common_recall": float(
            np.mean(numeric["observed_common_recall"])
        ),
        "mean_unobserved_common_recall": float(
            np.mean(numeric["unobserved_common_recall"])
        ),
        "mean_hidden_support_a": float(np.mean(numeric["exclusive_hidden_support_a"])),
        "mean_hidden_support_b": float(np.mean(numeric["exclusive_hidden_support_b"])),
    }
    for name, expected in expected_aggregate.items():
        actual = aggregate.get(name)
        if isinstance(expected, list):
            matches = actual == expected
        else:
            try:
                matches = math.isclose(
                    float(actual), expected, rel_tol=0.0, abs_tol=1e-12
                )
            except (TypeError, ValueError):
                matches = False
        if not matches:
            raise ValueError(f"source aggregate mismatch: {name}")

    if scout_source.get("schema_version") != 1:
        raise ValueError("Surflo scout source is not schema v1")
    public_eval = scout_source.get("public_eval")
    if (
        not isinstance(public_eval, dict)
        or public_eval.get("benchmark") != "tnt"
        or public_eval.get("scene") != "Ignatius"
    ):
        raise ValueError("Surflo scout source is not the locked Ignatius evaluation")
    scout_runs = public_eval.get("runs")
    if not isinstance(scout_runs, list) or not scout_runs:
        raise ValueError("Surflo scout source has no evaluation runs")
    method_names: list[str] = []
    scout_numeric: dict[str, list[float]] = {
        "chamfer_mean_norm": [],
        "f1": [],
        "eval_seconds_excluding_model_startup": [],
        "peak_vram_gib": [],
    }
    for index, run in enumerate(scout_runs):
        if not isinstance(run, dict) or not isinstance(run.get("method"), str):
            raise ValueError(f"malformed Surflo scout run {index}")
        method_names.append(run["method"])
        for field in scout_numeric:
            scout_numeric[field].append(
                _finite_float(run.get(field), f"public_eval.runs[{index}].{field}")
            )
        if scout_numeric["f1"][-1] < 0.0 or scout_numeric["f1"][-1] > 1.0:
            raise ValueError(f"Surflo scout F1 is outside [0,1] at run {index}")
        if any(scout_numeric[field][-1] < 0.0 for field in scout_numeric):
            raise ValueError(f"Surflo scout measurement is negative at run {index}")
    if not set(SURFLO_METHODS).issubset(method_names) or "vggt" not in method_names:
        raise ValueError("Surflo scout source is missing required method rows")

    return {
        "paired_seeds": np.asarray(seeds, dtype=np.int64),
        "paired_labels": np.asarray(labels, dtype="<U11"),
        "paired_observed_recall": np.asarray(
            numeric["observed_common_recall"], dtype=np.float64
        ),
        "paired_unobserved_recall": np.asarray(
            numeric["unobserved_common_recall"], dtype=np.float64
        ),
        "paired_hidden_support_a": np.asarray(
            numeric["exclusive_hidden_support_a"], dtype=np.float64
        ),
        "paired_hidden_support_b": np.asarray(
            numeric["exclusive_hidden_support_b"], dtype=np.float64
        ),
        "paired_completion_precision": np.asarray(
            numeric["completion_candidate_precision_to_either_hypothesis"],
            dtype=np.float64,
        ),
        "paired_camera_rmse_m": np.asarray(
            numeric["camera_rmse_after_observed_alignment"], dtype=np.float64
        ),
        "paired_wall_seconds": np.asarray(numeric["wall_seconds"], dtype=np.float64),
        "paired_peak_vram_gib": np.asarray(numeric["peak_vram_gib"], dtype=np.float64),
        "scout_methods": np.asarray(method_names, dtype="<U32"),
        "scout_chamfer_mean_norm": np.asarray(
            scout_numeric["chamfer_mean_norm"], dtype=np.float64
        ),
        "scout_f1": np.asarray(scout_numeric["f1"], dtype=np.float64),
        "scout_eval_seconds": np.asarray(
            scout_numeric["eval_seconds_excluding_model_startup"], dtype=np.float64
        ),
        "scout_peak_vram_gib": np.asarray(
            scout_numeric["peak_vram_gib"], dtype=np.float64
        ),
    }


def evaluate_surflo_evidence(arrays: dict[str, np.ndarray]) -> dict[str, Any]:
    """Derive endpoint metrics only from persisted measured arrays."""
    if set(arrays) != set(SURFLO_ARRAY_SEMANTICS):
        raise ValueError("Surflo evidence array set mismatch")
    seeds = np.asarray(arrays["paired_seeds"])
    labels = np.asarray(arrays["paired_labels"])
    if (
        seeds.shape != (4,)
        or not np.array_equal(seeds, np.arange(4))
        or labels.shape != (4,)
    ):
        raise ValueError("Surflo paired evidence shape mismatch")
    for name, values in arrays.items():
        values = np.asarray(values)
        if name in {"paired_labels", "scout_methods"}:
            continue
        if values.ndim != 1 or not np.all(np.isfinite(values)):
            raise ValueError(f"Surflo evidence array is invalid: {name}")
    paired_numeric_names = {name for name in arrays if name.startswith("paired_")} - {
        "paired_seeds",
        "paired_labels",
    }
    if any(np.asarray(arrays[name]).shape != (4,) for name in paired_numeric_names):
        raise ValueError("Surflo paired numeric evidence shape mismatch")
    paired_probabilities = (
        "paired_observed_recall",
        "paired_unobserved_recall",
        "paired_hidden_support_a",
        "paired_hidden_support_b",
        "paired_completion_precision",
    )
    if any(
        np.any((np.asarray(arrays[name]) < 0.0) | (np.asarray(arrays[name]) > 1.0))
        for name in paired_probabilities
    ):
        raise ValueError("Surflo paired probability is outside [0,1]")
    if any(np.any(np.asarray(arrays[name]) < 0.0) for name in paired_numeric_names):
        raise ValueError("Surflo paired evidence contains a negative measurement")
    support_a = np.asarray(arrays["paired_hidden_support_a"], dtype=np.float64)
    support_b = np.asarray(arrays["paired_hidden_support_b"], dtype=np.float64)
    expected_labels = np.asarray(
        [_classification(a, b) for a, b in zip(support_a, support_b, strict=True)]
    )
    if not np.array_equal(labels, expected_labels):
        raise ValueError("Surflo paired labels do not match hidden support")

    methods = np.asarray(arrays["scout_methods"])
    if len(set(methods.tolist())) != len(methods):
        raise ValueError("Surflo scout method names are not unique")
    method_index = {str(name): index for index, name in enumerate(methods)}
    if not set((*SURFLO_METHODS, "vggt")).issubset(method_index):
        raise ValueError("Surflo evidence is missing endpoint methods")
    f1 = np.asarray(arrays["scout_f1"], dtype=np.float64)
    chamfer = np.asarray(arrays["scout_chamfer_mean_norm"], dtype=np.float64)
    if any(
        len(np.asarray(arrays[name])) != len(methods)
        for name in (
            "scout_chamfer_mean_norm",
            "scout_f1",
            "scout_eval_seconds",
            "scout_peak_vram_gib",
        )
    ):
        raise ValueError("Surflo scout evidence shape mismatch")
    if np.any((f1 < 0.0) | (f1 > 1.0)):
        raise ValueError("Surflo scout F1 is outside [0,1]")
    if any(
        np.any(np.asarray(arrays[name]) < 0.0)
        for name in (
            "scout_chamfer_mean_norm",
            "scout_eval_seconds",
            "scout_peak_vram_gib",
        )
    ):
        raise ValueError("Surflo scout evidence contains a negative measurement")
    plain = method_index["surflo/plain"]
    guided = method_index["surflo/guided-no-densification"]
    vggt = method_index["vggt"]
    coherent = np.isin(labels, ["scene_a", "scene_b"])
    hybrid = labels == "hybrid"
    unsupported = labels == "unsupported"
    hidden_support = np.maximum(support_a, support_b)
    metrics = {
        "geometry": {
            "scout_surflo_plain_f1": float(f1[plain]),
            "scout_surflo_plain_chamfer_mean_norm": float(chamfer[plain]),
            "scout_surflo_guided_f1": float(f1[guided]),
            "scout_surflo_guided_chamfer_mean_norm": float(chamfer[guided]),
            "scout_vggt_f1": float(f1[vggt]),
            "scout_f1_gain_over_vggt": float(f1[plain] - f1[vggt]),
            "observed_common_recall": float(np.mean(arrays["paired_observed_recall"])),
            "unobserved_common_recall": float(
                np.mean(arrays["paired_unobserved_recall"])
            ),
            "camera_rmse_after_observed_alignment_m": float(
                np.mean(arrays["paired_camera_rmse_m"])
            ),
        },
        "rendering": {},
        "generative": {
            "hidden_hypothesis_support": float(np.mean(hidden_support)),
            "hidden_hypothesis_a_support": float(np.mean(support_a)),
            "hidden_hypothesis_b_support": float(np.mean(support_b)),
            "completion_candidate_precision_to_either_hypothesis": float(
                np.mean(arrays["paired_completion_precision"])
            ),
            "coherent_supported_seed_fraction": float(np.mean(coherent)),
            "hybrid_seed_fraction": float(np.mean(hybrid)),
            "unsupported_seed_fraction": float(np.mean(unsupported)),
        },
    }
    sweep = [
        {
            "parameter": "seed",
            "value": int(seed),
            "metric": "hidden_hypothesis_support",
            "measurement": float(support),
        }
        for seed, support in zip(seeds, hidden_support, strict=True)
    ]
    return {"metrics": metrics, "sweep": sweep}


def build_surflo_endpoint(
    paired_source: dict[str, Any],
    scout_source: dict[str, Any],
    *,
    paired_sha256: str | None = None,
    scout_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate both tracked results and construct a self-describing endpoint."""
    arrays = _source_arrays(paired_source, scout_source)
    evaluated = evaluate_surflo_evidence(arrays)
    array_records = {
        name: {
            "shape": list(array.shape),
            "dtype": str(array.dtype),
            "semantics": SURFLO_ARRAY_SEMANTICS[name],
        }
        for name, array in sorted(arrays.items())
    }
    record = {
        "schema_version": 1,
        "sources": {
            "visible_surface_scout": {
                "path": "experiments/insula-scout/results.json",
                "sha256": scout_sha256,
                "scope": "one Tanks & Temples Ignatius scene; not a benchmark aggregate",
            },
            "paired_hidden_scene": {
                "path": "experiments/photoreal-scenes/results.json",
                "sha256": paired_sha256,
                "scope": "four point-noise seeds under byte-identical ambiguous context",
            },
        },
        "benchmark": {
            "inference_mode": "plain",
            "query_points": int(paired_source["settings"]["num_query_points"]),
            "ode_steps": int(paired_source["settings"]["num_steps"]),
            "seeds": paired_source["settings"]["seeds"],
            "classification_support_threshold": SUPPORT_THRESHOLD,
            "hybrid_minority_ratio": HYBRID_MINORITY_RATIO,
            "favorable_hidden_completion_required": False,
        },
        "architecture": {
            "evidence_encoder": "frozen VGGT-1B",
            "evidence_state": "deterministic_global_tokens",
            "compressor": "Perceiver",
            "decoder": "conditional flow over 6D position-normal query points",
            "stochastic_variable_scope": "query_point",
            "optional_point_coupling": "rendering-guidance gradients during ODE integration",
            "sampled_persistent_scene_state": False,
            "cross_query_hypothesis_persistence": False,
            "mesh_path": "oriented points through Gaussian wrapping",
        },
        "synthesis": {
            "inherits": [
                "feed-forward multi-view visual geometry from VGGT",
                "global cross-view conditioning",
                "flow-matching generation and oriented surface output",
                "optional rendering guidance and mesh extraction",
            ],
            "improves": [
                "output point count is selected at inference rather than fixed by a pointmap grid",
                "the measured scout improves plain surface F1 over the inherited VGGT pointmap on one scene",
            ],
            "not_established": [
                "a posterior over complete scenes",
                "one hypothesis that persists when point count, camera, or time queries change",
                "support for either hidden paired-scene hypothesis in the recorded four seeds",
            ],
            "next_objective": "sample z* from p(z* | O) once, then reuse z* across points, cameras, and time",
        },
        "arrays": array_records,
        "metrics": evaluated["metrics"],
        "seed_outcomes": evaluated["sweep"],
        "resource_summary": {
            "paired_mean_wall_seconds": float(np.mean(arrays["paired_wall_seconds"])),
            "paired_peak_vram_gib": float(np.max(arrays["paired_peak_vram_gib"])),
        },
    }
    return {
        "arrays": arrays,
        "metrics": evaluated["metrics"],
        "sweep": evaluated["sweep"],
        "record": record,
    }
