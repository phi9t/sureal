"""Blob-store backed publication workflow for retained evidence bundles."""

import datetime
import fcntl
import gzip
import hashlib
import json
import os
import shutil
import tarfile
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Mapping

from blob_store.core import (
    BlobStore,
    BlobStoreError,
    blob_adapter_from_descriptor,
    default_waystone_descriptor,
    normalize_waystone_tool_digest,
    validate_blob_key,
    waystone_tool_pins,
)
from evidence.source_snapshot import file_sha256, require_digest, require_regular_file, safe_member_name
from evidence.journal import read_entries


DEFAULT_RESOURCE_AREA = "runs"
DEFAULT_RESOURCE_CHILD = "perception-resource-closures"
DEFAULT_CHECKPOINT_AREA = "checkpoints"
DEFAULT_CHECKPOINT_CHILD = "perception-sustained-checkpoints"
DEFAULT_NATIVE_CACHE_AREA = "runs"
DEFAULT_NATIVE_CACHE_CHILD = "perception-native-cache"
DEFAULT_NATIVE_CACHE_KIND = "cache"
DEFAULT_SUSTAINED_PILOT_AREA = "runs"
DEFAULT_SUSTAINED_PILOT_CHILD = "perception-sustained-pilot"
DEFAULT_SUSTAINED_PILOT_KIND = "pilot"
DEFAULT_RESEARCH_JOURNAL_AREA = "runs"
DEFAULT_RESEARCH_JOURNAL_CHILD = "perception-research-journal"
DEFAULT_RESEARCH_JOURNAL_KIND = "snapshot"
RESEARCH_JOURNAL_FILE_NAMES = (
    "experiment-registry.json",
    "experiment-tracker.md",
    "experiments.json",
    "research-journal.jsonl",
    "research-journal.md",
)
DEFAULT_CHUNK_SIZE_BYTES = 128 * 1024 * 1024
WAYSTONE_DESCRIPTOR = default_waystone_descriptor()
STREAM_CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True)
class PublicationSpec:
    """Data-only publication request consumed by :func:`publish`.

    ``payload`` is interpreted only by ``inventory``.  That keeps each future
    publication kind responsible for naming its files while the workflow owns
    staging, archive keys, storage, manifest writing and audit.
    """

    payload: object
    inventory: Callable[[object], Mapping[str, Mapping[str, object]]]
    area: str
    child: str
    run_id: str
    kind: str
    staging_style: str
    mode: str
    release: bool
    store: BlobStore
    store_descriptor: Mapping[str, object]
    tool_digest: Mapping[str, str]
    staging_root: Path
    reserve: Callable[[Path, int], object]
    chunk_size_bytes: int = DEFAULT_CHUNK_SIZE_BYTES

    def inventory_map(self) -> dict[str, dict[str, object]]:
        return _normalize_inventory(self.inventory(self.payload))

    def with_payload(self, payload):
        return replace(self, payload=payload)


def resource_bundle_spec(
    *,
    payload,
    run_id,
    kind,
    store,
    store_descriptor,
    tool_digest,
    staging_root,
    reserve,
    chunk_size_bytes=DEFAULT_CHUNK_SIZE_BYTES,
):
    """Build the resource-bundle publication spec used by sustained runs."""

    return PublicationSpec(
        payload=payload,
        inventory=lambda value: value,
        area=DEFAULT_RESOURCE_AREA,
        child=DEFAULT_RESOURCE_CHILD,
        run_id=run_id,
        kind=kind,
        staging_style="hardlink",
        mode="archive",
        release=False,
        store=store,
        store_descriptor=dict(store_descriptor),
        tool_digest=dict(tool_digest),
        staging_root=Path(staging_root),
        reserve=reserve,
        chunk_size_bytes=chunk_size_bytes,
    )


def research_journal_spec(
    *,
    research_root,
    run_id,
    store,
    store_descriptor,
    tool_digest,
    staging_root,
    reserve,
    chunk_size_bytes=DEFAULT_CHUNK_SIZE_BYTES,
):
    """Build the direct-files publication spec for the research journal."""

    return PublicationSpec(
        payload=Path(research_root),
        inventory=_research_journal_inventory,
        area=DEFAULT_RESEARCH_JOURNAL_AREA,
        child=DEFAULT_RESEARCH_JOURNAL_CHILD,
        run_id=run_id,
        kind=DEFAULT_RESEARCH_JOURNAL_KIND,
        staging_style="copy",
        mode="direct",
        release=False,
        store=store,
        store_descriptor=dict(store_descriptor),
        tool_digest=dict(tool_digest),
        staging_root=Path(staging_root),
        reserve=reserve,
        chunk_size_bytes=chunk_size_bytes,
    )


def native_cache_spec(
    *,
    payload,
    run_id,
    release,
    store,
    store_descriptor,
    tool_digest,
    staging_root,
    reserve,
    chunk_size_bytes=DEFAULT_CHUNK_SIZE_BYTES,
):
    """Build the archive-mode publication spec for a native input cache."""

    return PublicationSpec(
        payload=payload,
        inventory=lambda value: value,
        area=DEFAULT_NATIVE_CACHE_AREA,
        child=DEFAULT_NATIVE_CACHE_CHILD,
        run_id=run_id,
        kind=DEFAULT_NATIVE_CACHE_KIND,
        staging_style="copy",
        mode="archive",
        release=release,
        store=store,
        store_descriptor=dict(store_descriptor),
        tool_digest=dict(tool_digest),
        staging_root=Path(staging_root),
        reserve=reserve,
        chunk_size_bytes=chunk_size_bytes,
    )


def sustained_pilot_spec(
    *,
    payload,
    run_id,
    release,
    store,
    store_descriptor,
    tool_digest,
    staging_root,
    reserve,
    chunk_size_bytes=DEFAULT_CHUNK_SIZE_BYTES,
):
    """Build the archive-mode publication spec for a sustained pilot payload."""

    return PublicationSpec(
        payload=payload,
        inventory=lambda value: value,
        area=DEFAULT_SUSTAINED_PILOT_AREA,
        child=DEFAULT_SUSTAINED_PILOT_CHILD,
        run_id=run_id,
        kind=DEFAULT_SUSTAINED_PILOT_KIND,
        staging_style="copy",
        mode="archive",
        release=release,
        store=store,
        store_descriptor=dict(store_descriptor),
        tool_digest=dict(tool_digest),
        staging_root=Path(staging_root),
        reserve=reserve,
        chunk_size_bytes=chunk_size_bytes,
    )


def publish_research_journal(
    *,
    research_root=None,
    run_id=None,
    store=None,
    store_descriptor=None,
    tool_digest=None,
    staging_root=None,
    receipt_path=None,
    legacy_receipt_path=None,
    reserve=None,
):
    """Publish the research journal through the publication module."""

    research_root = Path(research_root) if research_root is not None else Path(__file__).resolve().parents[1] / "research"
    if run_id is None:
        run_id = "snapshot-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    descriptor = dict(store_descriptor or WAYSTONE_DESCRIPTOR)
    if store is None:
        store = BlobStore(blob_adapter_from_descriptor(descriptor))
    tool_digest = store_tool_digest(store, tool_digest)
    if staging_root is None:
        staging_root = research_root / ".publication-stage" / run_id
    if reserve is None:
        reserve = lambda _path, _maximum_new_bytes: None
    spec = research_journal_spec(
        research_root=research_root,
        run_id=run_id,
        store=store,
        store_descriptor=descriptor,
        tool_digest=tool_digest,
        staging_root=staging_root,
        reserve=reserve,
    )
    receipt = publish(spec)
    if receipt_path is not None:
        write_research_journal_receipt(receipt_path, receipt, legacy_path=legacy_receipt_path)
    return receipt


def write_research_journal_receipt(path, receipt, *, legacy_path=None) -> None:
    """Replace the active journal receipt after preserving old HDFS bytes."""

    _normalize_receipt(receipt)
    target = Path(path)
    legacy = Path(legacy_path) if legacy_path is not None else target.with_name(
        "research-journal-hdfs-legacy-verified.json"
    )
    data = _json_bytes(receipt)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        current = target.read_bytes()
        if current == data:
            return
        if _is_new_publication_receipt(current):
            raise ValueError("research journal publication receipt changed")
        if legacy.exists():
            if legacy.read_bytes() != current:
                raise ValueError("research journal legacy receipt differs")
        else:
            legacy.write_bytes(current)
    target.write_bytes(data)


def sustained_checkpoint_spec(
    *,
    payload,
    run_id,
    kind,
    release,
    store,
    store_descriptor,
    tool_digest,
    staging_root,
    reserve,
    chunk_size_bytes=DEFAULT_CHUNK_SIZE_BYTES,
):
    """Build a caller-controlled sustained-checkpoint publication spec."""

    return PublicationSpec(
        payload=payload,
        inventory=lambda value: value,
        area=DEFAULT_CHECKPOINT_AREA,
        child=DEFAULT_CHECKPOINT_CHILD,
        run_id=run_id,
        kind=kind,
        staging_style="copy",
        mode="archive",
        release=release,
        store=store,
        store_descriptor=dict(store_descriptor),
        tool_digest=dict(tool_digest),
        staging_root=Path(staging_root),
        reserve=reserve,
        chunk_size_bytes=chunk_size_bytes,
    )


def release_plan(spec: PublicationSpec) -> list[dict[str, object]]:
    """Return the local release plan implied by a publication spec."""

    _validate_spec(spec)
    inventory = spec.inventory_map()
    plan = []
    for index, names in enumerate(_partition_inventory(inventory, spec.chunk_size_bytes)):
        archive_key = _blob_key(spec, f"archive-{index:03d}.tar.gz")
        for name in sorted(names):
            entry = inventory[name]
            plan.append(
                {
                    "path": name,
                    "local_path": entry["path"],
                    "sha256": entry["sha256"],
                    "bytes": entry["bytes"],
                    "archive_blob_key": archive_key,
                }
            )
    if not plan:
        raise ValueError("publication release inventory required")
    return plan


def publish(spec: PublicationSpec) -> dict:
    """Stage, archive, store, read back, manifest and audit one publication."""

    _validate_spec(spec)
    inventory = spec.inventory_map()
    total_bytes = sum(entry["bytes"] for entry in inventory.values())
    spec.staging_root.mkdir(parents=True, exist_ok=True)
    spec.reserve(Path(spec.staging_root), total_bytes)
    with tempfile.TemporaryDirectory(prefix="publication.", dir=spec.staging_root) as directory:
        work = Path(directory)
        staged = _stage_inventory(spec, inventory, work / "raw")
        if spec.mode == "archive":
            chunks = []
            for index, names in enumerate(_partition_inventory(inventory, spec.chunk_size_bytes)):
                archive = work / f"archive-{index:03d}.tar.gz"
                _write_archive(archive, staged, names)
                chunks.append(spec.store.put(_blob_key(spec, f"archive-{index:03d}.tar.gz"), archive))
            manifest = {
                "schema_version": 1,
                "area": spec.area,
                "child": spec.child,
                "run_id": spec.run_id,
                "kind": spec.kind,
                "mode": spec.mode,
                "inventory": _public_inventory(inventory),
                "chunks": chunks,
            }
            receipt_blobs = {"chunks": chunks}
        else:
            files = []
            for name in sorted(staged):
                files.append(spec.store.put(_blob_key(spec, name), staged[name]["path"]))
            manifest = {
                "schema_version": 1,
                "area": spec.area,
                "child": spec.child,
                "run_id": spec.run_id,
                "kind": spec.kind,
                "mode": spec.mode,
                "inventory": _public_inventory(inventory),
                "files": files,
            }
            receipt_blobs = {"files": files}
        manifest_path = work / "manifest.json"
        _write_json(manifest_path, manifest)
        manifest_blob = spec.store.put(_blob_key(spec, "manifest.json"), manifest_path)
    receipt = {
        "schema_version": 1,
        "store_descriptor": dict(spec.store_descriptor),
        "tool_sha256": _normalize_tool_digest(spec.tool_digest),
        "verified_by_readback": True,
        "blobs": dict({"manifest": manifest_blob}, **receipt_blobs),
    }
    audit(receipt, store=spec.store)
    if spec.release:
        _release_inventory(inventory)
    return receipt


def audit(receipt, *, store=None) -> dict[str, object]:
    """Verify a publication receipt against its manifest and stored chunks."""

    receipt = _normalize_receipt(receipt)
    if store is None:
        store = BlobStore(blob_adapter_from_descriptor(receipt["store_descriptor"]))
    manifest = _fetch_json_blob(store, receipt["blobs"]["manifest"])
    if manifest.get("schema_version") != 1:
        raise ValueError("publication manifest shape required")
    if manifest.get("mode") == "direct":
        return _audit_direct_publication(receipt, manifest, store)
    if manifest.get("mode") != "archive":
        raise ValueError("publication manifest shape required")
    expected_key_prefix = _manifest_key_prefix(manifest)
    if receipt["blobs"]["manifest"]["key"] != expected_key_prefix + "/manifest.json":
        raise ValueError("publication manifest key differs")
    if manifest.get("chunks") != receipt["blobs"]["chunks"]:
        raise ValueError("publication chunk records differ from manifest")
    inventory = _normalize_manifest_inventory(manifest.get("inventory"))
    seen = {}
    payload_bytes = 0
    chunk_inventories = []
    with tempfile.TemporaryDirectory(prefix="publication-audit.") as directory:
        root = Path(directory)
        for index, chunk in enumerate(receipt["blobs"]["chunks"]):
            expected_key = expected_key_prefix + f"/archive-{index:03d}.tar.gz"
            if chunk["key"] != expected_key:
                raise ValueError("publication chunk key differs")
            archive = root / f"archive-{index:03d}.tar.gz"
            _fetch_blob(store, chunk, archive)
            chunk_inventory = _archive_inventory(archive)
            chunk_inventories.append({"blob": chunk, "inventory": chunk_inventory})
            for name, entry in chunk_inventory.items():
                if name in seen:
                    raise ValueError("publication inventory contains duplicate member")
                if name not in inventory or inventory[name] != entry:
                    raise ValueError("publication archive member differs from manifest inventory")
                seen[name] = entry
                payload_bytes += entry["bytes"]
    if seen != inventory:
        raise ValueError("publication archive inventory is incomplete")
    return {
        "files": len(seen),
        "chunks": len(receipt["blobs"]["chunks"]),
        "payload_bytes": payload_bytes,
        "whole_member_union_exact": True,
        "manifest": manifest,
        "inventory": inventory,
        "chunk_inventories": chunk_inventories,
    }


def publish_bundle(backend, kind, inventory):
    """Sustained-run resource-bundle wrapper around the publication module."""

    backend.guard()
    descriptor = dict(getattr(backend, "resource_blob_store_descriptor", WAYSTONE_DESCRIPTOR))
    store = getattr(backend, "resource_blob_store", None)
    if store is None:
        store = BlobStore(blob_adapter_from_descriptor(descriptor))
    tool_digest = getattr(backend, "resource_blob_tool_digest", None)
    tool_digest = store_tool_digest(store, tool_digest)
    cache_root = Path(getattr(backend, "resource_cache_root", backend.R.parent.parent))
    work_root = Path(getattr(backend, "resource_work_root", backend.output.parent))
    reserve = getattr(backend, "resource_reserve_write", None)
    if reserve is None:
        from resources.scientific_budget import reserve_write

        reserve = reserve_write
    receipt_dir = cache_root / "insula" / ("resource-publication-" + backend.R.name + "-" + kind)
    receipt_dir.mkdir(parents=True, exist_ok=True)
    spec = resource_bundle_spec(
        payload=inventory,
        run_id=backend.R.name,
        kind=kind,
        store=store,
        store_descriptor=descriptor,
        tool_digest=tool_digest,
        staging_root=work_root / ("publication-stage-" + backend.R.name + "-" + kind),
        reserve=reserve,
    )
    receipt = publish(spec)
    receipt_path = receipt_dir / "verified-publication.json"
    _write_json_idempotent(receipt_path, receipt)
    return {
        "path": str(receipt_path),
        "sha256": file_sha256(receipt_path),
        "manifest_key": receipt["blobs"]["manifest"]["key"],
        "kind": kind,
    }


def _validate_spec(spec: PublicationSpec) -> None:
    if not isinstance(spec, PublicationSpec):
        raise ValueError("publication spec required")
    if spec.staging_style not in {"hardlink", "copy"}:
        raise ValueError("publication staging style required")
    if spec.mode not in {"archive", "direct"}:
        raise ValueError("publication mode required")
    if type(spec.release) is not bool:
        raise ValueError("publication release flag required")
    if type(spec.chunk_size_bytes) is not int or spec.chunk_size_bytes <= 0:
        raise ValueError("positive publication chunk size required")
    _key_prefix(spec)
    _normalize_tool_digest(spec.tool_digest)
    if not isinstance(spec.store_descriptor, Mapping):
        raise ValueError("publication store descriptor required")


def publication_store_descriptor(value):
    if value is None:
        return dict(WAYSTONE_DESCRIPTOR)
    descriptor = json.loads(value)
    if not isinstance(descriptor, dict):
        raise ValueError("store descriptor object required")
    return descriptor


def store_tool_digest(store, tool_digest=None, *, fallback_to_waystone=True):
    try:
        adapter_digest = getattr(getattr(store, "_adapter", None), "tool_sha256", None)
        normalized_adapter_digest = _normalize_tool_digest(adapter_digest) if adapter_digest is not None else None
    except Exception as error:
        if tool_digest is not None or not fallback_to_waystone:
            raise ValueError("publication tool digest required from blob store adapter") from error
        normalized_adapter_digest = None
    if tool_digest is None:
        if normalized_adapter_digest is not None:
            return normalized_adapter_digest
        if fallback_to_waystone:
            try:
                return _normalize_tool_digest(waystone_tool_pins())
            except (OSError, RuntimeError, ValueError) as error:
                raise ValueError("publication tool digest required") from error
        raise ValueError("publication tool digest required when blob store adapter does not expose tool_sha256")
    normalized = _normalize_tool_digest(tool_digest)
    if normalized_adapter_digest is not None and normalized != normalized_adapter_digest:
        raise ValueError("publication tool digest differs from blob store adapter")
    return normalized


def store_tool_digest_from_json(value, store):
    if value is None:
        return store_tool_digest(store)
    digest = json.loads(value)
    if not isinstance(digest, dict):
        raise ValueError("tool digest object required")
    return store_tool_digest(store, digest)


def write_publication_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def write_release_completed(path: Path, receipt_path: Path, plan) -> None:
    write_publication_json(
        path,
        {
            "publication_receipt_sha256": file_sha256(receipt_path),
            "released": plan,
        },
    )


def _audit_direct_publication(receipt, manifest, store) -> dict[str, object]:
    expected_key_prefix = _manifest_key_prefix(manifest)
    if receipt["blobs"]["manifest"]["key"] != expected_key_prefix + "/manifest.json":
        raise ValueError("publication manifest key differs")
    if manifest.get("files") != receipt["blobs"]["files"]:
        raise ValueError("publication file records differ from manifest")
    inventory = _normalize_manifest_inventory(manifest.get("inventory"))
    files = receipt["blobs"]["files"]
    if len(files) != len(inventory):
        raise ValueError("publication direct inventory is incomplete")
    payload_bytes = 0
    with tempfile.TemporaryDirectory(prefix="publication-audit.") as directory:
        root = Path(directory)
        for name, blob in zip(sorted(inventory), files):
            expected_key = expected_key_prefix + "/" + validate_blob_key(name)
            if blob["key"] != expected_key:
                raise ValueError("publication direct file key differs")
            expected = inventory[name]
            if blob["sha256"] != expected["sha256"] or blob["bytes"] != expected["bytes"]:
                raise ValueError("publication direct file record differs from manifest inventory")
            destination = root / name
            _fetch_blob(store, blob, destination)
            payload_bytes += blob["bytes"]
    return {
        "files": len(files),
        "chunks": 0,
        "payload_bytes": payload_bytes,
        "whole_member_union_exact": True,
        "manifest": manifest,
        "inventory": inventory,
    }


def _research_journal_inventory(research_root) -> dict[str, dict[str, object]]:
    root = Path(research_root)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("research journal root must be a regular directory")
    tracker_lock = root / "experiment-tracker.lock"
    journal_lock = root / "research-journal.lock"
    with tracker_lock.open("a") as tracker, journal_lock.open("a") as journal:
        fcntl.flock(tracker, fcntl.LOCK_EX)
        fcntl.flock(journal, fcntl.LOCK_SH)
        read_entries(root / "research-journal.jsonl")
        names = list(RESEARCH_JOURNAL_FILE_NAMES)
        evidence_root = root / "journal-evidence"
        if evidence_root.exists():
            if not evidence_root.is_dir() or evidence_root.is_symlink():
                raise ValueError("regular immutable evidence directory required")
            names.extend(
                "journal-evidence/" + child.name
                for child in sorted(evidence_root.iterdir())
                if child.is_file() and not child.is_symlink()
            )
        return _inventory_from_root(root, names)


def _inventory_from_root(root: Path, names) -> dict[str, dict[str, object]]:
    inventory = {}
    for name in sorted(names):
        name = safe_member_name(name)
        path = require_regular_file(root / name)
        inventory[name] = {"path": str(path), "sha256": file_sha256(path), "bytes": path.stat().st_size}
    return inventory


def _normalize_inventory(value) -> dict[str, dict[str, object]]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError("nonempty publication inventory required")
    result = {}
    for name, entry in sorted(value.items()):
        name = safe_member_name(name)
        if not isinstance(entry, Mapping):
            raise ValueError("publication inventory entry required")
        path = require_regular_file(entry.get("path"))
        digest = require_digest(entry.get("sha256"))
        size = entry.get("bytes")
        if type(size) is not int or size < 0:
            raise ValueError("publication inventory byte count required")
        if path.stat().st_size != size or file_sha256(path) != digest:
            raise ValueError("publication inventory source bytes changed")
        if name in result:
            raise ValueError("publication inventory names must be unique")
        result[name] = {"path": str(path), "sha256": digest, "bytes": size}
    return result


def _normalize_manifest_inventory(value) -> dict[str, dict[str, object]]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError("publication manifest inventory required")
    result = {}
    for name, entry in sorted(value.items()):
        name = safe_member_name(name)
        if not isinstance(entry, Mapping):
            raise ValueError("publication manifest inventory entry required")
        result[name] = {
            "sha256": require_digest(entry.get("sha256")),
            "bytes": _require_nonnegative_int(entry.get("bytes"), "publication manifest byte count required"),
        }
    return result


def _public_inventory(inventory):
    return {name: {"sha256": entry["sha256"], "bytes": entry["bytes"]} for name, entry in sorted(inventory.items())}


def _stage_inventory(spec: PublicationSpec, inventory, destination: Path):
    staged = {}
    destination.mkdir()
    for name, entry in inventory.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if spec.staging_style == "hardlink":
            os.link(entry["path"], target)
        else:
            shutil.copyfile(entry["path"], target)
        if target.stat().st_size != entry["bytes"] or file_sha256(target) != entry["sha256"]:
            raise ValueError("staged publication member differs from source")
        staged[name] = {"path": str(target), "sha256": entry["sha256"], "bytes": entry["bytes"]}
    return staged


def _release_inventory(inventory) -> None:
    plan = []
    for name, entry in sorted(inventory.items()):
        path = require_regular_file(entry["path"])
        if path.stat().st_size != entry["bytes"] or file_sha256(path) != entry["sha256"]:
            raise ValueError("publication release source bytes changed")
        plan.append(path)
    for path in plan:
        path.unlink()


def _partition_inventory(inventory, limit):
    chunks = []
    current = []
    size = 0
    for name, entry in sorted(inventory.items()):
        if current and size + entry["bytes"] > limit:
            chunks.append(current)
            current = []
            size = 0
        current.append(name)
        size += entry["bytes"]
    if current:
        chunks.append(current)
    return chunks


def _write_archive(path: Path, staged, names) -> None:
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gzip_file:
            with tarfile.open(fileobj=gzip_file, mode="w") as archive:
                for name in sorted(names):
                    entry = staged[name]
                    source = Path(entry["path"])
                    if source.stat().st_size != entry["bytes"]:
                        raise ValueError("staged publication member size changed")
                    info = tarfile.TarInfo(name)
                    info.size = entry["bytes"]
                    info.mtime = 0
                    info.mode = 0o444
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    with source.open("rb") as input_file:
                        archive.addfile(info, input_file)


def _archive_inventory(path: Path):
    result = {}
    try:
        with tarfile.open(path, "r:gz") as archive:
            for member in archive:
                name = safe_member_name(member.name)
                if not member.isfile() or name in result:
                    raise ValueError("publication archive member shape required")
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError("publication archive member bytes required")
                digest, size = _stream_sha256_and_size(stream, member.size)
                result[name] = {"sha256": digest, "bytes": size}
    except (tarfile.TarError, OSError) as error:
        raise ValueError("publication archive unreadable") from error
    return result


def _fetch_json_blob(store, blob):
    with tempfile.TemporaryDirectory(prefix="publication-manifest.") as directory:
        path = Path(directory) / "manifest.json"
        _fetch_blob(store, blob, path)
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError as error:
            raise ValueError("publication manifest JSON required") from error


def _fetch_blob(store, blob, destination: Path) -> None:
    blob = _normalize_blob(blob)
    try:
        store.get(blob["key"], destination, blob["sha256"], expected_bytes=blob["bytes"])
    except BlobStoreError:
        raise
    except Exception as error:
        raise ValueError("publication blob cannot be read back") from error
    if destination.stat().st_size != blob["bytes"]:
        raise ValueError("publication blob byte count differs")


def _normalize_receipt(receipt):
    if not isinstance(receipt, Mapping):
        raise ValueError("publication receipt required")
    if set(receipt) != {"schema_version", "store_descriptor", "tool_sha256", "verified_by_readback", "blobs"}:
        raise ValueError("publication receipt shape required")
    if receipt["schema_version"] != 1 or receipt["verified_by_readback"] is not True:
        raise ValueError("publication readback receipt required")
    blobs = receipt["blobs"]
    if not isinstance(blobs, Mapping) or "manifest" not in blobs:
        raise ValueError("publication blob records required")
    result = {
        "schema_version": 1,
        "store_descriptor": dict(receipt["store_descriptor"]),
        "tool_sha256": _normalize_receipt_tool_digest(receipt["tool_sha256"]),
        "verified_by_readback": True,
        "blobs": {
            "manifest": _normalize_blob(blobs["manifest"]),
        },
    }
    if set(blobs) == {"manifest", "chunks"}:
        chunks = blobs["chunks"]
        if not isinstance(chunks, list) or not chunks:
            raise ValueError("publication chunks required")
        result["blobs"]["chunks"] = [_normalize_blob(chunk) for chunk in chunks]
        return result
    if set(blobs) == {"manifest", "files"}:
        files = blobs["files"]
        if not isinstance(files, list) or not files:
            raise ValueError("publication files required")
        result["blobs"]["files"] = [_normalize_blob(blob) for blob in files]
        return result
    raise ValueError("publication blob records required")


def _normalize_blob(value):
    if not isinstance(value, Mapping) or set(value) != {"key", "sha256", "bytes"}:
        raise ValueError("publication blob record required")
    return {
        "key": validate_blob_key(value["key"]),
        "sha256": require_digest(value["sha256"]),
        "bytes": _require_nonnegative_int(value["bytes"], "publication blob byte count required"),
    }


def _normalize_tool_digest(value):
    try:
        return normalize_waystone_tool_digest(value)
    except ValueError as error:
        raise ValueError("publication tool digest required") from error


def _normalize_receipt_tool_digest(value):
    if not isinstance(value, Mapping) or not value:
        raise ValueError("publication tool digest required")
    return {_validate_tool_role(role): require_digest(digest) for role, digest in sorted(value.items())}


def _validate_tool_role(value) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("publication tool digest role required")
    if "/" in value or "\\" in value or value in {".", ".."}:
        raise ValueError("publication tool digest role must not be a path")
    return value


def _require_nonnegative_int(value, message):
    if type(value) is not int or value < 0:
        raise ValueError(message)
    return value


def _blob_key(spec: PublicationSpec, name: str) -> str:
    return _key_prefix(spec) + "/" + validate_blob_key(name)


def _key_prefix(spec: PublicationSpec) -> str:
    return validate_blob_key("/".join([spec.area, spec.child, spec.run_id, spec.kind]))


def _manifest_key_prefix(manifest) -> str:
    try:
        return validate_blob_key(
            "/".join([manifest["area"], manifest["child"], manifest["run_id"], manifest["kind"]])
        )
    except (KeyError, TypeError) as error:
        raise ValueError("publication manifest key fields required") from error


def _write_json(path: Path, value) -> None:
    path.write_bytes(_json_bytes(value))


def _write_json_idempotent(path: Path, value) -> None:
    data = _json_bytes(value).decode()
    if path.exists():
        if path.read_text() != data:
            raise ValueError("publication receipt changed")
        return
    path.write_text(data)


def _json_bytes(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _is_new_publication_receipt(data: bytes) -> bool:
    try:
        value = json.loads(data)
        _normalize_receipt(value)
        return True
    except (json.JSONDecodeError, TypeError, ValueError):
        return False


def _stream_sha256_and_size(stream, expected_size: int) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    while True:
        chunk = stream.read(STREAM_CHUNK_BYTES)
        if not chunk:
            break
        size += len(chunk)
        if size > expected_size:
            raise ValueError("publication archive member size differs")
        digest.update(chunk)
    if size != expected_size:
        raise ValueError("publication archive member size differs")
    return digest.hexdigest(), size
