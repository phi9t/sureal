"""Publish one closed scientific-processing directory, then optionally release it."""

import argparse
import json
import re
import shutil
import subprocess
import sys
from fnmatch import fnmatchcase
from pathlib import Path

from blob_store.core import BlobStore, blob_adapter_from_descriptor
from evidence.source_snapshot import (
    file_sha256,
    is_regular_file,
    require_regular_file,
    snapshot_target_and_materialize,
    verify_or_materialize_receipt_sources,
)
from insula.entry import launch_plan
from insula.runtime_identity import verify_rootfs
from resources.backend import resource_cpu_root_for
from resources.resource_archive import DEFAULT_LIMIT, create_archive, safe_name, verify_archive
from resources.resource_rehydrate import rehydrate_archive
from resources.scientific_budget import reserve_write
from retention.publication import (
    WAYSTONE_DESCRIPTOR,
    PublicationSpec,
    audit as audit_publication,
    publish as publish_publication,
    _write_json_idempotent,
)
from retention.publisher_runtime import admitted_host_sources


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CACHE_ROOT = Path.home() / ".cache/waystone/waymo-perception"
SCIENTIFIC_PROCESSING = CACHE_ROOT / "scientific-processing"
SNAPSHOT_TARGET = "//autonomy/retention:publish_scientific_directory"
REQUIRED_CHUNK_STAGES = [
    "create-live",
    "archive-put",
    "archive-get",
    "manifest-put",
    "manifest-get",
    "verify-live",
    "rehydrate-live",
]
REQUIRED_RELEASE_STAGES = REQUIRED_CHUNK_STAGES + [
    "independent",
    "release-plan",
    "release-completed",
]
PROTECTED_NAMES = frozenset(
    [
        "balanced16-native-v2",
        "balanced16-physical-v2",
        "balanced16-labels-v2",
        "cohort16-baseline-balanced20261002a",
        "balanced16-sustained-baseline-controller20261003a",
        "balanced16-camera-previews-v2",
        "balanced16-selection.candidate.json",
        "balanced16-sustained.candidate.json",
        "motion-current-geometry-audit-v3",
    ]
)
PROTECTED_PATTERNS = (
    "balanced16-sustained-*",
    "resource-retention-balanced16-sustained-baseline-controller20261003a-shared-*",
    "resource-retention-balanced16-sustained-*",
)
HOST_SOURCE_REQUIRED = (
    "retention/publish_scientific_directory.py",
    "retention/publisher_runtime.py",
    "resources/backend.py",
    "resources/resource_archive.py",
    "resources/resource_archive_cli.py",
    "resources/resource_rehydrate.py",
    "resources/resource_release_plan.py",
    "resources/scientific_budget.py",
    "retention/publication.py",
    "evidence/source_snapshot.py",
    "blob_store/core.py",
    "insula/entry.py",
    "insula/runtime_identity.py",
)
SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def _safe_component(value, what):
    if not isinstance(value, str) or not SAFE_COMPONENT.fullmatch(value):
        raise ValueError(f"safe {what} required")
    return value


def _is_relative_to(path, parent):
    try:
        Path(path).relative_to(parent)
    except ValueError:
        return False
    return True


def _require_case_root(case, root, scientific_processing):
    case = _safe_component(case, "case")
    if case in PROTECTED_NAMES or any(fnmatchcase(case, pattern) for pattern in PROTECTED_PATTERNS):
        raise ValueError("protected scientific-processing entry: " + case)
    root = Path(root)
    scientific_processing = Path(scientific_processing)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("regular source directory required")
    if root.name != case or root.parent.resolve() != scientific_processing.resolve():
        raise ValueError("--root must be the named direct child of scientific-processing")
    return root, scientific_processing


def _require_evidence_root(evidence, scientific_processing):
    evidence = Path(evidence)
    scientific_processing = Path(scientific_processing).resolve()
    resolved = evidence.resolve(strict=False)
    if resolved == scientific_processing or _is_relative_to(resolved, scientific_processing):
        raise ValueError("--evidence must be outside scientific-processing")
    evidence.mkdir(parents=True, exist_ok=True)
    if evidence.is_symlink() or not evidence.is_dir():
        raise ValueError("regular evidence directory required")
    return evidence


def _source_inventory(root):
    records = []
    for path in sorted(Path(root).rglob("*")):
        relative = path.relative_to(root).as_posix()
        safe_name(relative)
        if path.is_symlink():
            raise ValueError("regular source files without symlinks required")
        if path.is_dir():
            continue
        if not is_regular_file(path):
            raise ValueError("regular source files required")
        file = require_regular_file(path)
        records.append(
            {
                "path": relative,
                "bytes": file.stat().st_size,
                "sha256": file_sha256(file),
            }
        )
    if not records:
        raise ValueError("closed scientific directory must contain files")
    return records


def _publication_inventory(root):
    root = Path(root)
    return {
        record["path"]: {
            "path": str(root / record["path"]),
            "sha256": record["sha256"],
            "bytes": record["bytes"],
        }
        for record in _source_inventory(root)
    }


def _chunks(records, max_bytes):
    chunks = []
    current = []
    size = 0
    for record in records:
        if record["bytes"] > max_bytes:
            raise ValueError("single source file exceeds archive bound")
        if current and size + record["bytes"] > max_bytes:
            chunks.append(current)
            current = []
            size = 0
        current.append(record)
        size += record["bytes"]
    if current:
        chunks.append(current)
    return chunks


def _freeze_host_sources(repository, destination):
    repository = Path(repository)
    if not all(is_regular_file(repository / name) for name in HOST_SOURCE_REQUIRED):
        raise ValueError("complete regular host source closure required")
    return snapshot_target_and_materialize(SNAPSHOT_TARGET, destination, repo_root=repository.parent)


def _validate_host_sources(repository, pins):
    required = (
        {"autonomy/" + name for name in HOST_SOURCE_REQUIRED}
        if pins.get("schema_version") == 2
        else set(HOST_SOURCE_REQUIRED)
    )
    if not required <= set(pins.get("source_pins", {})):
        raise ValueError("complete host execution source bindings required")
    return verify_or_materialize_receipt_sources(
        pins,
        pins["source_snapshot_root"],
        env_var="SUREAL_SOURCE_SNAPSHOT_STORE",
    )


def _admit_host_sources(receipt_path, current_package, destination):
    return admitted_host_sources(
        receipt_path,
        current_package,
        destination,
        _freeze_host_sources,
        _validate_host_sources,
    )


class DirectArchiveRunner:
    def run(self, mode, input_dir, source_root, output_dir, evidence_dir, *, max_bytes):
        input_dir = Path(input_dir)
        source_root = Path(source_root)
        output_dir = Path(output_dir)
        evidence_dir = Path(evidence_dir)
        output_dir.mkdir(exist_ok=False)
        job = json.loads((input_dir / "job.json").read_text())
        if mode == "create":
            for name, digest in job["source_sha256"].items():
                if file_sha256(source_root / name) != digest:
                    raise ValueError("source payload differs")
            manifest = create_archive(source_root, job["source_sha256"], output_dir / "archive.tar.gz", max_bytes=max_bytes)
            (output_dir / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2))
            check = verify_archive(output_dir / "archive.tar.gz", manifest, max_bytes=max_bytes)
        elif mode in {"verify", "rehydrate"}:
            if file_sha256(source_root / "manifest.json") != job["manifest_sha256"]:
                raise ValueError("manifest readback differs")
            manifest = json.loads((source_root / "manifest.json").read_text())
            check = verify_archive(source_root / "archive.tar.gz", manifest, max_bytes=max_bytes)
            if mode == "rehydrate":
                check = rehydrate_archive(
                    source_root / "archive.tar.gz",
                    manifest,
                    output_dir / "restored",
                    max_bytes=max_bytes,
                )
        else:
            raise ValueError("unknown archive operation")
        (output_dir / "check.json").write_text(json.dumps(check, indent=2))
        (output_dir / "live.log").write_text("PASS archive " + mode + "\n")
        evidence_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(output_dir / "check.json", evidence_dir / "check.json")
        shutil.copyfile(output_dir / "live.log", evidence_dir / "live.log")
        return {
            "stage": {"create": "create-live", "verify": "verify-live", "rehydrate": "rehydrate-live"}[mode],
            "command": ["python", "/experiment/resources/resource_archive_cli.py", mode],
            "exit_code": 0,
            "validation": check,
            "artifacts": {str(path): file_sha256(path) for path in sorted(evidence_dir.iterdir())},
        }


class InsulaArchiveRunner:
    def __init__(self, rootfs, source_tree, source_pins, validate_sources):
        self.rootfs = Path(rootfs)
        self.source_tree = Path(source_tree)
        self.source_pins = dict(source_pins)
        self.validate_sources = validate_sources

    def run(self, mode, input_dir, source_root, output_dir, evidence_dir, *, max_bytes):
        del max_bytes
        self.validate_sources()
        input_dir = Path(input_dir)
        source_root = Path(source_root)
        output_dir = Path(output_dir)
        evidence_dir = Path(evidence_dir)
        output_dir.mkdir(exist_ok=False)
        command = launch_plan(
            self.rootfs,
            self.source_tree,
            source_root,
            output_dir,
            ["python", "/experiment/resources/resource_archive_cli.py", mode],
        )
        separator = command.index("--")
        command[separator:separator] = ["--ro-bind", str(input_dir), "/tmp/inputs"]
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
        (output_dir / "live.log").write_text(result.stdout + result.stderr)
        if result.returncode != 0:
            raise RuntimeError("live archive operation failed: " + str(output_dir / "live.log"))
        for path, digest in self.source_pins.items():
            if file_sha256(path) != digest:
                raise ValueError("staged source changed")
        evidence_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(output_dir / "check.json", evidence_dir / "check.json")
        shutil.copyfile(output_dir / "live.log", evidence_dir / "live.log")
        return {
            "stage": {"create": "create-live", "verify": "verify-live", "rehydrate": "rehydrate-live"}[mode],
            "command": command,
            "exit_code": 0,
            "validation": json.loads((output_dir / "check.json").read_text()),
            "artifacts": {str(path): file_sha256(path) for path in sorted(evidence_dir.iterdir())},
        }


class InsulaIndependentRunner:
    def __init__(self, rootfs, source_tree, source_pins, validate_sources):
        self.rootfs = Path(rootfs)
        self.source_tree = Path(source_tree)
        self.source_pins = dict(source_pins)
        self.validate_sources = validate_sources

    def run(self, source_root, chunks, output_dir, *, max_bytes):
        self.validate_sources()
        output_dir = Path(output_dir)
        input_dir = output_dir.parent / "independent-input"
        input_dir.mkdir(exist_ok=False)
        chunk_root = input_dir / "chunks"
        chunk_root.mkdir()
        for index, chunk in enumerate(chunks):
            target = chunk_root / str(index)
            target.mkdir()
            shutil.copyfile(chunk["downloaded_archive"], target / "archive.tar.gz")
            (target / "manifest.json").write_text(json.dumps(chunk["manifest"], sort_keys=True, indent=2))
        (input_dir / "job.json").write_text(
            json.dumps({"chunks": len(chunks), "max_bytes": max_bytes}, sort_keys=True)
        )
        output_dir.mkdir(exist_ok=False)
        command = launch_plan(
            self.rootfs,
            self.source_tree,
            source_root,
            output_dir,
            ["python", "/experiment/retention/publish_scientific_directory.py", "--independent-audit"],
        )
        separator = command.index("--")
        command[separator:separator] = [
            "--ro-bind",
            str(input_dir),
            "/tmp/inputs",
            "--setenv",
            "PYTHONPATH",
            "/experiment",
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
        (output_dir / "live.log").write_text(result.stdout + result.stderr)
        if result.returncode != 0:
            raise RuntimeError("independent scientific directory audit failed: " + str(output_dir / "live.log"))
        for path, digest in self.source_pins.items():
            if file_sha256(path) != digest:
                raise ValueError("staged source changed")
        return {
            "stage": "independent",
            "command": command,
            "exit_code": 0,
            "validation": json.loads((output_dir / "check.json").read_text()),
            "artifacts": {str(path): file_sha256(path) for path in sorted(output_dir.iterdir()) if path.is_file()},
            "inputs": {str(path): file_sha256(path) for path in sorted(input_dir.rglob("*")) if path.is_file()},
        }

    def __call__(self, source_root, chunks, output_dir, *, max_bytes):
        return self.run(source_root, chunks, output_dir, max_bytes=max_bytes)


def _default_live_runners(run_dir, cache_root, host_pins, admitted_package):
    source = run_dir / "source"
    source.mkdir()
    for folder in ("resources", "evidence", "insula", "retention"):
        shutil.copytree(admitted_package / folder, source / folder, ignore=shutil.ignore_patterns("__pycache__"))
    source_pins = {str(path): file_sha256(path) for path in sorted(source.rglob("*")) if path.is_file()}
    rootfs = resource_cpu_root_for(None, cache_root)
    runtime = json.loads(Path(str(rootfs) + ".lock.json").read_text())
    verify_rootfs(rootfs, runtime["rootfs_sha256"])

    def validate_sources():
        _validate_host_sources(admitted_package, host_pins)

    return (
        InsulaArchiveRunner(rootfs, source, source_pins, validate_sources),
        InsulaIndependentRunner(rootfs, source, source_pins, validate_sources),
        runtime,
        source_pins,
    )


def _independent_restore(source_root, chunks, output_dir, *, max_bytes):
    output_dir = Path(output_dir)
    restored = output_dir / "restored"
    restored.mkdir(parents=True, exist_ok=False)
    for index, chunk in enumerate(chunks):
        destination = restored / str(index)
        rehydrate_archive(
            chunk["downloaded_archive"],
            chunk["manifest"],
            destination,
            max_bytes=max_bytes,
        )
    source = {record["path"]: record for record in _source_inventory(source_root)}
    recovered = {}
    for path in sorted(restored.rglob("*")):
        if path.is_dir():
            continue
        if path.is_symlink() or not is_regular_file(path):
            raise ValueError("independent restore contains nonregular file")
        relative = path.relative_to(restored).as_posix()
        _, member = relative.split("/", 1)
        recovered[member] = {
            "path": member,
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        }
    if recovered != source:
        raise ValueError("independent restored inventory differs")
    check = {
        "exact_restored_inventory": True,
        "members": len(recovered),
        "payload_bytes": sum(record["bytes"] for record in recovered.values()),
    }
    (output_dir / "check.json").write_text(json.dumps(check, indent=2))
    (output_dir / "live.log").write_text("PASS independent scientific directory retention\n")
    return {
        "stage": "independent",
        "command": ["python", "-m", "retention.publish_scientific_directory", "independent"],
        "exit_code": 0,
        "validation": check,
        "artifacts": {str(path): file_sha256(path) for path in sorted(output_dir.iterdir()) if path.is_file()},
    }


def _independent_audit_cli():
    input_dir = Path("/tmp/inputs")
    job = json.loads((input_dir / "job.json").read_text())
    chunks = []
    for index in range(job["chunks"]):
        chunk_dir = input_dir / "chunks" / str(index)
        chunks.append(
            {
                "downloaded_archive": chunk_dir / "archive.tar.gz",
                "manifest": json.loads((chunk_dir / "manifest.json").read_text()),
            }
        )
    _independent_restore("/source", chunks, "/outputs", max_bytes=job["max_bytes"])
    print("PASS independent scientific directory retention", flush=True)


def _safe_release(root, plan):
    root = Path(root).resolve()
    verified = []
    for entry in plan:
        path = Path(entry["local_path"])
        resolved = path.resolve()
        if root not in resolved.parents:
            raise ValueError("release plan path escapes --root")
        file = require_regular_file(path)
        if file.stat().st_size != entry["bytes"] or file_sha256(file) != entry["sha256"]:
            raise ValueError("release plan source changed")
        verified.append((file, entry))
    for file, _ in verified:
        file.unlink()
    return [entry for _, entry in verified]


def _release_plan_from_audit(root, audit_result):
    root = Path(root)
    if not isinstance(audit_result, dict) or audit_result.get("whole_member_union_exact") is not True:
        raise ValueError("passing publication audit required before release")
    plan = []
    for name, entry in sorted(audit_result["inventory"].items()):
        path = root / safe_name(name)
        file = require_regular_file(path)
        if file.stat().st_size != entry["bytes"] or file_sha256(file) != entry["sha256"]:
            raise ValueError("source payload differs")
        plan.append({"path": name, "bytes": entry["bytes"], "sha256": entry["sha256"], "local_path": str(path)})
    return plan


def publish(
    *,
    case,
    root,
    hdfs_namespace,
    evidence,
    host_source_receipt=None,
    auth_source="token-file",
    release=False,
    scientific_processing=SCIENTIFIC_PROCESSING,
    store=None,
    store_descriptor=None,
    tool_digest=None,
    reserve=None,
    host_source_admitter=_admit_host_sources,
    release_planner=_release_plan_from_audit,
    identifier=None,
    max_bytes=DEFAULT_LIMIT,
):
    if auth_source != "token-file":
        raise ValueError("--auth-source token-file is required")
    hdfs_namespace = _safe_component(hdfs_namespace, "HDFS namespace")
    root, scientific_processing = _require_case_root(case, root, scientific_processing)
    evidence = _require_evidence_root(evidence, scientific_processing)
    identifier = identifier or case
    run_dir = evidence / ("blob-publication-" + identifier)
    run_dir.mkdir(exist_ok=False)
    host_pins, admitted_package = host_source_admitter(host_source_receipt, PACKAGE_ROOT, run_dir / "host-source")
    del host_pins, admitted_package
    descriptor = dict(store_descriptor or WAYSTONE_DESCRIPTOR)
    if store is None:
        store = BlobStore(blob_adapter_from_descriptor(descriptor))
    if tool_digest is None:
        adapter_digest = getattr(getattr(store, "_adapter", None), "tool_sha256", None)
        tool_digest = adapter_digest if adapter_digest is not None else {"blob-store-adapter": "0" * 64}
    if reserve is None:
        reserve = reserve_write
    spec = PublicationSpec(
        payload=_publication_inventory(root),
        inventory=lambda payload: payload,
        area="runs",
        child=hdfs_namespace,
        run_id=identifier,
        kind="scientific-directory",
        staging_style="copy",
        mode="archive",
        release=release,
        store=store,
        store_descriptor=descriptor,
        tool_digest=tool_digest,
        staging_root=run_dir / "stage",
        reserve=reserve,
        chunk_size_bytes=max_bytes,
    )
    receipt = publish_publication(spec)
    audit_result = audit_publication(receipt, store=store)
    receipt_path = run_dir / "verified-publication.json"
    _write_json_idempotent(receipt_path, receipt)
    if release:
        plan = release_planner(root, audit_result)
        released = _safe_release(root, plan)
        completed = {
            "publication_receipt_sha256": file_sha256(receipt_path),
            "released_count": len(released),
            "released": released,
        }
        completed_path = run_dir / "release-completed.json"
        completed_path.write_text(json.dumps(completed, indent=2))
    print("ADMITTED blob-store scientific directory publication", receipt_path, "local release", release, flush=True)
    return receipt


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv == ["--independent-audit"]:
        _independent_audit_cli()
        return
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--hdfs-namespace", required=True)
    parser.add_argument("--auth-source", default="token-file", choices=["token-file"])
    parser.add_argument("--host-source-receipt", type=Path)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--release", action="store_true")
    args = parser.parse_args(argv)
    publish(
        case=args.case,
        root=args.root,
        hdfs_namespace=args.hdfs_namespace,
        evidence=args.evidence,
        auth_source=args.auth_source,
        host_source_receipt=args.host_source_receipt,
        release=args.release,
    )


if __name__ == "__main__":
    main()
