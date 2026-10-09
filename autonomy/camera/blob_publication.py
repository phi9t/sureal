"""Blob-store helpers for scientific camera publication."""
from blob_store.core import BlobStore, blob_adapter_from_descriptor, blob_store_descriptor, validate_blob_key

DEFAULT_STORE_DESCRIPTOR = {"kind": "waystone", "project": "sureal"}


def camera_blob_key(scene, kind, name):
    return validate_blob_key("runs/scientific-camera/" + str(scene) + "/" + str(kind) + "/" + str(name))


def publication_blob_store(descriptor=None):
    adapter = blob_adapter_from_descriptor(descriptor or DEFAULT_STORE_DESCRIPTOR)
    return BlobStore(adapter), blob_store_descriptor(adapter)


def put_and_fetch_blob(store, key, source, destination):
    result = store.put(key, source)
    store.get(result["key"], destination, result["sha256"])
    return dict(result, verified_by_readback=True)
