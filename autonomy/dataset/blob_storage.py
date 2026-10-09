"""Dataset blob-store keys and receipt helpers."""

from collections.abc import Mapping
from pathlib import Path

from blob_store.core import (
    BlobStore,
    blob_adapter_from_descriptor,
    blob_key_from_uri,
    validate_blob_key,
)


DEFAULT_STORE_DESCRIPTOR = {"kind": "waystone", "project": "sureal"}
RAW_DATASET_CHILD = "waymo-perception-v2.0.1"
SCENE_ARCHIVE_CHILD = "scene-records-v1"
SIDECAR_BUNDLE_CHILD = "component-bundles-v1"


def default_store_descriptor():
    return dict(DEFAULT_STORE_DESCRIPTOR)


def default_blob_store():
    return BlobStore(blob_adapter_from_descriptor(default_store_descriptor()))


def dataset_blob_key(child, run_id, kind, name):
    return validate_blob_key("/".join(("datasets", str(child), str(run_id), str(kind), str(name))))


def source_blob_key(official_split, component, scene):
    return dataset_blob_key(
        RAW_DATASET_CHILD,
        scene,
        "raw-" + str(official_split) + "-" + str(component),
        "source.parquet",
    )


def scene_archive_blob_key(scene):
    return dataset_blob_key(SCENE_ARCHIVE_CHILD, scene, "scientific", "archive.tar")


def scene_manifest_blob_key(scene):
    return dataset_blob_key(SCENE_ARCHIVE_CHILD, scene, "scientific", "publication.json")


def sidecar_archive_blob_key(scene, *, compressed=False):
    name = "archive.tar.gz" if compressed else "archive.tar"
    return dataset_blob_key(SIDECAR_BUNDLE_CHILD, scene, _sidecar_kind(compressed), name)


def sidecar_manifest_blob_key(scene, *, compressed=False):
    return dataset_blob_key(SIDECAR_BUNDLE_CHILD, scene, _sidecar_kind(compressed), "publication.json")


def publication_archive_reference(publication):
    if not isinstance(publication, Mapping):
        raise ValueError("publication receipt required")
    blob = publication.get("archive_blob")
    if isinstance(blob, Mapping):
        return _validated_blob_receipt(blob)
    uri = publication.get("archive_hdfs_uri")
    if not isinstance(uri, str) or not uri.startswith("hdfs://"):
        raise ValueError("publication recovery source required")
    return uri


def put_blob(blob_store, key, source):
    return _blob_receipt(blob_store.put(key, Path(source)))


def fetch_record_blob(record, destination, *, blob_store=None):
    blob = record_blob(record)
    store = blob_store if blob_store is not None else _blob_store_for_record(record)
    store.get(blob["key"], destination, blob["sha256"])
    return blob


def record_blob(record):
    if not isinstance(record, Mapping):
        raise ValueError("source record required")
    blob = record.get("blob")
    if isinstance(blob, Mapping):
        return _validated_blob_receipt(blob)
    uri = record.get("hdfs_uri")
    if not isinstance(uri, str) or not uri.startswith("hdfs://"):
        raise ValueError("source blob reference required")
    descriptor = record_store_descriptor(record)
    return {
        "key": blob_key_from_uri(uri, descriptor),
        "sha256": _record_sha256(record),
        "bytes": _record_size(record),
    }


def record_store_descriptor(record):
    descriptor = record.get("store_descriptor") if isinstance(record, Mapping) else None
    if descriptor is None:
        return default_store_descriptor()
    if not isinstance(descriptor, Mapping):
        raise ValueError("store descriptor required")
    return dict(descriptor)


def blob_transfer_check(stage, blob):
    receipt = _validated_blob_receipt(blob)
    return {
        "stage": stage,
        "blob_key": receipt["key"],
        "sha256": receipt["sha256"],
        "bytes": receipt["bytes"],
        "verified_by_readback": receipt["verified_by_readback"],
        "exit_code": 0,
    }


def _blob_store_for_record(record):
    return BlobStore(blob_adapter_from_descriptor(record_store_descriptor(record)))


def _sidecar_kind(compressed):
    return "scientific-compressed" if compressed else "scientific"


def _blob_receipt(blob):
    receipt = _validated_blob_receipt(blob)
    receipt["verified_by_readback"] = True
    return receipt


def _validated_blob_receipt(blob):
    try:
        key = validate_blob_key(blob["key"])
        sha256 = _require_sha256(blob["sha256"])
        byte_count = blob["bytes"]
    except KeyError as error:
        raise ValueError("blob receipt required") from error
    if type(byte_count) is not int or byte_count < 0:
        raise ValueError("blob byte count required")
    result = {"key": key, "sha256": sha256, "bytes": byte_count}
    if "verified_by_readback" in blob:
        if blob["verified_by_readback"] is not True:
            raise ValueError("blob readback verification required")
        result["verified_by_readback"] = True
    return result


def _record_sha256(record):
    return _require_sha256(record.get("sha256"))


def _record_size(record):
    size = record.get("source_metadata", {}).get("size")
    if type(size) not in (str, int) or not str(size).isdigit() or int(size) <= 0:
        raise ValueError("source object size required")
    return int(size)


def _require_sha256(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("sha256 digest required")
    return value
