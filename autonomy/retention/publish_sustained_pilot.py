"""Publish an admitted sustained pilot through the blob-store publication module."""

import argparse
import json
import uuid
from pathlib import Path

from blob_store.core import BlobStore, blob_adapter_from_descriptor
from resources.scientific_budget import reserve_write
from resources.scientific_payload import unique_payload_bytes
from retention.publication import (
    publish,
    publication_store_descriptor,
    release_plan as publication_release_plan,
    store_tool_digest_from_json,
    sustained_pilot_spec,
    write_publication_json,
    write_release_completed,
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
    descriptor = publication_store_descriptor(args.store_descriptor)
    store = BlobStore(blob_adapter_from_descriptor(descriptor))
    tool_digest = store_tool_digest_from_json(args.tool_digest, store)
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
    write_publication_json(receipt_path, receipt)
    if args.release:
        write_release_completed(publication_root / "release-completed.json", receipt_path, plan)
    if unique_payload_bytes(args.work_root) > 15 * 1024**3:
        raise ValueError("scientific payload budget exceeded")
    return receipt_path


def _publication_inventory(payload: Path, frozen_inventory):
    return {
        name: {"path": str(payload / name), "sha256": digest, "bytes": (payload / name).stat().st_size}
        for name, digest in sorted(frozen_inventory["source_sha256"].items())
    }


if __name__ == "__main__":
    main()
