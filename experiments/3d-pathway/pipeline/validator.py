"""Validate complete pathway runs and their recorded provenance."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

import numpy as np

from contracts import IMPLEMENTATION_FILES, INPUT_FILES, ROOT, canonical_json, ensure_finite, load_json, sha256_file, validate_json_schema_instance
from dynamic import (
    DYNAMIC_ARRAY_SEMANTICS,
    DYNAMIC_CAMERA_CONTAMINATION,
    DYNAMIC_PROFILE_FRAMES,
    DYNAMIC_PROFILE_MAX_OCCLUSION,
    DYNAMIC_VARIANTS,
    dynamic_result_metrics,
    evaluate_dynamic_fixture,
    generate_dynamic_failure_sweep,
    generate_dynamic_fixture,
)
from generative import (
    AMBIGUITY_ARRAY_SEMANTICS,
    AMBIGUITY_PROFILE_POINTS,
    AMBIGUITY_RANDOM_SEED,
    COHERENT_SAMPLE_THRESHOLD,
    EVIDENCE_TOLERANCE_M,
    evaluate_ambiguity_fixture,
    generate_ambiguity_failure_sweep,
)


REQUIRED_TOP_LEVEL = {
    "schema_version", "module_id", "profile", "status", "network_mode",
    "measurement_kind", "metrics", "metric_provenance", "failure_sweep", "failure_sweep_provenance", "resources", "provenance",
}


def _require_type(value: Any, expected: type, location: str) -> None:
    if not isinstance(value, expected):
        raise ValueError(f"schema type mismatch at {location}: expected {expected.__name__}")


def _load_failure_sweep(path: Path, module_label: str) -> list[dict[str, str | int | float]]:
    try:
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != ["parameter", "value", "metric", "measurement"]:
                raise ValueError(f"{module_label} failure sweep mismatch")
            return [
                {
                    "parameter": row["parameter"],
                    "value": int(row["value"]),
                    "metric": row["metric"],
                    "measurement": float(row["measurement"]),
                }
                for row in reader
            ]
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise ValueError(f"{module_label} failure sweep mismatch") from error


def _validate_module13(run_dir: Path, result: dict[str, Any]) -> None:
    archive_path = run_dir / "artifacts" / "ambiguity_samples.npz"
    comparison_path = run_dir / "artifacts" / "ambiguity_comparison.json"
    if not archive_path.is_file() or not comparison_path.is_file():
        raise ValueError("Module 13 recomputation artifacts are missing")
    try:
        with np.load(archive_path, allow_pickle=False) as archive:
            fixture = {name: archive[name] for name in archive.files}
    except (OSError, ValueError) as error:
        raise ValueError("Module 13 ambiguity archive is invalid") from error
    recomputed = evaluate_ambiguity_fixture(fixture)
    comparison = load_json(comparison_path)
    profile_config = load_json(ROOT / "curriculum.json")["profiles"][result["profile"]]
    expected_assignment_shape = (
        int(profile_config["samples"]),
        AMBIGUITY_PROFILE_POINTS[result["profile"]],
    )
    if fixture["independent_assignments"].shape != expected_assignment_shape:
        raise ValueError("Module 13 fixture/profile mismatch")
    expected_array_records = {
        name: {
            "shape": list(array.shape),
            "dtype": str(array.dtype),
            "semantics": AMBIGUITY_ARRAY_SEMANTICS[name],
        }
        for name, array in sorted(fixture.items())
    }
    expected_fixture_record = {
        "evidence": "48 input-visible points on an occluding plane",
        "hidden_hypotheses": "one object translated left or right behind the plane",
        "coordinate_convention": "right-handed xyz in metres",
        "sample_count": int(fixture["independent_assignments"].shape[0]),
        "hidden_points_per_sample": int(fixture["independent_assignments"].shape[1]),
        "random_seed": AMBIGUITY_RANDOM_SEED,
        "evidence_tolerance_m": EVIDENCE_TOLERANCE_M,
        "coherent_sample_threshold": COHERENT_SAMPLE_THRESHOLD,
    }
    if (
        comparison.get("schema_version") != 1
        or comparison.get("fixture") != expected_fixture_record
        or comparison.get("samplers") != recomputed
        or comparison.get("arrays") != expected_array_records
    ):
        raise ValueError("Module 13 ambiguity comparison record mismatch")

    independent = recomputed["independent_points"]
    shared = recomputed["shared_scene_latent"]
    expected_metrics = {
        "independent_point_coherence": independent["within_sample_coherence"],
        "independent_point_hybrid_fraction": independent["hybrid_sample_fraction"],
        "independent_point_hypothesis_coverage": independent["hypothesis_coverage"],
        "independent_point_coherent_hypothesis_coverage": independent[
            "coherent_hypothesis_coverage"
        ],
        "independent_point_evidence_consistency": independent["evidence_consistency"],
        "independent_point_evidence_rmse_m": independent["evidence_rmse_m"],
        "independent_point_worst_sample_evidence_rmse_m": independent[
            "worst_sample_evidence_rmse_m"
        ],
        "independent_point_marginal_mode_entropy_bits": independent[
            "marginal_mode_entropy_bits"
        ],
        "independent_point_coherent_scene_entropy_bits": independent[
            "coherent_scene_entropy_bits"
        ],
        "independent_point_balanced_posterior_frequency_error": independent[
            "balanced_posterior_frequency_error"
        ],
        "independent_point_repeat_query_consistency": independent[
            "repeat_query_consistency"
        ],
        "independent_point_best_hypothesis_rmse_m": independent[
            "best_hypothesis_rmse_m"
        ],
        "shared_latent_coherence": shared["within_sample_coherence"],
        "shared_latent_hypothesis_coverage": shared["hypothesis_coverage"],
        "shared_latent_coherent_hypothesis_coverage": shared[
            "coherent_hypothesis_coverage"
        ],
        "shared_latent_evidence_consistency": shared["evidence_consistency"],
        "shared_latent_evidence_rmse_m": shared["evidence_rmse_m"],
        "shared_latent_worst_sample_evidence_rmse_m": shared[
            "worst_sample_evidence_rmse_m"
        ],
        "shared_latent_scene_entropy_bits": shared["coherent_scene_entropy_bits"],
        "shared_latent_balanced_posterior_frequency_error": shared[
            "balanced_posterior_frequency_error"
        ],
        "shared_latent_repeat_query_consistency": shared["repeat_query_consistency"],
        "shared_latent_best_hypothesis_rmse_m": shared["best_hypothesis_rmse_m"],
    }
    recorded_metrics = result["metrics"]["generative"]
    if set(recorded_metrics) != set(expected_metrics) or any(
        not math.isclose(
            float(recorded_metrics[name]),
            float(expected),
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        for name, expected in expected_metrics.items()
    ):
        raise ValueError("Module 13 metric mismatch")

    expected_sweep, _ = generate_ambiguity_failure_sweep(
        int(profile_config["sweep_steps"])
    )
    csv_sweep = _load_failure_sweep(
        run_dir / "artifacts" / "failure_sweep.csv",
        "Module 13",
    )
    if result["failure_sweep"] != expected_sweep or csv_sweep != expected_sweep:
        raise ValueError("Module 13 failure sweep mismatch")


def _validate_module14(run_dir: Path, result: dict[str, Any]) -> None:
    archive_path = run_dir / "artifacts" / "dynamic_sequence.npz"
    comparison_path = run_dir / "artifacts" / "dynamic_comparison.json"
    if not archive_path.is_file() or not comparison_path.is_file():
        raise ValueError("Module 14 recomputation artifacts are missing")
    try:
        with np.load(archive_path, allow_pickle=False) as archive:
            fixture = {name: archive[name] for name in archive.files}
    except (OSError, ValueError) as error:
        raise ValueError("Module 14 dynamic archive is invalid") from error
    comparison = evaluate_dynamic_fixture(fixture)
    profile = result["profile"]
    frame_count = DYNAMIC_PROFILE_FRAMES[profile]
    max_occlusion = DYNAMIC_PROFILE_MAX_OCCLUSION[profile]
    if (
        fixture["truth_object_xyz"].shape[1] != frame_count
        or int(fixture["reappearance_index"][0])
        - int(fixture["occlusion_start_index"][0])
        != max_occlusion
    ):
        raise ValueError("Module 14 fixture/profile mismatch")
    expected_fixture = generate_dynamic_fixture(frame_count, max_occlusion)
    if set(fixture) != set(expected_fixture) or any(
        not np.array_equal(fixture[name], expected_fixture[name])
        for name in expected_fixture
    ):
        raise ValueError("Module 14 fixture contract mismatch")
    expected_array_records = {
        name: {
            "shape": list(array.shape),
            "dtype": str(array.dtype),
            "semantics": DYNAMIC_ARRAY_SEMANTICS[name],
        }
        for name, array in sorted(fixture.items())
    }
    expected_fixture_record = {
        "event": "two indistinguishable objects reverse while fully occluded",
        "coordinate_convention": "right-handed world xyz in metres",
        "frame_count": frame_count,
        "occlusion_frames": max_occlusion,
        "variants": list(DYNAMIC_VARIANTS),
        "joint_motion_camera_contamination": DYNAMIC_CAMERA_CONTAMINATION,
    }
    comparison_record = load_json(comparison_path)
    if (
        comparison_record.get("schema_version") != 1
        or comparison_record.get("fixture") != expected_fixture_record
        or comparison_record.get("conditions") != comparison
        or comparison_record.get("arrays") != expected_array_records
    ):
        raise ValueError("Module 14 dynamic comparison record mismatch")

    expected_metrics = dynamic_result_metrics(comparison)
    recorded_metrics = result["metrics"]["geometry"]
    if set(recorded_metrics) != set(expected_metrics) or any(
        not math.isclose(
            float(recorded_metrics[name]),
            float(expected),
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        for name, expected in expected_metrics.items()
    ):
        raise ValueError("Module 14 metric mismatch")
    if result["metrics"]["rendering"] or result["metrics"]["generative"]:
        raise ValueError("Module 14 unsupported metric family is non-empty")

    profile_config = load_json(ROOT / "curriculum.json")["profiles"][profile]
    expected_sweep, _ = generate_dynamic_failure_sweep(
        frame_count,
        max_occlusion,
        int(profile_config["sweep_steps"]),
    )
    csv_sweep = _load_failure_sweep(
        run_dir / "artifacts" / "failure_sweep.csv",
        "Module 14",
    )
    if result["failure_sweep"] != expected_sweep or csv_sweep != expected_sweep:
        raise ValueError("Module 14 failure sweep mismatch")


def validate_result(run_dir: Path, expected_module: str | None = None) -> dict[str, Any]:
    result_path = run_dir / "result.json"
    if not result_path.is_file():
        raise ValueError(f"missing result: {result_path}")
    result = load_json(result_path)
    validate_json_schema_instance(result, load_json(ROOT / "result.schema.json"), "result")
    missing = REQUIRED_TOP_LEVEL - set(result)
    if missing:
        raise ValueError(f"result missing keys: {sorted(missing)}")
    if result["schema_version"] != 1 or result["status"] != "complete":
        raise ValueError("result is not a complete schema-v1 record")
    if result["network_mode"] != "offline":
        raise ValueError("lab execution must be offline")
    if result["profile"] not in {"smoke", "full"}:
        raise ValueError("unknown profile")
    if expected_module is not None and result["module_id"] != expected_module:
        raise ValueError(f"expected module {expected_module}, got {result['module_id']}")
    if set(result["metrics"]) != {"geometry", "rendering", "generative"}:
        raise ValueError("metrics must retain geometry, rendering, and generative families")
    if result["measurement_kind"] not in {"controlled_fixture", "reused_measured_result"}:
        raise ValueError("unknown measurement kind")
    if result["failure_sweep_provenance"] != result["measurement_kind"]:
        raise ValueError("failure sweep provenance mismatch")
    _require_type(result["metrics"], dict, "metrics")
    _require_type(result["failure_sweep"], list, "failure_sweep")
    for family, metrics in result["metrics"].items():
        _require_type(metrics, dict, f"metrics.{family}")
        if set(result["metric_provenance"].get(family, {})) != set(metrics):
            raise ValueError(f"metric provenance mismatch for {family}")
    if len(result["failure_sweep"]) < 2:
        raise ValueError("failure sweep is incomplete")
    for required in ("runtime_seconds", "peak_cpu_bytes", "peak_gpu_bytes"):
        if required not in result["resources"]:
            raise ValueError(f"resources missing {required}")
    provenance = result["provenance"]
    for required in ("environment", "config", "inputs_sha256", "config_sha256", "implementation_sha256", "artifacts_sha256", "artifact_provenance", "reports_sha256"):
        if required not in provenance:
            raise ValueError(f"provenance missing {required}")
    artifacts = run_dir / "artifacts"
    recorded = provenance["artifacts_sha256"]
    actual = {
        path.relative_to(artifacts).as_posix(): sha256_file(path)
        for path in sorted(artifacts.rglob("*")) if path.is_file()
    }
    if actual != recorded:
        raise ValueError("artifact hash mismatch")
    if set(provenance["artifact_provenance"]) != set(recorded):
        raise ValueError("artifact provenance mismatch")
    actual_inputs = {name: sha256_file(ROOT / name) for name in INPUT_FILES}
    if provenance["inputs_sha256"] != actual_inputs:
        raise ValueError("input hash mismatch")
    actual_implementation = {name: sha256_file(ROOT / name) for name in IMPLEMENTATION_FILES}
    if provenance["implementation_sha256"] != actual_implementation:
        raise ValueError("implementation hash mismatch")
    actual_config = __import__("hashlib").sha256(canonical_json(provenance["config"])).hexdigest()
    if provenance["config_sha256"] != actual_config:
        raise ValueError("config hash mismatch")
    reports = provenance["reports_sha256"]
    if reports != {"report.md": sha256_file(run_dir / "report.md")}:
        raise ValueError("report hash mismatch")
    if result["module_id"] == "15":
        asset = next(item for item in load_json(ROOT / "assets.lock.json")["assets"] if item["id"] == "surflo-paired-scenes")
        if result.get("source_results_sha256") != asset["sha256"]:
            raise ValueError("Surflo source result does not match asset lock")
    if result["module_id"] == "13":
        _validate_module13(run_dir, result)
    if result["module_id"] == "14":
        _validate_module14(run_dir, result)
    ensure_finite(result)
    return result


def validate_report(run_root: Path) -> dict[str, Any]:
    manifest_path = run_root / "report.json"
    if not manifest_path.is_file():
        raise ValueError(f"missing report manifest: {manifest_path}")
    manifest = load_json(manifest_path)
    validate_json_schema_instance(manifest, load_json(ROOT / "report.schema.json"), "report")
    if manifest["report_sha256"] != sha256_file(run_root / "report.md"):
        raise ValueError("aggregate report hash mismatch")
    actual_modules = [path.parent.name for path in sorted(run_root.glob("[0-9][0-9]/result.json"))]
    if manifest["module_ids"] != actual_modules:
        raise ValueError("aggregate report module list mismatch")
    expected = [f"{index:02d}" for index in range(1, 16)]
    if manifest["complete_curriculum"] != (actual_modules == expected):
        raise ValueError("aggregate completeness flag mismatch")
    ensure_finite(manifest)
    return manifest
