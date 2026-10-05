"""Validate complete pathway runs and their recorded provenance."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

import numpy as np

from contracts import (
    IMPLEMENTATION_FILES,
    INPUT_FILES,
    ROOT,
    canonical_json,
    ensure_finite,
    full_acceptance_status,
    landed_reference_adapter_names,
    load_json,
    module_by_id,
    reference_adapter_by_name,
    sha256_file,
    validate_json_schema_instance,
)
from controlled_suite import COMPATIBLE_MODULES, controlled_suite_record
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
from surflo_endpoint import build_surflo_endpoint, evaluate_surflo_evidence
from reporting import aggregate_report, module_report
from reference_runner import validate_landed_reference_result


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


def _validate_module15(run_dir: Path, result: dict[str, Any]) -> None:
    archive_path = run_dir / "artifacts" / "surflo_endpoint_evidence.npz"
    endpoint_path = run_dir / "artifacts" / "surflo_endpoint.json"
    if not archive_path.is_file() or not endpoint_path.is_file():
        raise ValueError("Module 15 recomputation artifacts are missing")
    paired_path = ROOT.parent / "photoreal-scenes" / "results.json"
    scout_path = ROOT.parent / "insula-scout" / "results.json"
    locks = {
        item["id"]: item for item in load_json(ROOT / "assets.lock.json")["assets"]
    }
    paired_hash = sha256_file(paired_path)
    scout_hash = sha256_file(scout_path)
    if (
        paired_hash != locks["surflo-paired-scenes"]["sha256"]
        or locks["surflo-paired-scenes"].get("inference_mode") != "plain"
        or result.get("source_results_sha256") != paired_hash
        or scout_hash != locks["surflo-visible-scout"]["sha256"]
        or result.get("scout_results_sha256") != scout_hash
        or result.get("source_result_status") != "pass"
    ):
        raise ValueError("Module 15 source result does not match asset locks")
    expected = build_surflo_endpoint(
        load_json(paired_path),
        load_json(scout_path),
        paired_sha256=paired_hash,
        scout_sha256=scout_hash,
    )
    try:
        with np.load(archive_path, allow_pickle=False) as archive:
            arrays = {name: archive[name] for name in archive.files}
    except (OSError, ValueError) as error:
        raise ValueError("Module 15 evidence archive is invalid") from error
    if set(arrays) != set(expected["arrays"]) or any(
        not np.array_equal(arrays[name], expected["arrays"][name])
        for name in expected["arrays"]
    ):
        raise ValueError("Module 15 evidence does not match locked sources")
    recomputed = evaluate_surflo_evidence(arrays)
    if result["metrics"] != recomputed["metrics"]:
        raise ValueError("Module 15 metric mismatch")
    if result["metrics"]["rendering"]:
        raise ValueError("Module 15 unsupported rendering metric family is non-empty")
    endpoint = load_json(endpoint_path)
    if endpoint != expected["record"]:
        raise ValueError("Module 15 endpoint record mismatch")
    csv_sweep = _load_failure_sweep(
        run_dir / "artifacts" / "failure_sweep.csv",
        "Module 15",
    )
    if result["failure_sweep"] != recomputed["sweep"] or csv_sweep != recomputed["sweep"]:
        raise ValueError("Module 15 failure sweep mismatch")


def validate_result(run_dir: Path, expected_module: str | None = None) -> dict[str, Any]:
    result_path = run_dir / "result.json"
    if not result_path.is_file():
        raise ValueError(f"missing result: {result_path}")
    result = load_json(result_path)
    resources = result.get("resources")
    if isinstance(resources, dict) and (
        (
            "network_isolation" in resources
            and resources["network_isolation"] != "python_socket_guard"
        )
        or (
            "cpu_memory_scope" in resources
            and resources["cpu_memory_scope"]
            != "process_lifetime_high_water_mark"
        )
    ):
        raise ValueError("fixture runtime contract mismatch")
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
    expected_measurement_kind = (
        "reused_measured_result"
        if result["module_id"] == "15"
        else "controlled_fixture"
    )
    if result["measurement_kind"] != expected_measurement_kind:
        raise ValueError("measurement kind does not match module contract")
    if result["failure_sweep_provenance"] != expected_measurement_kind:
        raise ValueError("failure sweep provenance mismatch")
    _require_type(result["metrics"], dict, "metrics")
    _require_type(result["failure_sweep"], list, "failure_sweep")
    for family, metrics in result["metrics"].items():
        _require_type(metrics, dict, f"metrics.{family}")
        if set(result["metric_provenance"].get(family, {})) != set(metrics):
            raise ValueError(f"metric provenance mismatch for {family}")
        if any(
            value != expected_measurement_kind
            for value in result["metric_provenance"][family].values()
        ):
            raise ValueError(f"metric provenance value mismatch for {family}")
    if len(result["failure_sweep"]) < 2:
        raise ValueError("failure sweep is incomplete")
    for required in ("runtime_seconds", "peak_cpu_bytes", "peak_gpu_bytes"):
        if required not in result["resources"]:
            raise ValueError(f"resources missing {required}")
    if (
        result["resources"].get("network_isolation") != "python_socket_guard"
        or result["resources"].get("cpu_memory_scope")
        != "process_lifetime_high_water_mark"
    ):
        raise ValueError("fixture runtime contract mismatch")
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
    if provenance["artifact_provenance"] != {
        name: expected_measurement_kind for name in recorded
    }:
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
    if result["module_id"] == "13":
        _validate_module13(run_dir, result)
    if result["module_id"] == "14":
        _validate_module14(run_dir, result)
    if result["module_id"] == "15":
        _validate_module15(run_dir, result)
    controlled = result.get("controlled_suite")
    controlled_artifact = artifacts / "controlled-suite.json"
    if result["profile"] == "smoke":
        if controlled is not None or provenance["config"].get("controlled_suite") is not None:
            raise ValueError("smoke result unexpectedly binds the Blender controlled suite")
        if controlled_artifact.exists():
            raise ValueError("smoke result contains a controlled-suite artifact")
    else:
        if result["module_id"] not in COMPATIBLE_MODULES:
            raise ValueError("full module is not registered as a controlled-suite consumer")
        if not isinstance(controlled, dict) or not controlled_artifact.is_file():
            raise ValueError("full result lacks its Blender controlled-suite binding")
        payload = load_json(controlled_artifact)
        record = controlled_suite_record()
        if (
            payload.get("schema_version") != 1
            or payload.get("module_id") != result["module_id"]
            or payload.get("suite") != controlled
            or provenance["config"].get("controlled_suite") != controlled
            or controlled.get("asset_id") != "controlled-suite"
            or controlled.get("episode_id") != record["episode_id"]
            or controlled.get("recipe_sha256") != record["sha256"]
            or controlled.get("episode_manifest_sha256")
            != record["episode_manifest_sha256"]
            or controlled.get("validation_sha256") != record["validation_sha256"]
            or controlled.get("artifact_count") != record["artifact_count"]
            or controlled.get("renderer", {}).get("blender_version")
            != record["blender_version"]
            or controlled.get("renderer", {}).get("profile") != record["profile"]
            or controlled.get("renderer", {}).get("samples") != record["samples"]
            or controlled.get("views")
            != {
                "context": record["context_views"],
                "target_per_hypothesis": record["target_views_per_hypothesis"],
            }
            or controlled.get("surface_points_per_hypothesis")
            != record["surface_points_per_hypothesis"]
        ):
            raise ValueError("Blender controlled-suite result binding mismatch")
        sensors = payload.get("sensor_simulations")
        if (
            not isinstance(sensors, dict)
            or sensors.get("schema_version") != 1
            or sensors.get("source_view") != "shared_context/0000"
            or sensors.get("depth_units") != "metres"
            or not isinstance(sensors.get("valid_pixels"), int)
            or sensors["valid_pixels"] <= 0
            or not isinstance(sensors.get("lidar_return_count"), int)
            or sensors["lidar_return_count"] <= 0
        ):
            raise ValueError("Blender controlled-suite sensor binding mismatch")
    if (run_dir / "report.md").read_text(encoding="utf-8") != module_report(
        module_by_id(result["module_id"]), result
    ):
        raise ValueError("report content does not match result")
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
    module_paths = sorted(run_root.glob("[0-9][0-9]/result.json"))
    actual_module_hashes = {
        path.relative_to(run_root).as_posix(): sha256_file(path) for path in module_paths
    }
    if manifest["module_results_sha256"] != actual_module_hashes:
        raise ValueError("aggregate module result hash mismatch")
    reference_paths = sorted(run_root.glob("references/*/result.json"))
    actual_reference_hashes = {
        path.relative_to(run_root).as_posix(): sha256_file(path)
        for path in reference_paths
    }
    if manifest["reference_results_sha256"] != actual_reference_hashes:
        raise ValueError("aggregate reference result hash mismatch")

    actual_modules = [path.parent.name for path in module_paths]
    if manifest["module_ids"] != actual_modules:
        raise ValueError("aggregate report module list mismatch")
    expected = [f"{index:02d}" for index in range(1, 16)]
    if manifest["complete_curriculum"] != (actual_modules == expected):
        raise ValueError("aggregate completeness flag mismatch")
    module_items = [
        (module_by_id(path.parent.name), validate_result(path.parent, path.parent.name))
        for path in module_paths
    ]
    reference_by_name = {
        path.parent.name: validate_landed_reference_result(path.parent, path.parent.name)
        for path in reference_paths
    }
    expected_references = landed_reference_adapter_names()
    unknown_references = sorted(set(reference_by_name) - set(expected_references))
    if unknown_references:
        raise ValueError(
            f"aggregate contains unregistered reference adapters: {unknown_references}"
        )
    reference_items = [
        (reference_adapter_by_name(adapter), reference_by_name[adapter])
        for adapter in expected_references
        if adapter in reference_by_name
    ]
    reference_names = [result["adapter"] for _, result in reference_items]
    profiles = sorted({result["profile"] for _, result in module_items})
    reference_profiles = sorted({result["profile"] for _, result in reference_items})
    complete_references = reference_names == expected_references
    expected_fields = {
        "run_id": run_root.name,
        "profiles": profiles,
        "measurement_kinds": sorted(
            {result["measurement_kind"] for _, result in module_items}
        ),
        "metric_families": ["geometry", "rendering", "generative"],
        "assumptions": [
            "Metrics remain separated by task family.",
            "Controlled fixtures are not third-party benchmark reproductions.",
        ],
        "failure_interpretations": {
            result["module_id"]: result.get("observations", [])
            for _, result in module_items
        },
        "module_resources": {
            result["module_id"]: result["resources"] for _, result in module_items
        },
        "reference_adapters": reference_names,
        "reference_profiles": reference_profiles,
        "complete_reference_suite": complete_references,
        "full_acceptance": full_acceptance_status(
            actual_modules,
            expected,
            profiles,
            reference_names,
            expected_references,
            reference_profiles,
        ),
        "reference_failure_boundaries": {
            result["adapter"]: record.get(
                "measurement_note", "See the adapter evaluation contract."
            )
            for record, result in reference_items
        },
        "source_ids": sorted(
            {
                source
                for module, _ in module_items
                for source in module["sources"]
            }
        ),
    }
    for name, expected_value in expected_fields.items():
        if manifest.get(name) != expected_value:
            raise ValueError(f"aggregate {name.replace('_', ' ')} mismatch")
    expected_report = aggregate_report(
        run_root.name,
        module_items,
        reference_items,
    )
    if (run_root / "report.md").read_text(encoding="utf-8") != expected_report:
        raise ValueError("aggregate report content mismatch")
    ensure_finite(manifest)
    return manifest
