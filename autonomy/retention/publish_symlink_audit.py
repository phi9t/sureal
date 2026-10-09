"""Publish and optionally retire a symlink-preserving scientific audit tree."""

import argparse
import gzip
import json
import os
import shutil
import tarfile
import tempfile
from pathlib import Path

from blob_store.core import BlobStore, blob_adapter_from_descriptor, validate_blob_key
from evidence.source_snapshot import (
    file_sha256,
    is_regular_file,
    require_regular_file,
    snapshot_target_and_materialize,
    verify_or_materialize_receipt_sources,
)
from resources.resource_archive import safe_name
from retention.publish_scientific_directory import (
    CACHE_ROOT,
    PACKAGE_ROOT,
    SCIENTIFIC_PROCESSING,
    _require_evidence_root,
    _safe_component,
)
from retention.publication import (
    WAYSTONE_DESCRIPTOR,
    _normalize_receipt_tool_digest,
    _normalize_tool_digest,
    _write_json_idempotent,
)
from retention.publisher_runtime import admitted_host_sources


SNAPSHOT_TARGET = "//autonomy/retention:publish_symlink_audit"
HOST_SOURCE_REQUIRED = (
    "retention/publish_symlink_audit.py",
    "retention/publish_scientific_directory.py",
    "retention/publisher_runtime.py",
    "resources/resource_archive.py",
    "evidence/source_snapshot.py",
    "blob_store/core.py",
    "retention/publication.py",
)


def _require_case_root(case, root, scientific_processing):
    case = _safe_component(case, "case")
    root = Path(root)
    scientific_processing = Path(scientific_processing)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("regular audit source directory required")
    if root.name != case or root.parent.resolve() != scientific_processing.resolve():
        raise ValueError("--root must be the named direct child of scientific-processing")
    return root, scientific_processing


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


def tree_listing(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("regular audit directory required")
    records = []

    def visit(directory):
        for child in sorted(directory.iterdir(), key=lambda item: item.name):
            relative = child.relative_to(root).as_posix()
            safe_name(relative)
            if child.is_symlink():
                records.append({"path": relative, "kind": "symlink", "link_text": os.readlink(child)})
            elif child.is_dir():
                records.append({"path": relative, "kind": "directory"})
                visit(child)
            elif is_regular_file(child):
                file = require_regular_file(child)
                records.append(
                    {
                        "path": relative,
                        "kind": "file",
                        "bytes": file.stat().st_size,
                        "sha256": file_sha256(file),
                    }
                )
            else:
                raise ValueError("unsupported audit entry: " + str(child))

    visit(root)
    if not records:
        raise ValueError("audit directory must contain entries")
    return records


def create_symlink_archive(root, archive):
    root = Path(root)
    archive = Path(archive)
    listing = tree_listing(root)
    with archive.open("xb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0, compresslevel=6) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as writer:
                for record in listing:
                    info = tarfile.TarInfo(record["path"])
                    info.mtime = 0
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    info.pax_headers = {}
                    if record["kind"] == "directory":
                        info.type = tarfile.DIRTYPE
                        info.mode = 0o555
                        writer.addfile(info)
                    elif record["kind"] == "symlink":
                        info.type = tarfile.SYMTYPE
                        info.mode = 0o777
                        info.linkname = record["link_text"]
                        writer.addfile(info)
                    elif record["kind"] == "file":
                        info.size = record["bytes"]
                        info.mode = 0o444
                        with require_regular_file(root / record["path"]).open("rb") as stream:
                            writer.addfile(info, stream)
                    else:
                        raise ValueError("unknown audit listing kind")
    manifest = {
        "schema_version": 1,
        "listing": listing,
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": file_sha256(archive),
    }
    return manifest


def _ensure_extract_parent(destination, target):
    destination = Path(destination).resolve()
    parent = Path(target).parent
    parent.mkdir(parents=True, exist_ok=True)
    for candidate in [parent, *parent.parents]:
        if candidate == destination:
            return
        if candidate.is_symlink():
            raise ValueError("archive extraction parent is a symlink")
    raise ValueError("archive member escapes extraction root")


def extract_symlink_archive(archive, manifest, destination):
    archive = Path(archive)
    destination = Path(destination)
    if archive.stat().st_size != manifest["archive_bytes"] or file_sha256(archive) != manifest["archive_sha256"]:
        raise ValueError("archive bytes or hash differ")
    destination.mkdir(exist_ok=False)
    seen = set()
    try:
        with tarfile.open(archive, "r:*") as reader:
            for member in reader:
                name = safe_name(member.name)
                if name in seen:
                    raise ValueError("duplicate archive member")
                seen.add(name)
                target = destination / name
                _ensure_extract_parent(destination, target)
                if member.isdir():
                    target.mkdir(exist_ok=True)
                elif member.issym():
                    if target.exists() or target.is_symlink():
                        raise ValueError("archive extraction target exists")
                    target.symlink_to(member.linkname)
                elif member.isfile():
                    if target.exists() or target.is_symlink():
                        raise ValueError("archive extraction target exists")
                    stream = reader.extractfile(member)
                    if stream is None:
                        raise ValueError("archive regular member is unreadable")
                    with target.open("xb") as output:
                        shutil.copyfileobj(stream, output, length=1024 * 1024)
                    target.chmod(0o444)
                else:
                    raise ValueError("unsupported archive member")
    except (tarfile.TarError, OSError, EOFError) as error:
        raise ValueError("invalid symlink audit archive") from error
    listing = tree_listing(destination)
    if listing != manifest["listing"]:
        raise ValueError("extracted audit listing differs")
    return listing


def _same_device(source, destination):
    return Path(source).stat().st_dev == Path(destination).parent.stat().st_dev


def _move_tree(root, destination, expected_listing, same_device):
    root = Path(root)
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("audit move destination already exists: " + str(destination))
    if not destination.parent.is_dir() or destination.parent.is_symlink():
        raise ValueError("audit move parent directory required")
    if not same_device(root, destination):
        raise OSError("cross-device audit move refused")
    root.rename(destination)
    moved = tree_listing(destination)
    if moved != expected_listing:
        raise ValueError("moved audit listing differs")
    return moved


def _blob_key_prefix(child, run_id):
    return validate_blob_key("/".join(["runs", child, run_id, "symlink-audit"]))


def _blob_key(child, run_id, name):
    return _blob_key_prefix(child, run_id) + "/" + validate_blob_key(name)


def _fetch_blob(store, blob, destination):
    blob = _normalize_blob(blob)
    store.get(blob["key"], destination, blob["sha256"], expected_bytes=blob["bytes"])


def _fetch_json_blob(store, blob, destination):
    _fetch_blob(store, blob, destination)
    try:
        return json.loads(Path(destination).read_text())
    except json.JSONDecodeError as error:
        raise ValueError("symlink audit manifest JSON required") from error


def _normalize_blob(value):
    if not isinstance(value, dict) or set(value) != {"key", "sha256", "bytes"}:
        raise ValueError("symlink audit blob record required")
    digest = value["sha256"]
    if not isinstance(digest, str) or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError("symlink audit blob digest required")
    size = value["bytes"]
    if type(size) is not int or size < 0:
        raise ValueError("symlink audit blob byte count required")
    return {"key": validate_blob_key(value["key"]), "sha256": digest, "bytes": size}


def _normalize_receipt(receipt):
    if not isinstance(receipt, dict):
        raise ValueError("symlink audit receipt required")
    if set(receipt) != {"schema_version", "store_descriptor", "tool_sha256", "verified_by_readback", "blobs"}:
        raise ValueError("symlink audit receipt shape required")
    if receipt["schema_version"] != 1 or receipt["verified_by_readback"] is not True:
        raise ValueError("symlink audit readback receipt required")
    blobs = receipt["blobs"]
    if not isinstance(blobs, dict) or set(blobs) != {"archive", "manifest"}:
        raise ValueError("symlink audit blob records required")
    return {
        "schema_version": 1,
        "store_descriptor": dict(receipt["store_descriptor"]),
        "tool_sha256": _normalize_receipt_tool_digest(receipt["tool_sha256"]),
        "verified_by_readback": True,
        "blobs": {
            "archive": _normalize_blob(blobs["archive"]),
            "manifest": _normalize_blob(blobs["manifest"]),
        },
    }


def audit(receipt, *, store=None):
    receipt = _normalize_receipt(receipt)
    if store is None:
        store = BlobStore(blob_adapter_from_descriptor(receipt["store_descriptor"]))
    with tempfile.TemporaryDirectory(prefix="symlink-audit.") as directory:
        root = Path(directory)
        manifest_path = root / "manifest.json"
        manifest = _fetch_json_blob(store, receipt["blobs"]["manifest"], manifest_path)
        if manifest.get("schema_version") != 1 or manifest.get("kind") != "symlink-audit":
            raise ValueError("symlink audit manifest shape required")
        expected_prefix = _blob_key_prefix(manifest["child"], manifest["run_id"])
        if receipt["blobs"]["manifest"]["key"] != expected_prefix + "/manifest.json":
            raise ValueError("symlink audit manifest key differs")
        if receipt["blobs"]["archive"]["key"] != expected_prefix + "/audit.tar.gz":
            raise ValueError("symlink audit archive key differs")
        if manifest.get("archive") != receipt["blobs"]["archive"]:
            raise ValueError("symlink audit archive record differs from manifest")
        archive_path = root / "audit.tar.gz"
        _fetch_blob(store, receipt["blobs"]["archive"], archive_path)
        listing = extract_symlink_archive(archive_path, manifest, root / "readback")
    return {
        "entries": len(listing),
        "listing": listing,
        "manifest": manifest,
        "whole_listing_exact": True,
    }


def publish(
    *,
    case,
    root,
    hdfs_namespace,
    evidence,
    host_source_receipt=None,
    auth_source="token-file",
    preserve_symlinks=False,
    readback=False,
    write_receipt=False,
    move_to=None,
    scientific_processing=SCIENTIFIC_PROCESSING,
    store=None,
    store_descriptor=None,
    tool_digest=None,
    host_source_admitter=_admit_host_sources,
    identifier=None,
    same_device=_same_device,
):
    if auth_source != "token-file":
        raise ValueError("--auth-source token-file is required")
    if not preserve_symlinks or not readback or not write_receipt:
        raise ValueError("--preserve-symlinks, --readback and --receipt are required")
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
    packed = run_dir / "packed"
    packed.mkdir()
    archive = packed / "audit.tar.gz"
    manifest = create_symlink_archive(root, archive)
    archive_blob = store.put(_blob_key(hdfs_namespace, identifier, "audit.tar.gz"), archive)
    manifest.update(
        {
            "area": "runs",
            "child": hdfs_namespace,
            "run_id": identifier,
            "kind": "symlink-audit",
            "archive": archive_blob,
        }
    )
    manifest_path = packed / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2))
    manifest_blob = store.put(_blob_key(hdfs_namespace, identifier, "manifest.json"), manifest_path)
    receipt = {
        "schema_version": 1,
        "store_descriptor": descriptor,
        "tool_sha256": _normalize_tool_digest(tool_digest),
        "verified_by_readback": True,
        "blobs": {"archive": archive_blob, "manifest": manifest_blob},
    }
    audit_result = audit(receipt, store=store)
    receipt_path = run_dir / "verified-publication.json"
    _write_json_idempotent(receipt_path, receipt)
    if move_to is not None:
        moved_listing = _move_tree(root, move_to, audit_result["listing"], same_device)
        completed = {"moved_from": str(root), "moved_to": str(move_to), "listing": moved_listing}
        completed_path = run_dir / "move-completed.json"
        completed_path.write_text(json.dumps(completed, indent=2))
    print("ADMITTED blob-store symlink audit publication", receipt_path, "moved", move_to is not None, flush=True)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--hdfs-namespace", required=True)
    parser.add_argument("--auth-source", default="token-file", choices=["token-file"])
    parser.add_argument("--host-source-receipt", type=Path)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--preserve-symlinks", action="store_true")
    parser.add_argument("--readback", action="store_true")
    parser.add_argument("--receipt", action="store_true", dest="write_receipt")
    parser.add_argument("--move-to", type=Path)
    args = parser.parse_args(argv)
    publish(
        case=args.case,
        root=args.root,
        hdfs_namespace=args.hdfs_namespace,
        evidence=args.evidence,
        host_source_receipt=args.host_source_receipt,
        auth_source=args.auth_source,
        preserve_symlinks=args.preserve_symlinks,
        readback=args.readback,
        write_receipt=args.write_receipt,
        move_to=args.move_to,
    )


if __name__ == "__main__":
    main()
