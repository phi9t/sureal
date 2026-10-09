"""Retain one independently admitted sustained checkpoint through the blob store."""

import argparse
import json
import os
import uuid
from pathlib import Path

from blob_store.core import BlobStore, blob_adapter_from_descriptor, waystone_tool_pins
from insula.runtime_identity import verify_rootfs
from resources.backend import resource_cpu_root_for
from resources.scientific_budget import reserve_write
from resources.scientific_payload import unique_payload_bytes
from retention.publication import (
    WAYSTONE_DESCRIPTOR,
    publish,
    release_plan as publication_release_plan,
    sustained_checkpoint_spec,
)
from retention.publisher_runtime import admitted_host_sources
from retention.sustained_checkpoint_inventory import freeze_checkpoint_inventory
from retention.checkpoint_retention_policy import checkpoint_case
from retention.checkpoint_retention_sources import freeze_host_sources, validate_host_sources


P = Path(__file__).resolve().parents[1]
C = Path.home() / ".cache/waystone/waymo-perception"
W = C / "scientific-processing"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--receipt-sha256", required=True)
    parser.add_argument("--host-source-receipt", type=Path)
    parser.add_argument("--release", action="store_true")
    parser.add_argument("--lock-fd", type=int)
    parser.add_argument("--lock-path", type=Path, default=C / "insula/architecture-experiments.lock")
    parser.add_argument("--cache-root", type=Path, default=C)
    parser.add_argument("--work-root", type=Path, default=W)
    parser.add_argument("--store-descriptor")
    parser.add_argument("--tool-digest")
    args = parser.parse_args()

    from retention.sustained_controller_lock import acquire_experiment_lock

    with acquire_experiment_lock(args.lock_path, args.lock_fd):
        receipt = publish_checkpoint(args)
    print("ADMITTED blob-store retention", receipt, "local release", args.release, flush=True)


def publish_checkpoint(args):
    if args.host_source_receipt is not None:
        admitted_host_sources(
            args.host_source_receipt,
            P,
            args.cache_root / "insula/checkpoint-publisher-host-source",
            freeze_host_sources,
            validate_host_sources,
        )
    final = json.loads(args.receipt.read_text())
    payload = Path(final["output_directory"])
    inventory = freeze_checkpoint_inventory(payload, args.receipt, args.receipt_sha256)
    case = checkpoint_case(args.work_root, payload, final["step"], requested_step=inventory["requested_step"])
    run_id = case + "-step" + str(final["step"])
    publication_root = args.cache_root / "insula" / ("hdfs-retention-" + run_id + "-" + uuid.uuid4().hex)
    publication_root.mkdir(parents=True)
    descriptor = _store_descriptor(args.store_descriptor)
    store = BlobStore(blob_adapter_from_descriptor(descriptor))
    tool_digest = _tool_digest(args.tool_digest, store)
    spec_inventory = _publication_inventory(payload, inventory)
    spec = sustained_checkpoint_spec(
        payload=spec_inventory,
        run_id=run_id,
        kind="checkpoint",
        release=args.release,
        store=store,
        store_descriptor=descriptor,
        tool_digest=tool_digest,
        staging_root=args.work_root / ("publication-stage-" + run_id),
        reserve=reserve_write,
    )
    plan = publication_release_plan(spec)
    receipt = publish(spec)
    receipt_path = publication_root / "verified-publication.json"
    _write_json(receipt_path, receipt)
    if args.release:
        release_path = publication_root / "release-completed.json"
        _write_json(
            release_path,
            {
                "publication_receipt_sha256": _sha256(receipt_path),
                "released": plan,
            },
        )
    if descriptor.get("kind") == "waystone":
        _verify_default_resource_root(args.cache_root)
    if unique_payload_bytes(args.work_root) > 15 * 1024**3:
        raise ValueError("scientific payload budget exceeded")
    return receipt_path


def _publication_inventory(payload: Path, frozen_inventory):
    result = {}
    for name, digest in sorted(frozen_inventory["source_sha256"].items()):
        path = payload / name
        result[name] = {"path": str(path), "sha256": digest, "bytes": path.stat().st_size}
    return result


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


def _verify_default_resource_root(cache_root: Path) -> None:
    root = resource_cpu_root_for(None,C) if cache_root == C else resource_cpu_root_for(None, cache_root)
    lock_path = Path(str(root) + ".lock.json")
    if lock_path.exists():
        runtime = json.loads(lock_path.read_text())
        verify_rootfs(root, runtime["rootfs_sha256"])


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
