"""Publish one closed scientific-processing directory, then optionally release it."""

import argparse
import json
import re
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
from resources.resource_archive import DEFAULT_LIMIT, safe_name
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
    "resources/resource_archive.py",
    "resources/scientific_budget.py",
    "retention/publication.py",
    "evidence/source_snapshot.py",
    "blob_store/core.py",
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


def _require_tool_digest(store, tool_digest):
    if tool_digest is not None:
        return tool_digest
    adapter_digest = getattr(getattr(store, "_adapter", None), "tool_sha256", None)
    if adapter_digest is None:
        raise ValueError("tool digest required when blob store adapter does not expose tool_sha256")
    return adapter_digest


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
    tool_digest = _require_tool_digest(store, tool_digest)
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
        release=False,  # Blob-store 05 moves this caller-side release into publication.publish().
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
