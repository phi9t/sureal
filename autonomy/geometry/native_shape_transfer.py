"""Fetch one native shape source through the blob store."""
import argparse
import json
from pathlib import Path

from blob_store.core import (
    BlobStore,
    BlobStoreError,
    Corrupt,
    Missing,
    blob_adapter_from_descriptor,
    blob_key_from_uri,
    default_waystone_descriptor,
    validate_blob_key,
)


def _key_for_source(source, blob_adapter, store_descriptor):
    source = str(source)
    if not source.startswith("hdfs://"):
        return validate_blob_key(source)
    return blob_key_from_uri(source, blob_adapter if blob_adapter is not None else store_descriptor)


def fetch_blob(source, destination, expected_sha256, *, expected_bytes=None, blob_store=None, blob_adapter=None, store_descriptor=None):
    descriptor = store_descriptor or default_waystone_descriptor()
    adapter = blob_adapter
    if blob_store is None and adapter is None:
        adapter = blob_adapter_from_descriptor(descriptor)
    key = _key_for_source(source, adapter, descriptor)
    if blob_store is None:
        blob_store = BlobStore(adapter)
    try:
        blob_store.get(key, destination, expected_sha256, expected_bytes=expected_bytes)
    except (Corrupt, Missing) as error:
        raise ValueError("native shape blob fetch failed") from error
    except BlobStoreError:
        raise
    path = Path(destination)
    return {"blob_key": key, "sha256": expected_sha256, "bytes": path.stat().st_size}


def _parse_source_destination(args):
    if args.destination is None:
        return args.operation_or_source, args.source_or_destination
    if args.operation_or_source != "get":
        raise ValueError("only blob get is supported")
    return args.source_or_destination, args.destination


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--expected-bytes", type=int)
    parser.add_argument("--store-descriptor-json")
    parser.add_argument("--timeout-seconds", type=float, default=None, help=argparse.SUPPRESS)
    parser.add_argument("operation_or_source")
    parser.add_argument("source_or_destination")
    parser.add_argument("destination", nargs="?")
    args = parser.parse_args()
    source, destination = _parse_source_destination(args)
    descriptor = json.loads(args.store_descriptor_json) if args.store_descriptor_json else default_waystone_descriptor()
    fetch_blob(source, destination, args.expected_sha256, expected_bytes=args.expected_bytes, store_descriptor=descriptor)


if __name__ == "__main__":
    main()
