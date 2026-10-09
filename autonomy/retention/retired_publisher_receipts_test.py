import json
import shutil
import tempfile
import unittest
from pathlib import Path

from evidence.source_snapshot import LocalSnapshotStore, source_snapshot_receipt


def _write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data)


def _source_receipt(root: Path, store_root: Path):
    _write(root / "publisher.py", "admitted source\n")
    receipt = source_snapshot_receipt(
        root,
        ["publisher.py"],
        LocalSnapshotStore(store_root),
        target="//autonomy/retention:legacy-publisher",
    )
    _write(root / "publisher.py", "changed working tree\n")
    return receipt


def _native_cache_receipt(source_binding):
    return {
        "closure_complete": True,
        "source_admission_complete": True,
        "host_source_pins": source_binding,
        "source_sha256": {},
        "parent_receipts": [],
        "cache_inventory_sha256": "a" * 64,
        "manifest_readback_exact": True,
        "source_pins": {},
        "runtime_lock": {},
        "waystone_tool_sha256": {},
        "chunks": [],
        "independent_admission": {},
        "publication_manifest_hdfs_uri": (
            "hdfs://harunava/user/tiger/waystone/sureal/runs/perception-native-cache/run/"
            "publication-manifest.json"
        ),
        "publication_manifest_sha256": "b" * 64,
    }


def _resource_receipt(source_binding):
    return {
        "schema_version": 1,
        "kind": "checkpoint",
        "hdfs_prefix": "hdfs://harunava/user/tiger/waystone/sureal/runs/perception-resource-closures/run",
        "source_inventory": {},
        "source_inventory_sha256": "c" * 64,
        "resource_identity_sha256": "d" * 64,
        "native_manifest_sha256": "e" * 64,
        "resource_source_pins": source_binding,
        "resource_source_directory": "/retired/source",
        "execution_directory": "/retired/execution",
        "runtime_lock": {},
        "rootfs_path": "/retired/rootfs",
        "audit_runtime_namespace": {},
        "waystone_tool_sha256": {},
        "archive_library": {},
        "chunks": [],
        "independent_admission": {},
        "manifest_readback_exact": True,
        "publication_manifest_hdfs_uri": (
            "hdfs://harunava/user/tiger/waystone/sureal/runs/perception-resource-closures/run/"
            "publication-manifest.json"
        ),
        "publication_manifest_sha256": "f" * 64,
    }


class RetiredPublisherReceiptTests(unittest.TestCase):
    def test_embedded_source_snapshot_receipt_verifies_without_working_tree(self):
        from retention.retired_publisher_receipts import verify_roots

        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "working-tree"
            snapshot = _source_receipt(source, base / "snapshot-store")
            receipt_path = base / "insula" / "hdfs-retention-run" / "verified-publication.json"
            _write(receipt_path, json.dumps(_native_cache_receipt(snapshot)))
            shutil.rmtree(source)

            report = verify_roots([base])

            native = report["kinds"]["native-cache-retention"]
            self.assertEqual(native["found"], 1)
            self.assertEqual(native["verified"], 1)
            self.assertEqual(native["missing_source_pins"], 0)
            self.assertEqual(native["failed"], 0)
            self.assertEqual(native["receipts"][0]["source_snapshot_fields"], ["host_source_pins"])
            self.assertEqual(native["receipts"][0]["verified_sources"], 1)

    def test_plain_legacy_pin_maps_are_reported_missing_not_verified(self):
        from retention.retired_publisher_receipts import verify_roots

        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            receipt_path = base / "insula" / "resource-retention-run" / "verified-publication.json"
            _write(receipt_path, json.dumps(_resource_receipt({"retention.py": "0" * 64})))

            report = verify_roots([base])

            resource = report["kinds"]["resource-retention"]
            self.assertEqual(resource["found"], 1)
            self.assertEqual(resource["verified"], 0)
            self.assertEqual(resource["missing_source_pins"], 1)
            self.assertEqual(resource["failed"], 0)
            self.assertEqual(
                resource["receipts"][0]["reason"],
                "no embedded source snapshot receipt; only legacy digest pin maps were present",
            )

    def test_discovers_each_retired_final_receipt_kind_by_shape(self):
        from retention.retired_publisher_receipts import verify_roots

        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "source"
            snapshot = _source_receipt(source, base / "store")
            fixtures = {
                "native-cache-retention": _native_cache_receipt(snapshot),
                "sustained-checkpoint-retention": dict(
                    _native_cache_receipt(snapshot),
                    checkpoint_inventory_sha256="1" * 64,
                ),
                "sustained-pilot-retention": dict(_native_cache_receipt(snapshot), pilot_inventory_sha256="2" * 64),
                "resource-retention": _resource_receipt(snapshot),
            }
            fixtures["sustained-checkpoint-retention"].pop("cache_inventory_sha256")
            fixtures["sustained-pilot-retention"].pop("cache_inventory_sha256")
            for kind, receipt in fixtures.items():
                _write(base / kind / "verified-publication.json", json.dumps(receipt))
            _write(
                base / "native-cache-retention" / "admission-input" / "publication.json",
                json.dumps({key: value for key, value in fixtures["native-cache-retention"].items() if key != "independent_admission"}),
            )

            report = verify_roots([base])

            for kind in fixtures:
                with self.subTest(kind=kind):
                    self.assertEqual(report["kinds"][kind]["found"], 1)
                    self.assertEqual(report["kinds"][kind]["verified"], 1)


if __name__ == "__main__":
    unittest.main()
