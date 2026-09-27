#!/usr/bin/env python3
"""Create compact, tracked evidence from a raw stock-Surflo probe."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
import math
from pathlib import Path
from typing import Any


MEASUREMENTS = (
    "observed_common_recall",
    "unobserved_common_recall",
    "exclusive_hidden_support_a",
    "exclusive_hidden_support_b",
    "completion_candidate_precision_to_either_hypothesis",
    "camera_rmse_after_observed_alignment",
    "wall_seconds",
    "peak_vram_gib",
)
SUPPORT_THRESHOLD = 0.10
HYBRID_MINORITY_RATIO = 0.60


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mapping(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def _support_label(support_a: float, support_b: float) -> str:
    largest = max(support_a, support_b)
    smallest = min(support_a, support_b)
    if largest < SUPPORT_THRESHOLD:
        return "unsupported"
    if smallest / max(largest, 1e-12) >= HYBRID_MINORITY_RATIO:
        return "hybrid"
    return "scene_a" if support_a > support_b else "scene_b"


def build_summary(
    raw_path: Path,
    manifest_path: Path,
    validation_path: Path,
    analytic_baseline_path: Path,
    *,
    measurement_date_utc: str,
) -> dict[str, Any]:
    raw_path = Path(raw_path)
    manifest_path = Path(manifest_path)
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validation = json.loads(Path(validation_path).read_text(encoding="utf-8"))
    baseline = json.loads(Path(analytic_baseline_path).read_text(encoding="utf-8"))
    try:
        if date.fromisoformat(measurement_date_utc).isoformat() != measurement_date_utc:
            raise ValueError
    except (TypeError, ValueError) as error:
        raise ValueError("measurement_date_utc must be an ISO 8601 calendar date") from error
    if raw.get("episode_manifest_sha256") != _sha256(manifest_path):
        raise ValueError("raw probe episode hash does not match the supplied manifest")
    if (
        validation.get("status") != "pass"
        or validation.get("episode_manifest_sha256") != _sha256(manifest_path)
    ):
        raise ValueError("validation report is not bound to the supplied manifest")
    settings = _mapping(raw, "settings")
    if settings.get("seeds") != [0, 1, 2, 3]:
        raise ValueError("probe must contain seeds 0,1,2,3")
    if settings.get("inference_mode") != "plain":
        raise ValueError("probe must record plain inference mode")
    if settings.get("num_query_points") != 100_000 or settings.get("num_steps") != 100:
        raise ValueError("probe must use 100000 queries and 100 ODE steps")
    raw_runs = raw.get("runs")
    if not isinstance(raw_runs, list) or len(raw_runs) != 4:
        raise ValueError("probe must contain four runs")

    runs = []
    support_labels = []
    for expected_seed, run in enumerate(raw_runs):
        if not isinstance(run, dict) or run.get("seed") != expected_seed:
            raise ValueError("probe runs must be ordered seeds 0,1,2,3")
        values = {name: float(run[name]) for name in MEASUREMENTS}
        if not all(math.isfinite(value) for value in values.values()):
            raise ValueError(f"probe seed {expected_seed} contains non-finite measurements")
        hypothesis = _mapping(run, "hypothesis")
        raw_label = hypothesis.get("label")
        support_label = _support_label(
            values["exclusive_hidden_support_a"],
            values["exclusive_hidden_support_b"],
        )
        if raw_label != support_label:
            raise ValueError(
                f"probe seed {expected_seed} support classification mismatch: "
                f"raw={raw_label}, recomputed={support_label}"
            )
        support_labels.append(support_label)
        runs.append(
            {"seed": expected_seed, "support_label": support_label, **values}
        )

    renderer = _mapping(manifest, "renderer")
    scenes = _mapping(manifest, "scenes")
    aggregate = _mapping(raw, "aggregate")
    if aggregate.get("labels") != support_labels:
        raise ValueError("raw aggregate labels do not match per-seed support labels")
    derived_aggregate = {
        key: value for key, value in aggregate.items() if key != "labels"
    }
    derived_aggregate["support_labels"] = support_labels
    analytic_aggregate = _mapping(baseline, "aggregate")
    checkpoint = _mapping(raw, "checkpoint")
    vggt = _mapping(raw, "vggt")
    source = _mapping(raw, "source")
    return {
        "schema_version": 2,
        "status": "pass",
        "measurement_date_utc": measurement_date_utc,
        "question": raw.get("question"),
        "episode": {
            "schema_version": manifest.get("schema_version"),
            "manifest_sha256": _sha256(manifest_path),
            "profile": renderer.get("profile"),
            "device": renderer.get("device"),
            "visibility": {
                scene_name: _mapping(_mapping(scenes, scene_name), "visibility")
                for scene_name in ("scene_a", "scene_b")
            },
        },
        "checkpoint_sha256": checkpoint.get("sha256"),
        "model_provenance": {
            "checkpoint_sha256": checkpoint.get("sha256"),
            "vggt": vggt,
        },
        "source": source,
        "settings": {
            "inference_mode": settings["inference_mode"],
            "seeds": settings["seeds"],
            "num_query_points": settings["num_query_points"],
            "num_steps": settings["num_steps"],
            "tau_scene_diagonal_fraction": settings.get("tau_scene_diagonal_fraction"),
            "tau": settings.get("tau"),
        },
        "runs": runs,
        "aggregate": derived_aggregate,
        "comparison": {
            "analytic_baseline_path": "../insula-scout/synthetic_results.json",
            "analytic_baseline_behavior": analytic_aggregate.get("baseline_behavior"),
            "photoreal_behavior": aggregate.get("baseline_behavior"),
            "favorable_outcome_required": False,
        },
        "artifacts": {
            "raw_results_sha256": _sha256(raw_path),
            "validation_report_sha256": _sha256(validation_path),
        },
        "acceptance": {
            "all_four_seeds_complete": True,
            "valid_measurements": True,
            "classification_outcome_gated": False,
        },
        "interpretation_guardrail": raw.get("interpretation_guardrail"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--analytic-baseline", type=Path, required=True)
    parser.add_argument("--measurement-date-utc", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build_summary(
        args.raw,
        args.manifest,
        args.validation,
        args.analytic_baseline,
        measurement_date_utc=args.measurement_date_utc,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "pass", "output": str(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
