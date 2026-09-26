"""Validate complete pathway runs and their recorded provenance."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from contracts import IMPLEMENTATION_FILES, INPUT_FILES, ROOT, canonical_json, ensure_finite, load_json, sha256_file, validate_json_schema_instance


REQUIRED_TOP_LEVEL = {
    "schema_version", "module_id", "profile", "status", "network_mode",
    "measurement_kind", "metrics", "metric_provenance", "failure_sweep", "failure_sweep_provenance", "resources", "provenance",
}


def _require_type(value: Any, expected: type, location: str) -> None:
    if not isinstance(value, expected):
        raise ValueError(f"schema type mismatch at {location}: expected {expected.__name__}")


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
