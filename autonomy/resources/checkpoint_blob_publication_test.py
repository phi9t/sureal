import hashlib
import json
import tempfile
import tarfile
import unittest
from pathlib import Path

from blob_store.core import BlobStore, InMemoryBlobAdapter


TOOL_DIGEST = {
    "waystone": "a" * 64,
}
STORE_DESCRIPTOR = {
    "kind": "in-memory",
    "project": "unit",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class CheckpointBlobPublicationTests(unittest.TestCase):
    def write_archive(self, root, inventory):
        archive = root / "archive-000.tar.gz"
        with tarfile.open(archive, "w:gz") as output:
            for name, entry in sorted(inventory.items()):
                output.add(entry["path"], arcname=name)
        return archive

    def test_checkpoint_reader_accepts_new_blob_publication_shape(self):
        from resources.checkpoint import recover_publication_record, validate_publication_record, write_publication_record

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "payload"
            source.mkdir()
            names = [
                "identity.json",
                "checkpoint.json",
                "native-final.json",
                "producer-report.json",
                "native-manifest.json",
            ]
            inventory = {}
            for name in names:
                path = source / name
                path.write_text(name)
                inventory[name] = {"path": str(path), "sha256": sha(path), "bytes": path.stat().st_size}

            store = BlobStore(InMemoryBlobAdapter(), backoff_seconds=())
            archive = self.write_archive(root, inventory)
            chunk = store.put(
                "runs/perception-resource-closures/balanced16-sustained-baseline-run1/checkpoint/archive-000.tar.gz",
                archive,
            )
            manifest = {
                "schema_version": 1,
                "area": "runs",
                "child": "perception-resource-closures",
                "run_id": "balanced16-sustained-baseline-run1",
                "kind": "checkpoint",
                "mode": "archive",
                "inventory": {
                    name: {"sha256": item["sha256"], "bytes": item["bytes"]}
                    for name, item in inventory.items()
                },
                "chunks": [chunk],
            }
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, sort_keys=True))
            manifest_blob = store.put(
                "runs/perception-resource-closures/balanced16-sustained-baseline-run1/checkpoint/manifest.json",
                manifest_path,
            )
            receipt_value = {
                "schema_version": 1,
                "store_descriptor": STORE_DESCRIPTOR,
                "tool_sha256": TOOL_DIGEST,
                "verified_by_readback": True,
                "blobs": {"manifest": manifest_blob, "chunks": [chunk]},
            }
            receipt_path = root / "verified-publication.json"
            receipt_path.write_text(json.dumps(receipt_value, sort_keys=True))

            backend = type("Backend", (), {})()
            backend.resource_blob_store = store
            backend.resource_root = root / "resource-layer"
            backend.resource_root.mkdir()
            backend.resource_identity_sha256 = inventory["identity.json"]["sha256"]
            backend.manifest_sha = inventory["native-manifest.json"]["sha256"]
            case_root = root / "case"
            case_root.mkdir()
            final = case_root / "final.json"
            final.write_text("final")
            companion = case_root / "companion.json"
            companion.write_text("companion")
            report = case_root / "report.json"
            report.write_text("report")
            record = {
                "root": str(case_root),
                "target_step": 1000,
                "final_path": str(final),
                "final_sha256": inventory["native-final.json"]["sha256"],
                "resource_companion_path": str(companion),
                "resource_companion_sha256": inventory["checkpoint.json"]["sha256"],
                "report_sha256": inventory["producer-report.json"]["sha256"],
            }
            receipt = {
                "path": str(receipt_path),
                "sha256": sha(receipt_path),
                "manifest_key": receipt_value["blobs"]["manifest"]["key"],
                "kind": "checkpoint",
            }

            identity = write_publication_record(backend, record, receipt, inventory)
            self.assertEqual(identity["manifest_key"], receipt["manifest_key"])
            record.pop("resource_publication")
            self.assertEqual(recover_publication_record(backend, record, inventory)["manifest_key"], receipt["manifest_key"])
            self.assertEqual(validate_publication_record(backend, record)["manifest_key"], receipt["manifest_key"])


if __name__ == "__main__":
    unittest.main()
