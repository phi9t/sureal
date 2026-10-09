"""Blob-store backed publication workflow for retained evidence bundles."""

import gzip
import io
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
    blob_adapter_from_descriptor,
    validate_blob_key,
    waystone_tool_pins,
)
from evidence.source_snapshot import file_sha256, require_digest, require_regular_file, safe_member_name


DEFAULT_RESOURCE_AREA = "runs"
DEFAULT_RESOURCE_CHILD = "perception-resource-closures"
DEFAULT_CHUNK_SIZE_BYTES = 128 * 1024 * 1024
WAYSTONE_DESCRIPTOR = {"kind": "waystone", "project": "sureal"}


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


def publish(spec: PublicationSpec) -> dict:
    """Stage, archive, store, read back, manifest and audit one publication."""

    _validate_spec(spec)
    inventory = spec.inventory_map()
    total_bytes = sum(entry["bytes"] for entry in inventory.values())
    spec.reserve(Path(spec.staging_root), total_bytes)
    spec.staging_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="publication.", dir=spec.staging_root) as directory:
        work = Path(directory)
        staged = _stage_inventory(spec, inventory, work / "raw")
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
        manifest_path = work / "manifest.json"
        _write_json(manifest_path, manifest)
        manifest_blob = spec.store.put(_blob_key(spec, "manifest.json"), manifest_path)
    receipt = {
        "schema_version": 1,
        "store_descriptor": dict(spec.store_descriptor),
        "tool_sha256": _normalize_tool_digest(spec.tool_digest),
        "verified_by_readback": True,
        "blobs": {
            "manifest": manifest_blob,
            "chunks": chunks,
        },
    }
    audit(receipt, store=spec.store)
    return receipt


def audit(receipt, *, store=None) -> dict[str, object]:
    """Verify a publication receipt against its manifest and stored chunks."""

    receipt = _normalize_receipt(receipt)
    if store is None:
        store = BlobStore(blob_adapter_from_descriptor(receipt["store_descriptor"]))
    manifest = _fetch_json_blob(store, receipt["blobs"]["manifest"])
    if manifest.get("schema_version") != 1 or manifest.get("mode") != "archive":
        raise ValueError("publication manifest shape required")
    expected_key_prefix = _manifest_key_prefix(manifest)
    if receipt["blobs"]["manifest"]["key"] != expected_key_prefix + "/manifest.json":
        raise ValueError("publication manifest key differs")
    if manifest.get("chunks") != receipt["blobs"]["chunks"]:
        raise ValueError("publication chunk records differ from manifest")
    inventory = _normalize_manifest_inventory(manifest.get("inventory"))
    seen = {}
    payload_bytes = 0
    with tempfile.TemporaryDirectory(prefix="publication-audit.") as directory:
        root = Path(directory)
        for index, chunk in enumerate(receipt["blobs"]["chunks"]):
            expected_key = expected_key_prefix + f"/archive-{index:03d}.tar.gz"
            if chunk["key"] != expected_key:
                raise ValueError("publication chunk key differs")
            archive = root / f"archive-{index:03d}.tar.gz"
            _fetch_blob(store, chunk, archive)
            for name, entry in _archive_inventory(archive).items():
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
    }


def publish_bundle(backend, kind, inventory):
    """Sustained-run resource-bundle wrapper around the publication module."""

    backend.guard()
    descriptor = dict(getattr(backend, "resource_blob_store_descriptor", WAYSTONE_DESCRIPTOR))
    store = getattr(backend, "resource_blob_store", None)
    if store is None:
        store = BlobStore(blob_adapter_from_descriptor(descriptor))
    tool_digest = getattr(backend, "resource_blob_tool_digest", None)
    if tool_digest is None:
        adapter = getattr(store, "_adapter", None)
        tool_digest = getattr(adapter, "tool_sha256", None)
    if tool_digest is None:
        tool_digest = waystone_tool_pins()
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
    if spec.mode != "archive":
        raise ValueError("publication archive mode required")
    if type(spec.release) is not bool:
        raise ValueError("publication release flag required")
    if type(spec.chunk_size_bytes) is not int or spec.chunk_size_bytes <= 0:
        raise ValueError("positive publication chunk size required")
    _key_prefix(spec)
    _normalize_tool_digest(spec.tool_digest)
    if not isinstance(spec.store_descriptor, Mapping):
        raise ValueError("publication store descriptor required")


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
                    data = Path(entry["path"]).read_bytes()
                    if len(data) != entry["bytes"]:
                        raise ValueError("staged publication member size changed")
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    info.mtime = 0
                    info.mode = 0o444
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    archive.addfile(info, io.BytesIO(data))


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
                data = stream.read()
                digest = _sha256_bytes(data)
                if member.size != len(data):
                    raise ValueError("publication archive member size differs")
                result[name] = {"sha256": digest, "bytes": len(data)}
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
        store.get(blob["key"], destination, blob["sha256"])
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
    if not isinstance(blobs, Mapping) or set(blobs) != {"manifest", "chunks"}:
        raise ValueError("publication blob records required")
    chunks = blobs["chunks"]
    if not isinstance(chunks, list) or not chunks:
        raise ValueError("publication chunks required")
    return {
        "schema_version": 1,
        "store_descriptor": dict(receipt["store_descriptor"]),
        "tool_sha256": _normalize_tool_digest(receipt["tool_sha256"]),
        "verified_by_readback": True,
        "blobs": {
            "manifest": _normalize_blob(blobs["manifest"]),
            "chunks": [_normalize_blob(chunk) for chunk in chunks],
        },
    }


def _normalize_blob(value):
    if not isinstance(value, Mapping) or set(value) != {"key", "sha256", "bytes"}:
        raise ValueError("publication blob record required")
    return {
        "key": validate_blob_key(value["key"]),
        "sha256": require_digest(value["sha256"]),
        "bytes": _require_nonnegative_int(value["bytes"], "publication blob byte count required"),
    }


def _normalize_tool_digest(value):
    if not isinstance(value, Mapping) or not value:
        raise ValueError("publication tool digest required")
    return {str(path): require_digest(digest) for path, digest in sorted(value.items())}


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
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def _write_json_idempotent(path: Path, value) -> None:
    data = json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    if path.exists():
        if path.read_text() != data:
            raise ValueError("publication receipt changed")
        return
    path.write_text(data)


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()
