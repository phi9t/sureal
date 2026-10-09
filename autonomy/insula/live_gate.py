"""Minimal live-gate execution and evidence records for Insula-mounted tests."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from evidence.source_snapshot import file_sha256
from insula.launch_plan import build_plan, load_runtime_lock, plan_data, render_plan


@dataclass(frozen=True)
class LiveGate:
    label: str
    rootfs: Path
    lock: Path
    experiment: Path
    fixture: Path
    command: list[str]
    expected_tests: int


def safe_label(label: str) -> str:
    return label.removeprefix("//").replace("/", "_").replace(":", "__")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_unittest_count(text: str) -> int | None:
    match = re.search(r"\bRan (\d+) tests?\b", text)
    return int(match.group(1)) if match else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_live_gate(gate: LiveGate, evidence_root: Path, *, output: Path | None = None, timeout: int = 3600):
    evidence_root = Path(evidence_root)
    output = Path(output) if output is not None else evidence_root / "outputs" / safe_label(gate.label)
    logs = evidence_root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=False)
    raw_log = logs / f"{safe_label(gate.label)}.{utc_now()}.log"

    rootfs = Path(gate.rootfs).resolve()
    lock = Path(gate.lock).resolve()
    experiment = Path(gate.experiment).resolve()
    fixture = Path(gate.fixture).resolve()
    runtime = load_runtime_lock(rootfs, lock)
    plan = build_plan(runtime, code=experiment, source=fixture, output=output.resolve(), command=gate.command)
    data = plan_data(plan)
    argv = render_plan(plan)

    started = time.monotonic()
    result = subprocess.run(argv, text=True, capture_output=True, timeout=timeout)
    raw_log.write_text(result.stdout + result.stderr)
    executed = parse_unittest_count(result.stdout + result.stderr)
    verdict = "pass" if result.returncode == 0 and executed == gate.expected_tests else "fail"
    receipt = {
        "schema_version": 1,
        "label": gate.label,
        "verdict": verdict,
        "rootfs": str(rootfs),
        "lock": str(lock),
        "rootfs_lock_sha256": file_sha256(lock),
        "fixture": str(fixture),
        "output": str(output.resolve()),
        "argv": argv,
        "mounts": [
            _mount_to_argv(mount)
            for mount in data["mounts"]
            if mount["kind"] in {"bind", "dev-bind", "tmpfs"}
        ],
        "environment": data["environment"],
        "command": data["command"],
        "exit_code": result.returncode,
        "expected_tests": gate.expected_tests,
        "executed_tests": executed,
        "duration_seconds": time.monotonic() - started,
        "raw_log": str(raw_log),
        "raw_log_sha256": _sha256(raw_log),
    }
    record = evidence_root / f"{safe_label(gate.label)}.json"
    record.write_text(json.dumps(receipt, indent=2) + "\n")
    if verdict != "pass":
        raise ValueError(f"live gate failed: {gate.label}; see {record}")
    return receipt


def _mount_to_argv(mount):
    if mount["kind"] == "tmpfs":
        return ["--tmpfs", mount["inside_path"]]
    flag = "--dev-bind" if mount["kind"] == "dev-bind" else "--bind" if mount["mode"] == "writable" else "--ro-bind"
    return [flag, mount["host_path"], mount["inside_path"]]
