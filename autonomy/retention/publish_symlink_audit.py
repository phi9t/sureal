"""Publish and optionally retire a symlink-preserving scientific audit tree."""

import argparse
import gzip
import json
import os
import shutil
import tarfile
import uuid
from pathlib import Path

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
    WaystoneClient,
    _require_evidence_root,
    _safe_component,
    _waystone_tool_pins,
)
from retention.publisher_runtime import admitted_host_sources


SNAPSHOT_TARGET = "//autonomy/retention:publish_symlink_audit"
HOST_SOURCE_REQUIRED = (
    "retention/publish_symlink_audit.py",
    "retention/publish_scientific_directory.py",
    "retention/publisher_runtime.py",
    "resources/resource_archive.py",
    "evidence/source_snapshot.py",
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
    waystone=None,
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
    identifier = identifier or (case + "-" + uuid.uuid4().hex)
    run_dir = evidence / ("hdfs-retention-" + identifier)
    run_dir.mkdir(exist_ok=False)
    host_pins, admitted_package = host_source_admitter(host_source_receipt, PACKAGE_ROOT, run_dir / "host-source")
    waystone_tool_pins = {}
    if waystone is None:
        waystone_tool_pins = _waystone_tool_pins()

        def validate_external():
            _validate_host_sources(admitted_package, host_pins)

        waystone = WaystoneClient(auth_source=auth_source, before_run=validate_external, tool_pins=waystone_tool_pins)
    layout = waystone.layout_profile(run_dir)
    remote = layout["paths"]["runs"].rstrip("/") + "/" + hdfs_namespace + "/" + identifier
    authenticated_read = waystone.authenticated_read(layout["project_root"], run_dir)
    packed = run_dir / "packed"
    packed.mkdir()
    archive = packed / "audit.tar.gz"
    manifest = create_symlink_archive(root, archive)
    manifest_path = packed / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2))
    archive_uri = remote + "/" + manifest["archive_sha256"] + "/audit.tar.gz"
    manifest_uri = remote + "/" + manifest["archive_sha256"] + "/manifest.json"
    checks = [
        {
            "stage": "create-live",
            "command": ["tar", "--preserve-symlinks", str(root)],
            "exit_code": 0,
            "validation": {
                "members": len(manifest["listing"]),
                "archive_sha256": manifest["archive_sha256"],
            },
        },
        waystone.put_new(archive, archive_uri, "archive-put", run_dir),
    ]
    download = run_dir / "download"
    download.mkdir()
    checks.append(waystone.get(archive_uri, download / "audit.tar.gz", "archive-get", run_dir))
    if (download / "audit.tar.gz").read_bytes() != archive.read_bytes():
        raise ValueError("archive readback differs")
    checks.append(waystone.put_new(manifest_path, manifest_uri, "manifest-put", run_dir))
    checks.append(waystone.get(manifest_uri, download / "manifest.json", "manifest-get", run_dir))
    if file_sha256(download / "manifest.json") != file_sha256(manifest_path):
        raise ValueError("manifest readback differs")
    readback_manifest = json.loads((download / "manifest.json").read_text())
    readback_listing = extract_symlink_archive(download / "audit.tar.gz", readback_manifest, run_dir / "readback")
    checks.append(
        {
            "stage": "readback-listing",
            "command": ["extract", "audit.tar.gz"],
            "exit_code": 0,
            "validation": {"listing_equal": readback_listing == manifest["listing"]},
        }
    )
    receipt = {
        "schema_version": 1,
        "case": case,
        "root": str(root),
        "hdfs_namespace": hdfs_namespace,
        "host_source_pins": host_pins,
        "waystone_tool_sha256": waystone_tool_pins,
        "authenticated_read": authenticated_read,
        "archive_hdfs_uri": archive_uri,
        "manifest_hdfs_uri": manifest_uri,
        "archive_sha256": manifest["archive_sha256"],
        "manifest_sha256": file_sha256(manifest_path),
        "source_listing": manifest["listing"],
        "readback_listing": readback_listing,
        "checks": checks,
    }
    if move_to is not None:
        moved_listing = _move_tree(root, move_to, manifest["listing"], same_device)
        completed = {"moved_from": str(root), "moved_to": str(move_to), "listing": moved_listing}
        completed_path = run_dir / "move-completed.json"
        completed_path.write_text(json.dumps(completed, indent=2))
        receipt["moved_listing"] = moved_listing
        receipt["move"] = {
            "stage": "move-completed",
            "command": ["rename", str(root), str(move_to)],
            "exit_code": 0,
            "move_completed_sha256": file_sha256(completed_path),
        }
    receipt_path = run_dir / "verified-publication.json"
    receipt_path.write_text(json.dumps(receipt, indent=2))
    print("ADMITTED HDFS symlink audit retention", receipt_path, "moved", move_to is not None, flush=True)
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
