"""Publish the research journal through the blob-store publication module."""

import argparse
import json
from pathlib import Path

from blob_store.core import BlobStore, blob_adapter_from_descriptor, waystone_tool_pins
from resources.scientific_budget import reserve_write
from retention.publication import WAYSTONE_DESCRIPTOR, publish_research_journal


P = Path(__file__).resolve().parents[1]
C = Path.home() / ".cache/waystone/waymo-perception"
W = C / "scientific-processing"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--research-root", type=Path, default=P / "research")
    parser.add_argument("--run-id")
    parser.add_argument("--store-descriptor")
    parser.add_argument("--tool-digest")
    parser.add_argument("--staging-root", type=Path)
    parser.add_argument("--receipt", type=Path, default=P / "research/research-journal-hdfs-verified.json")
    parser.add_argument("--legacy-receipt", type=Path)
    args = parser.parse_args(argv)

    descriptor = _store_descriptor(args.store_descriptor)
    store = BlobStore(blob_adapter_from_descriptor(descriptor))
    receipt = publish_research_journal(
        research_root=args.research_root,
        run_id=args.run_id,
        store=store,
        store_descriptor=descriptor,
        tool_digest=_tool_digest(args.tool_digest, store),
        staging_root=args.staging_root,
        receipt_path=args.receipt,
        legacy_receipt_path=args.legacy_receipt,
        reserve=reserve_write,
    )
    print("ADMITTED research journal blob-store publication", args.receipt, receipt["blobs"]["manifest"]["key"], flush=True)


def _store_descriptor(value):
    if value is None:
        return dict(WAYSTONE_DESCRIPTOR)
    descriptor = json.loads(value)
    if not isinstance(descriptor, dict):
        raise ValueError("store descriptor object required")
    return descriptor


def _tool_digest(value, store):
    if value is not None:
        digest = json.loads(value)
        if not isinstance(digest, dict):
            raise ValueError("tool digest object required")
        return digest
    adapter = getattr(store, "_adapter", None)
    digest = getattr(adapter, "tool_sha256", None)
    if digest is not None:
        return digest
    return waystone_tool_pins()


if __name__ == "__main__":
    main()
