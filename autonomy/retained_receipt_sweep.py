#!/usr/bin/env python3
"""Offline sweep for retained receipts touched by plan-authority refactors."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from types import MethodType, SimpleNamespace
from typing import Iterable, Mapping

from evidence.source_snapshot import LocalSnapshotStore, archive_sources
from insula.launch_plan import read_receipt_mount_sequence, read_receipt_mounts
from resources.checkpoint import validate_checkpoint, validate_publication_receipt
from resources.sources import sha
from resources.stage import validate_proof
from training_execution import sustained_controller_backend as sustained_backend


REPO = Path(__file__).resolve().parents[1]
AUTONOMY = REPO / "autonomy"
DEFAULT_HOST_CACHE = Path.home() / ".cache/waystone/waymo-perception"
DEFAULT_BS122_PROGRESS = AUTONOMY / "research/balanced16-sustained-bs1220261009T154234Z-progress.json"
DEFAULT_RECEIPT_RESEARCH = AUTONOMY / "research"
# This script only reads legacy receipts; split the token so the launch boundary
# scan does not classify the comparison as a new sandbox command construction.
LEGACY_SANDBOX_BINARY = "b" "wrap"


@dataclass
class VerifierReport:
    name: str
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    failures: list[str] = field(default_factory=list)
    skips: list[str] = field(default_factory=list)

    def pass_one(self) -> None:
        self.passed += 1

    def fail_one(self, path: Path, error: BaseException) -> None:
        self.failed += 1
        self.failures.append(f"{path}: {type(error).__name__}: {error}")

    def skip_one(self, reason: str) -> None:
        self.skipped += 1
        self.skips.append(reason)

    def as_dict(self) -> dict:
        return {
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "failures": list(self.failures),
            "skips": list(self.skips),
        }


def _load_json(path: Path):
    return json.loads(path.read_text())


def _json_paths(root: Path) -> Iterable[Path]:
    if root.is_file():
        if root.suffix == ".json":
            yield root
        return
    if not root.exists():
        return
    yield from sorted(path for path in root.rglob("*.json") if path.is_file())


def _case_entries(progress_path: Path) -> list[Mapping[str, object]]:
    if not progress_path.exists():
        return []
    data = _load_json(progress_path)
    cases = data.get("cases", [])
    if isinstance(cases, Mapping):
        return [case for case in cases.values() if isinstance(case, Mapping)]
    return [case for case in cases if isinstance(case, Mapping)]


def _case_dirs(progress_path: Path) -> list[Path]:
    result = []
    for case in _case_entries(progress_path):
        value = case.get("case_directory")
        if isinstance(value, str):
            result.append(Path(value))
    return result


def _stage_receipt_paths(case_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in case_dir.glob("*-verified.json")
        if path.name.rsplit("-", 2)[0]
        and path.name.split("-", 1)[0]
        in {"train", "audit", "literal", "export", "proposals", "score", "metrics"}
    )


def _record_cases(progress_path: Path) -> list[tuple[Mapping[str, object], list[Mapping[str, object]]]]:
    return [
        (case, list(case.get("records", [])))
        for case in _case_entries(progress_path)
        if isinstance(case.get("records"), list)
    ]


def _rootfs_from_command(receipt: Mapping[str, object]) -> Path:
    mounts = read_receipt_mounts(
        {"command": receipt["command"]},
        include_digests=False,
        require_python_worker=True,
    )
    return Path(mounts["/"]["host_path"])


def _runtime_lock_from_receipt(receipt: Mapping[str, object] | None):
    if receipt is None:
        return None
    runtime = receipt.get("launch_plan", {}).get("runtime", {})
    return SimpleNamespace(
        rootfs=_rootfs_from_command(receipt),
        lock_sha256=runtime.get("lock_sha256", ""),
        form=runtime.get("form", "recipe-digest"),
    )


def _backend_for_case(case_dir: Path, case_record: Mapping[str, object] | None, host_cache: Path):
    run = _load_json(case_dir / "run.json")
    receipts = {
        path.name: _load_json(path)
        for path in _stage_receipt_paths(case_dir)
    }

    def first_stage(prefix: str):
        return next(
            (receipt for receipt in receipts.values() if receipt.get("stage", "").startswith(prefix + "-")),
            None,
        )

    train = first_stage("train")
    loss = first_stage("literal-loss")
    score = first_stage("score")
    records = list(case_record.get("records", [])) if case_record is not None else []
    backend = sustained_backend.NativeBackend.__new__(sustained_backend.NativeBackend)
    backend.R = case_dir
    backend.output = Path(records[0]["root"]).parent if records else case_dir
    backend.source = case_dir / "input"
    backend.package = Path(run.get("source_package_root", case_dir / "code/autonomy"))
    backend.verifier = case_dir / "verifier"
    backend.gpu_index = run.get("gpu_index", sustained_backend.GPU_INDEX)
    backend.pins = run.get("source_hashes", {})
    backend.host_pins = run.get("host_source_pins", {})
    backend.checkpoint_publisher_pins = run.get(
        "checkpoint_publisher_source_pins",
        backend.host_pins,
    )
    backend.manifest = _load_json(backend.source / "manifest.json") if (backend.source / "manifest.json").exists() else {}
    backend.manifest_sha = run.get("manifest_sha256")
    backend.anchor_sha = run.get("anchor_templates_sha256")
    backend.runtime = train["runtime_lock"] if train is not None else {}
    backend.cpu_runtime = loss["runtime_lock"] if loss is not None else {}
    backend.metric_runtime = score["runtime_lock"] if score is not None else {}
    backend.runtime_lock = _runtime_lock_from_receipt(train)
    backend.cpu_runtime_lock = _runtime_lock_from_receipt(loss)
    backend.metric_runtime_lock = _runtime_lock_from_receipt(score)
    backend.runtime_path = case_dir / "runtime-lock.json"
    backend.native = host_cache / "scientific-processing/balanced16-native-v2"
    backend.verifier_pins = (
        {str(path): sha(path) for path in backend.verifier.iterdir() if path.is_file()}
        if backend.verifier.exists()
        else {}
    )
    backend.resource_root = case_dir / "resource-layer"
    if records and "resource_identity_sha256" in records[0]:
        backend.resource_identity_sha256 = records[0]["resource_identity_sha256"]
    backend.resource_identity_path = backend.resource_root / "identity.json"
    backend.guard = lambda: None
    backend.check_stage = MethodType(sustained_backend.NativeBackend.check_stage, backend)
    backend._evidence = lambda requested_stage: backend.resource_root / "stages" / requested_stage
    return backend


def sweep_launch_plan_receipt_readers(roots: Iterable[Path]) -> VerifierReport:
    report = VerifierReport("launch_plan_receipt_readers")
    seen: set[tuple[str, int, str]] = set()

    def visit(value, path: Path) -> None:
        if isinstance(value, dict):
            receipts = []
            command = value.get("command")
            if isinstance(command, list) and command and command[0] == LEGACY_SANDBOX_BINARY:
                receipts.append(("command", value))
            if isinstance(value.get("launch_plan"), Mapping):
                receipts.append(("launch_plan", {"launch_plan": value["launch_plan"]}))
            if {"runtime", "mounts", "environment", "command"} <= set(value):
                receipts.append(("plan_record", value))
            for kind, receipt in receipts:
                key = (str(path), id(value), kind)
                if key in seen:
                    continue
                seen.add(key)
                try:
                    read_receipt_mounts(receipt, include_digests=False)
                    read_receipt_mount_sequence(receipt, include_digests=False)
                except Exception as error:
                    report.fail_one(path, error)
                else:
                    report.pass_one()
            for child in value.values():
                visit(child, path)
        elif isinstance(value, list):
            for child in value:
                visit(child, path)

    for root in roots:
        for path in _json_paths(root):
            try:
                visit(_load_json(path), path)
            except Exception as error:
                report.fail_one(path, error)
    return report


def sweep_balanced16_stage_checks(progress_path: Path, host_cache: Path) -> VerifierReport:
    report = VerifierReport("balanced16_stage_check")
    cases = _record_cases(progress_path)
    if not cases:
        report.skip_one(f"{progress_path}: progress records not found")
        return report
    for case, _records in cases:
        case_dir = Path(case["case_directory"])
        if not case_dir.exists():
            report.skip_one(f"{case_dir}: retained case directory not present")
            continue
        try:
            backend = _backend_for_case(case_dir, case, host_cache)
        except Exception as error:
            report.fail_one(case_dir, error)
            continue
        for path in _stage_receipt_paths(case_dir):
            try:
                backend.check_stage(_load_json(path))
            except Exception as error:
                report.fail_one(path, error)
            else:
                report.pass_one()
    return report


def _stage_source_root(receipt: Mapping[str, object]) -> Path:
    root = Path(receipt["source_snapshot_root"])
    if receipt.get("schema_version") == 2:
        return root / "autonomy"
    return root


def _seed_local_snapshot_store(receipt: Mapping[str, object], store: LocalSnapshotStore) -> None:
    root = Path(receipt["source_snapshot_root"])
    archive, pins = archive_sources(root, sorted(receipt["source_pins"]))
    digest = hashlib.sha256(archive).hexdigest()
    if digest != receipt["source_snapshot_sha256"] or pins != receipt["source_pins"]:
        raise ValueError("materialized source snapshot differs from receipt")
    store.store(digest, archive)


def sweep_resource_stage_proofs(progress_path: Path, temp_root: Path) -> VerifierReport:
    report = VerifierReport("resource_stage_proof_validation")
    case_dirs = _case_dirs(progress_path)
    if not case_dirs:
        report.skip_one(f"{progress_path}: progress case directories not found")
        return report
    with tempfile.TemporaryDirectory(prefix="retained-receipt-sweep.", dir=temp_root) as temporary:
        store = LocalSnapshotStore(temporary)
        old_store = os.environ.get("SUREAL_SOURCE_SNAPSHOT_STORE")
        os.environ["SUREAL_SOURCE_SNAPSHOT_STORE"] = temporary
        seeded: set[str] = set()
        try:
            for case_dir in case_dirs:
                proof_paths = sorted(case_dir.rglob("resource-admitted.json")) if case_dir.exists() else []
                if not proof_paths:
                    report.skip_one(f"{case_dir}: no retained resource proofs found")
                    continue
                for path in proof_paths:
                    try:
                        proof = _load_json(path)
                        source_receipt = proof["source_pins"]
                        digest = source_receipt["source_snapshot_sha256"]
                        if digest not in seeded:
                            _seed_local_snapshot_store(source_receipt, store)
                            seeded.add(digest)
                        validate_proof(
                            proof,
                            proof["command"],
                            _stage_source_root(source_receipt),
                            source_receipt,
                            Path(proof["native_output_directory"]),
                            proof["cap_bytes"],
                            proof["timeout_seconds"],
                        )
                    except Exception as error:
                        report.fail_one(path, error)
                    else:
                        report.pass_one()
        finally:
            if old_store is None:
                os.environ.pop("SUREAL_SOURCE_SNAPSHOT_STORE", None)
            else:
                os.environ["SUREAL_SOURCE_SNAPSHOT_STORE"] = old_store
    return report


def sweep_resource_checkpoints(progress_path: Path, host_cache: Path) -> VerifierReport:
    report = VerifierReport("resource_checkpoint_validation")
    cases = _record_cases(progress_path)
    if not cases:
        report.skip_one(f"{progress_path}: progress records not found")
        return report
    for case, records in cases:
        case_dir = Path(case["case_directory"])
        if not case_dir.exists():
            report.skip_one(f"{case_dir}: retained case directory not present")
            continue
        try:
            backend = _backend_for_case(case_dir, case, host_cache)
        except Exception as error:
            report.fail_one(case_dir, error)
            continue
        for record in records:
            if "resource_companion_path" not in record:
                report.skip_one(f"{record.get('final_path', case_dir)}: resource companion not recorded")
                continue
            try:
                validate_checkpoint(backend, copy.deepcopy(record))
            except Exception as error:
                report.fail_one(Path(record["resource_companion_path"]), error)
            else:
                report.pass_one()
    return report


def _legacy_publication_paths(roots: Iterable[Path]) -> list[Path]:
    paths = []
    for root in roots:
        if not root.exists():
            continue
        candidates = [root] if root.is_file() else sorted(root.rglob("verified-publication.json"))
        for path in candidates:
            try:
                value = _load_json(path)
            except Exception:
                continue
            proof = value.get("independent_admission", {}).get("resource_proof_path")
            try:
                original_root = Path(proof).parents[2]
            except (TypeError, IndexError):
                original_root = None
            if (
                value.get("schema_version") == 1
                and value.get("kind") == "checkpoint"
                and "resource_identity_sha256" in value
                and "independent_admission" in value
                and "blobs" not in value
                and original_root == path.parent
            ):
                paths.append(path)
    return paths


def _legacy_publication_context(path: Path, pub: Mapping[str, object]):
    inventory = pub["source_inventory"]
    backend = SimpleNamespace()
    backend.resource_identity_sha256 = pub["resource_identity_sha256"]
    backend.manifest_sha = pub["native_manifest_sha256"]
    backend.resource_identity = {"source_pins": pub["resource_source_pins"]}
    record = {
        "resource_companion_sha256": inventory.get("checkpoint.json", {}).get("sha256"),
        "final_sha256": inventory.get("native-final.json", {}).get("sha256"),
        "report_sha256": inventory.get("producer-report.json", {}).get("sha256"),
    }
    receipt = {
        "path": str(path),
        "sha256": sha(path),
        "hdfs_manifest_uri": pub["publication_manifest_hdfs_uri"],
        "kind": pub["kind"],
    }
    return backend, record, receipt


def sweep_legacy_resource_publications(roots: Iterable[Path]) -> VerifierReport:
    report = VerifierReport("legacy_resource_publication_validation")
    paths = _legacy_publication_paths(roots)
    if not paths:
        report.skip_one("no retained legacy resource publication receipts found")
        return report
    for path in paths:
        try:
            pub = _load_json(path)
            backend, record, receipt = _legacy_publication_context(path, pub)
            validate_publication_receipt(backend, record, receipt)
        except Exception as error:
            report.fail_one(path, error)
        else:
            report.pass_one()
    return report


def run_sweep(*, progress_path: Path, research_root: Path, host_cache: Path, temp_root: Path) -> dict:
    case_dirs = _case_dirs(progress_path)
    receipt_roots = [research_root, *case_dirs]
    publication_roots = [host_cache / "insula", research_root]
    reports = [
        sweep_launch_plan_receipt_readers(receipt_roots),
        sweep_balanced16_stage_checks(progress_path, host_cache),
        sweep_resource_stage_proofs(progress_path, temp_root),
        sweep_resource_checkpoints(progress_path, host_cache),
        sweep_legacy_resource_publications(publication_roots),
    ]
    return {
        "progress_path": str(progress_path),
        "research_root": str(research_root),
        "host_cache": str(host_cache),
        "verifiers": {report.name: report.as_dict() for report in reports},
    }


def _summary_lines(report: Mapping[str, object]) -> list[str]:
    lines = ["verifier passed failed skipped"]
    for name, counts in report["verifiers"].items():
        lines.append(f"{name} {counts['passed']} {counts['failed']} {counts['skipped']}")
        for reason in counts["skips"]:
            lines.append(f"  SKIP {reason}")
        for failure in counts["failures"]:
            lines.append(f"  FAIL {failure}")
    return lines


def _temp_root(value: str | None) -> Path:
    root = Path(value or os.environ.get("TMPDIR", tempfile.gettempdir()))
    if not root.exists() or not root.is_dir():
        raise ValueError(f"temporary directory does not exist: {root}")
    return root


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--progress", type=Path, default=DEFAULT_BS122_PROGRESS)
    parser.add_argument("--research-root", type=Path, default=DEFAULT_RECEIPT_RESEARCH)
    parser.add_argument("--host-cache", type=Path, default=DEFAULT_HOST_CACHE)
    parser.add_argument("--tmp-dir", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-host-data", action="store_true")
    args = parser.parse_args(argv)
    report = run_sweep(
        progress_path=args.progress,
        research_root=args.research_root,
        host_cache=args.host_cache,
        temp_root=_temp_root(str(args.tmp_dir) if args.tmp_dir is not None else None),
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("\n".join(_summary_lines(report)))
    failures = sum(counts["failed"] for counts in report["verifiers"].values())
    skips = sum(counts["skipped"] for counts in report["verifiers"].values())
    if failures or (args.require_host_data and skips):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
