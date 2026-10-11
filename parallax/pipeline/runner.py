"""Offline lab execution with validation-before-atomic-promotion."""

from __future__ import annotations

import os
import platform
from pathlib import Path
import resource
import shutil
import socket
import sys
import time
import uuid
from contextlib import contextmanager
from typing import Any

from pipeline.contracts import IMPLEMENTATION_FILES, INPUT_FILES, ROOT, canonical_json, curriculum, module_by_id, sha256_file, validate_run_id, write_json
from curriculum.labs import run_lab
from pipeline.reporting import module_report
from pipeline.validator import validate_result
from scene.controlled_suite import ensure_controlled_suite, write_module_binding


SYNTHETIC_ILLUSTRATIVE_METRICS = {
    "02": {"geometry": {"photometric_normal_error_deg", "visual_hull_iou", "concavity_recall"}},
    "03": {"geometry": {"multipath_bias_m"}},
    "04": {"geometry": {"mesh_completeness"}},
    "05": {"geometry": {"inlier_fraction", "similarity_gauge_dof"}},
    "07": {"geometry": {"map_f_score"}},
    "08": {"geometry": {"unsupported_completion_fraction", "geometric_weak_match_rmse_m"}},
    "11": {"geometry": {"mesh_extraction_supported"}},
}


def _peak_cpu_bytes() -> int:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak * 1024 if sys.platform != "darwin" else peak)


def _artifact_hashes(artifacts: Path) -> dict[str, str]:
    return {
        path.relative_to(artifacts).as_posix(): sha256_file(path)
        for path in sorted(artifacts.rglob("*")) if path.is_file()
    }


def _hash_map(names: tuple[str, ...]) -> dict[str, str]:
    return {name: sha256_file(ROOT / name) for name in names}


@contextmanager
def offline_network():
    """Fail closed if a concept lab attempts an outbound socket."""
    original_socket = socket.socket
    original_connection = socket.create_connection

    def blocked(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("network access is disabled during offline lab execution")

    socket.socket = blocked  # type: ignore[assignment]
    socket.create_connection = blocked  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket = original_socket  # type: ignore[assignment]
        socket.create_connection = original_connection  # type: ignore[assignment]


def _default_metric_label(implementation: str) -> str:
    if implementation == "synthetic":
        return "computed_synthetic"
    if implementation == "real":
        return "computed_real"
    if implementation == "real+baseline":
        return "computed_real"
    raise ValueError(f"unknown implementation status: {implementation}")


def _metric_provenance(
    module_id: str,
    metrics: dict[str, Any],
    implementation: str,
) -> dict[str, dict[str, str]]:
    default = _default_metric_label(implementation)
    provenance = {
        family: {name: default for name in values}
        for family, values in metrics.items()
    }
    if implementation == "synthetic":
        for family, names in SYNTHETIC_ILLUSTRATIVE_METRICS.get(module_id, {}).items():
            family_provenance = provenance.get(family, {})
            missing = sorted(set(names) - set(family_provenance))
            if missing:
                raise ValueError(
                    f"illustrative metric labels reference unknown metrics for {module_id}: {missing}"
                )
            for name in names:
                family_provenance[name] = "illustrative"
    return provenance


def run_module(cache_root: Path, module_id: str, profile: str, run_id: str) -> Path:
    validate_run_id(run_id)
    module = module_by_id(module_id)
    module_id = module["id"]
    if profile not in {"smoke", "full"}:
        raise ValueError(f"unknown profile: {profile}")
    final = cache_root / "runs" / run_id / module_id
    if final.exists():
        raise FileExistsError(f"run already exists: {final}")
    staging_root = cache_root / "staging"
    staging_root.mkdir(parents=True, exist_ok=True)
    staging = staging_root / f"{run_id}.{module_id}.{uuid.uuid4().hex}"
    staging.mkdir()
    started = time.perf_counter()
    try:
        controlled_suite = None
        if profile == "full":
            suite_root = ensure_controlled_suite(render_if_missing=True)
        with offline_network():
            lab = run_lab(module_id, staging / "artifacts", profile)
            if profile == "full":
                controlled_suite = write_module_binding(
                    suite_root,
                    staging / "artifacts" / "controlled-suite.json",
                    module_id,
                )["suite"]
                lab.setdefault("observations", []).append(
                    "This full-profile lab is bound to the shared hash-verified Blender/Cycles "
                    "episode; its task-specific fixture metrics are not relabeled as benchmark scores."
                )
        elapsed = time.perf_counter() - started
        profile_config = curriculum()["profiles"][profile]
        module_implementation = module["implementation"]
        config = {
            "module_id": module_id,
            "module_implementation": module_implementation,
            "profile": profile,
            "run_id": run_id,
            "seed": 260925,
            "profile_config": profile_config,
            "controlled_suite": controlled_suite,
        }
        measurement_kind = "reused_measured_result" if module_id == "15" else "controlled_fixture"
        artifacts_sha256 = _artifact_hashes(staging / "artifacts")
        result: dict[str, Any] = {
            "schema_version": 1,
            "module_id": module_id,
            "module_slug": module["slug"],
            "module_implementation": module_implementation,
            "profile": profile,
            "status": "complete",
            "network_mode": "offline",
            "measurement_kind": measurement_kind,
            "metrics": lab["metrics"],
            "metric_provenance": _metric_provenance(
                module_id,
                lab["metrics"],
                module_implementation,
            ),
            "failure_sweep": lab["failure_sweep"],
            "failure_sweep_provenance": measurement_kind,
            "observations": lab.get("observations", []),
            "controlled_suite": controlled_suite,
            "resources": {
                "runtime_seconds": elapsed,
                "peak_cpu_bytes": _peak_cpu_bytes(),
                "peak_gpu_bytes": 0,
                "gpu": os.environ.get("NVIDIA_VISIBLE_DEVICES", "not-used"),
                "network_isolation": "python_socket_guard",
                "cpu_memory_scope": "process_lifetime_high_water_mark",
            },
            "provenance": {
                "environment": {
                    "python": platform.python_version(),
                    "platform": platform.platform(),
                    "implementation": platform.python_implementation(),
                },
                "config": config,
                "inputs_sha256": _hash_map(INPUT_FILES),
                "config_sha256": __import__("hashlib").sha256(canonical_json(config)).hexdigest(),
                "implementation_sha256": _hash_map(IMPLEMENTATION_FILES),
                "artifacts_sha256": artifacts_sha256,
                "artifact_provenance": {name: measurement_kind for name in artifacts_sha256},
                "reports_sha256": {},
            },
        }
        result.update(lab.get("extra_result", {}))
        write_json(staging / "result.json", result)
        (staging / "report.md").write_text(module_report(module, result), encoding="utf-8")
        result["provenance"]["reports_sha256"] = {"report.md": sha256_file(staging / "report.md")}
        write_json(staging / "result.json", result)
        validate_result(staging, expected_module=module_id)
        final.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, final)
        return final
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
