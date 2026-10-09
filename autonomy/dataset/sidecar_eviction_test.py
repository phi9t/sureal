import json
import tempfile
import unittest
from pathlib import Path

from dataset.sidecar_eviction import evict_sidecars
from evidence.source_snapshot import file_sha256 as sha


class SidecarEvictionTests(unittest.TestCase):
    def fixture(self, root):
        processing = root / "processing"
        sidecars = processing / "sidecars/lidar_pose"
        sidecars.mkdir(parents=True)
        payload = sidecars / "row.npz"
        payload.write_bytes(b"payload")
        publication = root / "publication"
        (publication / "packed").mkdir(parents=True)
        (publication / "input").mkdir()
        archive = publication / "packed/sidecars.tar"
        archive.write_bytes(b"archive")
        trusted = {
            "files": {"lidar_pose/row.npz": sha(payload)},
            "provenance": {"scene": "scene", "scene_receipt_sha256": "abc", "source_receipt_hashes": {}},
        }
        trusted_path = publication / "input/trusted.json"
        trusted_path.write_text(json.dumps(trusted))
        manifest = publication / "packed/publication.json"
        manifest.write_text("{}")
        receipt_data = {
            "scene": "scene",
            "archive_hdfs_uri": "hdfs://host/archive.tar",
            "archive": {"sha256": sha(archive)},
            "scene_receipt_sha256": "abc",
            "component_receipt_hashes": {},
            "publication_manifest_sha256": sha(manifest),
            "validation": {"files": 1, "provenance": trusted["provenance"]},
            "checks": [
                {"stage": stage, "exit_code": 0}
                for stage in [
                    "pack-live",
                    "hdfs-put",
                    "hdfs-download",
                    "independent-bundle-live",
                    "manifest-put-last",
                    "manifest-download",
                ]
            ],
            "artifacts": {"input/trusted.json": sha(trusted_path), "packed/publication.json": sha(manifest)},
        }
        receipt = publication / "receipt.json"
        receipt.write_text(json.dumps(receipt_data))
        return processing, publication, payload, archive, sha(receipt)

    def blob_fixture(self, root):
        processing, publication, payload, archive, _ = self.fixture(root)
        receipt = publication / "receipt.json"
        record = json.loads(receipt.read_text())
        record.pop("archive_hdfs_uri")
        archive_blob = {
            "key": "datasets/component-bundles-v1/scene/scientific/archive.tar",
            "sha256": sha(archive),
            "bytes": archive.stat().st_size,
            "verified_by_readback": True,
        }
        record["archive_blob"] = archive_blob
        record["store_descriptor"] = {"kind": "waystone", "project": "sureal"}
        record["checks"] = [
            {"stage": "pack-live", "exit_code": 0},
            dict({"stage": "archive-blob-put"}, **self.blob_check_fields(archive_blob)),
            dict({"stage": "archive-blob-fetch"}, **self.blob_check_fields(archive_blob)),
            {"stage": "independent-bundle-live", "exit_code": 0},
            dict({"stage": "manifest-blob-put-last"}, **self.blob_check_fields(archive_blob)),
            dict({"stage": "manifest-blob-fetch"}, **self.blob_check_fields(archive_blob)),
        ]
        receipt.write_text(json.dumps(record))
        return processing, publication, payload, archive, sha(receipt)

    def blob_check_fields(self, blob):
        return {
            "blob_key": blob["key"],
            "sha256": blob["sha256"],
            "bytes": blob["bytes"],
            "verified_by_readback": True,
        }

    def test_verified_eviction_preserves_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            processing, publication, payload, archive, digest = self.fixture(Path(directory))
            result = evict_sidecars(processing, publication, expected_publication_sha256=digest)
            self.assertFalse(payload.exists())
            self.assertFalse(archive.exists())
            self.assertEqual(result["bytes_evicted"], 14)
            self.assertTrue((processing / "sidecar-eviction.json").exists())
            self.assertTrue((publication / "receipt.json").exists())

    def test_blob_publication_receipt_preserves_blob_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            processing, publication, _, _, digest = self.blob_fixture(Path(directory))
            result = evict_sidecars(processing, publication, expected_publication_sha256=digest)
            self.assertEqual(result["archive_blob"]["key"], "datasets/component-bundles-v1/scene/scientific/archive.tar")
            self.assertNotIn("archive_hdfs_uri", result)

    def test_blob_archive_identity_mismatch_refuses_before_any_deletion(self):
        with tempfile.TemporaryDirectory() as directory:
            processing, publication, payload, archive, _ = self.blob_fixture(Path(directory))
            receipt = publication / "receipt.json"
            record = json.loads(receipt.read_text())
            record["archive_blob"]["sha256"] = "0" * 64
            receipt.write_text(json.dumps(record))
            digest = sha(receipt)
            with self.assertRaises(ValueError):
                evict_sidecars(processing, publication, expected_publication_sha256=digest)
            self.assertTrue(payload.exists())
            self.assertTrue(archive.exists())
            self.assertFalse((processing / "sidecar-eviction.json").exists())

    def test_mutations_refuse_before_any_deletion(self):
        for kind in ["payload", "archive", "receipt", "extra", "symlink"]:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                processing, publication, payload, archive, digest = self.fixture(Path(directory))
                if kind == "payload":
                    payload.write_bytes(b"bad")
                elif kind == "archive":
                    archive.write_bytes(b"bad")
                elif kind == "receipt":
                    (publication / "receipt.json").write_text("{}")
                elif kind == "extra":
                    (payload.parent / "extra").write_bytes(b"extra")
                else:
                    payload.unlink()
                    payload.symlink_to(archive)
                with self.assertRaises(ValueError):
                    evict_sidecars(processing, publication, expected_publication_sha256=digest)
                self.assertTrue(payload.exists())
                self.assertTrue(archive.exists())
                self.assertFalse((processing / "sidecar-eviction.json").exists())


if __name__ == "__main__":
    unittest.main()
