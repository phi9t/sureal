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

from contracts import IMPLEMENTATION_FILES, INPUT_FILES, ROOT, canonical_json, curriculum, module_by_id, sha256_file, validate_run_id, write_json
from labs import run_lab
from reporting import module_report
from validator import validate_result


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


def _metric_provenance(metrics: dict[str, Any], kind: str) -> dict[str, dict[str, str]]:
    return {
        family: {name: kind for name in values}
        for family, values in metrics.items()
    }


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
        with offline_network():
            lab = run_lab(module_id, staging / "artifacts", profile)
        elapsed = time.perf_counter() - started
        profile_config = curriculum()["profiles"][profile]
        config = {"module_id": module_id, "profile": profile, "run_id": run_id, "seed": 260925, "profile_config": profile_config}
        measurement_kind = "reused_measured_result" if module_id == "15" else "controlled_fixture"
        artifacts_sha256 = _artifact_hashes(staging / "artifacts")
        result: dict[str, Any] = {
            "schema_version": 1,
            "module_id": module_id,
            "module_slug": module["slug"],
            "profile": profile,
            "status": "complete",
            "network_mode": "offline",
            "measurement_kind": measurement_kind,
            "metrics": lab["metrics"],
            "metric_provenance": _metric_provenance(lab["metrics"], measurement_kind),
            "failure_sweep": lab["failure_sweep"],
            "failure_sweep_provenance": measurement_kind,
            "observations": lab.get("observations", []),
            "resources": {
                "runtime_seconds": elapsed,
                "peak_cpu_bytes": _peak_cpu_bytes(),
                "peak_gpu_bytes": 0,
                "gpu": os.environ.get("NVIDIA_VISIBLE_DEVICES", "not-used"),
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
