"""Publish the admitted native input cache through the blob-store publication module."""

import argparse
import json
import uuid
from pathlib import Path

from blob_store.core import BlobStore, blob_adapter_from_descriptor
from resources.scientific_budget import reserve_write
from resources.scientific_payload import unique_payload_bytes
from retention.cache_inventory import freeze_cache_inventory
from retention.publication import (
    native_cache_spec,
    publish,
    publication_store_descriptor,
    release_plan as publication_release_plan,
    store_tool_digest_from_json,
    write_publication_json,
    write_release_completed,
)
from retention.publication_sources import freeze_native_cache_sources, validate_native_cache_sources
from retention.publisher_runtime import admitted_host_sources
from retention.sustained_controller_lock import acquire_experiment_lock


P = Path(__file__).resolve().parents[1]
C = Path.home() / ".cache/waystone/waymo-perception"
W = C / "scientific-processing"
CASE = "overfit-native-cache-v1"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host-source-receipt", type=Path)
    parser.add_argument("--release", action="store_true")
    parser.add_argument("--lock-path", type=Path, default=C / "insula/architecture-experiments.lock")
    parser.add_argument("--cache-root", type=Path, default=C)
    parser.add_argument("--work-root", type=Path, default=W)
    parser.add_argument("--store-descriptor")
    parser.add_argument("--tool-digest")
    args = parser.parse_args()

    with acquire_experiment_lock(args.lock_path):
        receipt = publish_native_cache(args)
    print("ADMITTED blob-store retention", receipt, "local release", args.release, flush=True)


def publish_native_cache(args):
    if args.host_source_receipt is not None:
        admitted_host_sources(
            args.host_source_receipt,
            P,
            args.cache_root / "insula/native-cache-publisher-host-source",
            freeze_native_cache_sources,
            validate_native_cache_sources,
        )
    payload = args.work_root / CASE
    admissions = sorted(P.joinpath("research").glob("overfit-native-cache-*-verified.json"))
    admissions = [
        path
        for path in admissions
        if _admission_receipt_in_payload(path, payload)
    ]
    if len(admissions) != 16:
        raise ValueError("complete native-cache admissions required")
    inventory = freeze_cache_inventory(payload, admissions)
    descriptor = publication_store_descriptor(args.store_descriptor)
    store = BlobStore(blob_adapter_from_descriptor(descriptor))
    tool_digest = store_tool_digest_from_json(args.tool_digest, store)
    run_id = CASE
    publication_root = args.cache_root / "insula" / ("hdfs-retention-" + run_id + "-" + uuid.uuid4().hex)
    publication_root.mkdir(parents=True)
    spec = native_cache_spec(
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


def _admission_receipt_in_payload(path: Path, payload: Path) -> bool:
    try:
        record = json.loads(path.read_text())
        receipt = Path(record["receipt"])
        return "receipt" in record and receipt.is_relative_to(payload)
    except (KeyError, OSError, TypeError, json.JSONDecodeError, ValueError):
        return False


def _publication_inventory(payload: Path, frozen_inventory):
    return {
        name: {"path": str(payload / name), "sha256": digest, "bytes": (payload / name).stat().st_size}
        for name, digest in sorted(frozen_inventory["source_sha256"].items())
    }


if __name__ == "__main__":
    main()
