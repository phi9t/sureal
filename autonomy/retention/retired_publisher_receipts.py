"""Verify source-snapshot evidence in retired publication receipts."""

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Mapping

from evidence.source_snapshot import store_from_receipt, verify_or_materialize_receipt_sources


DEFAULT_RECEIPT_ROOTS = (
    Path.home() / ".cache/waystone/waymo-perception",
    Path(__file__).resolve().parents[1] / "research",
)

KIND_ORDER = (
    "native-cache-retention",
    "sustained-checkpoint-retention",
    "sustained-pilot-retention",
    "resource-retention",
)

FINAL_RECEIPT_SHAPES = {
    "native-cache-retention": {
        "cache_inventory_sha256",
        "host_source_pins",
        "publication_manifest_hdfs_uri",
        "chunks",
        "independent_admission",
    },
    "sustained-checkpoint-retention": {
        "checkpoint_inventory_sha256",
        "host_source_pins",
        "publication_manifest_hdfs_uri",
        "chunks",
        "independent_admission",
    },
    "sustained-pilot-retention": {
        "pilot_inventory_sha256",
        "host_source_pins",
        "publication_manifest_hdfs_uri",
        "chunks",
        "independent_admission",
    },
    "resource-retention": {
        "source_inventory_sha256",
        "resource_source_pins",
        "publication_manifest_hdfs_uri",
        "chunks",
        "independent_admission",
    },
}

SOURCE_SNAPSHOT_FIELDS = (
    "host_source_pins",
    "resource_source_pins",
    "checkpoint_publisher_source_pins",
    "source_snapshot_receipt",
    "source_receipt",
    "source_pins",
)

SOURCE_SNAPSHOT_RECEIPT_FIELDS = {
    "source_snapshot_sha256",
    "source_snapshot_store",
    "source_pins",
}

LEGACY_PIN_FIELDS = (
    "host_source_pins",
    "resource_source_pins",
    "source_pins",
)

NO_SOURCE_SNAPSHOT_REASON = "no embedded source snapshot receipt; only legacy digest pin maps were present"


def verify_roots(roots=DEFAULT_RECEIPT_ROOTS) -> dict:
    """Return per-kind verification counts for retired publisher receipts."""

    report = {
        "roots": [str(Path(root)) for root in roots],
        "kinds": {
            kind: {
                "found": 0,
                "verified": 0,
                "missing_source_pins": 0,
                "failed": 0,
                "receipts": [],
            }
            for kind in KIND_ORDER
        },
    }
    for path in _iter_json_paths(roots):
        loaded = _read_json(path)
        if loaded is None:
            continue
        data, receipt_sha256 = loaded
        kind = classify_retired_receipt(data)
        if kind is None:
            continue
        record = verify_receipt(path, data, kind, receipt_sha256)
        bucket = report["kinds"][kind]
        bucket["found"] += 1
        bucket[record["status"]] += 1
        bucket["receipts"].append(record)
    return report


def classify_retired_receipt(receipt) -> str | None:
    if not isinstance(receipt, Mapping):
        return None
    keys = set(receipt)
    for kind in KIND_ORDER:
        if FINAL_RECEIPT_SHAPES[kind] <= keys:
            return kind
    return None


def verify_receipt(path: Path, receipt: Mapping, kind: str, receipt_sha256: str | None = None) -> dict:
    record = {
        "path": str(path),
        "kind": kind,
        "receipt_sha256": receipt_sha256,
    }
    source_receipts = list(_embedded_source_snapshot_receipts(receipt))
    if not source_receipts:
        record.update(
            {
                "status": "missing_source_pins",
                "source_snapshot_fields": [],
                "verified_sources": 0,
                "reason": NO_SOURCE_SNAPSHOT_REASON if _has_legacy_pin_map(receipt) else "no embedded source snapshot receipt",
            }
        )
        return record

    verified = []
    try:
        for field, source_receipt in source_receipts:
            store = store_from_receipt(source_receipt)
            with tempfile.TemporaryDirectory(prefix="retired-receipt-sources.") as directory:
                result = verify_or_materialize_receipt_sources(
                    source_receipt,
                    Path(directory) / field,
                    store=store,
                )
            verified.append(
                {
                    "field": field,
                    "source_snapshot_sha256": result["source_snapshot_sha256"],
                    "source_snapshot_target": result["source_snapshot_target"],
                    "source_files": result["source_files"],
                }
            )
    except Exception as error:
        record.update(
            {
                "status": "failed",
                "source_snapshot_fields": [field for field, _ in source_receipts],
                "verified_sources": sum(item["source_files"] for item in verified),
                "reason": f"{type(error).__name__}: {error}",
            }
        )
        return record

    record.update(
        {
            "status": "verified",
            "source_snapshot_fields": [item["field"] for item in verified],
            "source_snapshot_sha256": [item["source_snapshot_sha256"] for item in verified],
            "source_snapshot_targets": [item["source_snapshot_target"] for item in verified],
            "verified_sources": sum(item["source_files"] for item in verified),
        }
    )
    return record


def _iter_json_paths(roots):
    for root in roots:
        root = Path(root)
        if root.is_file():
            if root.suffix == ".json":
                yield root
            continue
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.json")):
            if path.is_file():
                yield path


def _read_json(path: Path):
    try:
        data = path.read_bytes()
        return json.loads(data), hashlib.sha256(data).hexdigest()
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _embedded_source_snapshot_receipts(receipt: Mapping):
    for field in SOURCE_SNAPSHOT_FIELDS:
        value = receipt.get(field)
        if _is_source_snapshot_receipt(value):
            yield field, value


def _is_source_snapshot_receipt(value) -> bool:
    return isinstance(value, Mapping) and SOURCE_SNAPSHOT_RECEIPT_FIELDS <= set(value)


def _has_legacy_pin_map(receipt: Mapping) -> bool:
    return any(isinstance(receipt.get(field), Mapping) for field in LEGACY_PIN_FIELDS)


def _summary_lines(report: Mapping) -> list[str]:
    lines = ["kind found verified missing_source_pins failed"]
    for kind in KIND_ORDER:
        bucket = report["kinds"][kind]
        lines.append(
            f"{kind} {bucket['found']} {bucket['verified']} {bucket['missing_source_pins']} {bucket['failed']}"
        )
        for record in bucket["receipts"]:
            if record["status"] != "verified":
                lines.append(f"  {record['status']}: {record['path']}: {record['reason']}")
    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, action="append", help="receipt root or receipt JSON path")
    parser.add_argument("--json", action="store_true", help="write the full report as JSON")
    parser.add_argument("--fail-on-missing-source-pins", action="store_true")
    args = parser.parse_args(argv)
    report = verify_roots(args.root or DEFAULT_RECEIPT_ROOTS)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("\n".join(_summary_lines(report)))
    failures = sum(report["kinds"][kind]["failed"] for kind in KIND_ORDER)
    missing = sum(report["kinds"][kind]["missing_source_pins"] for kind in KIND_ORDER)
    if failures or (args.fail_on_missing_source_pins and missing):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
