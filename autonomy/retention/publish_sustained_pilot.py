"""Publish an admitted sustained pilot through the blob-store publication module."""

import argparse
import json
import uuid
from pathlib import Path

from blob_store.core import BlobStore, blob_adapter_from_descriptor, waystone_tool_pins
from resources.scientific_budget import reserve_write
from resources.scientific_payload import unique_payload_bytes
from retention.publication import (
    WAYSTONE_DESCRIPTOR,
    publish,
    release_plan as publication_release_plan,
    sustained_pilot_spec,
)
from retention.publication_sources import freeze_pilot_sources, validate_pilot_sources
from retention.publisher_runtime import admitted_host_sources
from retention.sustained_controller_lock import acquire_experiment_lock
from retention.sustained_pilot_inventory import freeze_pilot_inventory


P = Path(__file__).resolve().parents[1]
C = Path.home() / ".cache/waystone/waymo-perception"
W = C / "scientific-processing"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--receipt-sha256", required=True)
    parser.add_argument("--host-source-receipt", type=Path)
    parser.add_argument("--release", action="store_true")
    parser.add_argument("--lock-path", type=Path, default=C / "insula/architecture-experiments.lock")
    parser.add_argument("--cache-root", type=Path, default=C)
    parser.add_argument("--work-root", type=Path, default=W)
    parser.add_argument("--store-descriptor")
    parser.add_argument("--tool-digest")
    args = parser.parse_args()

    with acquire_experiment_lock(args.lock_path):
        receipt = publish_sustained_pilot(args)
    print("ADMITTED blob-store retention", receipt, "local release", args.release, flush=True)


def publish_sustained_pilot(args):
    if args.host_source_receipt is not None:
        admitted_host_sources(
            args.host_source_receipt,
            P,
            args.cache_root / "insula/pilot-publisher-host-source",
            freeze_pilot_sources,
            validate_pilot_sources,
        )
    final = json.loads(args.receipt.read_text())
    payload = Path(final["output_directory"])
    if payload.parent != args.work_root or not payload.name.startswith("balanced16-sustained-admission-"):
        raise ValueError("pilot-only scientific payload required")
    inventory = freeze_pilot_inventory(payload, args.receipt, args.receipt_sha256)
    descriptor = _store_descriptor(args.store_descriptor)
    store = BlobStore(blob_adapter_from_descriptor(descriptor))
    tool_digest = _tool_digest(args.tool_digest, store)
    run_id = payload.name
    publication_root = args.cache_root / "insula" / ("hdfs-retention-" + run_id + "-" + uuid.uuid4().hex)
    publication_root.mkdir(parents=True)
    spec = sustained_pilot_spec(
        payload=_publication_inventory(payload, inventory),
        run_id=run_id,
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
        _write_json(
            publication_root / "release-completed.json",
            {"publication_receipt_sha256": _sha256(receipt_path), "released": plan},
        )
    if unique_payload_bytes(args.work_root) > 15 * 1024**3:
        raise ValueError("scientific payload budget exceeded")
    return receipt_path


def _publication_inventory(payload: Path, frozen_inventory):
    return {
        name: {"path": str(payload / name), "sha256": digest, "bytes": (payload / name).stat().st_size}
        for name, digest in sorted(frozen_inventory["source_sha256"].items())
    }


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


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
