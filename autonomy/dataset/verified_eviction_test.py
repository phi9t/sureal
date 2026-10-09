import json
import tempfile
import unittest
from pathlib import Path

from dataset.verified_eviction import evict_points
from evidence.source_snapshot import file_sha256


class VerifiedEvictionTests(unittest.TestCase):
    def fixture(self, root):
        processing = root / "processing"
        points = processing / "points"
        points.mkdir(parents=True)
        publication = root / "publication"
        (publication / "packed").mkdir(parents=True)
        replay = root / "replay"
        replay.mkdir()
        payload = points / "scene-10-1-1.npz"
        payload.write_bytes(b"payload")
        archive = publication / "packed/scene.tar"
        archive.write_bytes(b"archive")
        report = points / "report.json"
        report.write_text(
            json.dumps(
                {
                    "scene": "scene",
                    "rows": [{"artifact": payload.name, "sha256": file_sha256(payload), "return_present": True}],
                }
            )
        )
        publication_record = {
            "scene": "scene",
            "archive_hdfs_uri": "hdfs://host/scene.tar",
            "archive": {"sha256": file_sha256(archive), "report_sha256": file_sha256(report)},
            "checks": [{"exit_code": 0}],
        }
        publication_receipt = publication / "receipt.json"
        publication_receipt.write_text(json.dumps(publication_record))
        replay_record = {
            "scene": "scene",
            "publication_receipt_sha256": file_sha256(publication_receipt),
            "checks": [{"exit_code": 0}, {"exit_code": 0}],
            "validation": {"records": 1},
        }
        replay_receipt = replay / "receipt.json"
        replay_receipt.write_text(json.dumps(replay_record))
        return (
            processing,
            publication,
            replay,
            file_sha256(publication_receipt),
            file_sha256(replay_receipt),
            payload,
            archive,
        )

    def blob_fixture(self, root):
        processing, publication, replay, _, _, payload, archive = self.fixture(root)
        publication_receipt = publication / "receipt.json"
        publication_record = json.loads(publication_receipt.read_text())
        publication_record.pop("archive_hdfs_uri")
        archive_blob = {
            "key": "datasets/scene-records-v1/scene/scientific/archive.tar",
            "sha256": file_sha256(archive),
            "bytes": archive.stat().st_size,
            "verified_by_readback": True,
        }
        publication_record["archive_blob"] = archive_blob
        publication_record["store_descriptor"] = {"kind": "waystone", "project": "sureal"}
        publication_record["checks"] = [
            {"stage": "pack-live", "exit_code": 0},
            dict({"stage": "archive-blob-put"}, **self.blob_check_fields(archive_blob)),
            dict({"stage": "archive-blob-fetch"}, **self.blob_check_fields(archive_blob)),
            {"stage": "independent-archive-live", "exit_code": 0},
            dict(
                {"stage": "manifest-blob-put-last"},
                **self.blob_check_fields(
                    {
                        "key": "datasets/scene-records-v1/scene/scientific/publication.json",
                        "sha256": "a" * 64,
                        "bytes": 100,
                    }
                ),
            ),
            dict(
                {"stage": "manifest-blob-fetch"},
                **self.blob_check_fields(
                    {
                        "key": "datasets/scene-records-v1/scene/scientific/publication.json",
                        "sha256": "a" * 64,
                        "bytes": 100,
                    }
                ),
            ),
        ]
        publication_receipt.write_text(json.dumps(publication_record))
        replay_receipt = replay / "receipt.json"
        replay_record = json.loads(replay_receipt.read_text())
        replay_record["publication_receipt_sha256"] = file_sha256(publication_receipt)
        replay_receipt.write_text(json.dumps(replay_record))
        return (
            processing,
            publication,
            replay,
            file_sha256(publication_receipt),
            file_sha256(replay_receipt),
            payload,
            archive,
        )

    def blob_check_fields(self, blob):
        return {
            "blob_key": blob["key"],
            "sha256": blob["sha256"],
            "bytes": blob["bytes"],
            "verified_by_readback": True,
        }

    def test_verified_payloads_evicted_and_recovery_manifest_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            processing, publication, replay, publication_sha, replay_sha, payload, archive = self.fixture(Path(tmp))
            result = evict_points(
                processing,
                publication,
                replay,
                expected_publication_sha256=publication_sha,
                expected_replay_sha256=replay_sha,
            )
            self.assertFalse(payload.exists())
            self.assertFalse(archive.exists())
            self.assertTrue((processing / "points/report.json").exists())
            self.assertEqual(result["bytes_evicted"], 14)
            self.assertEqual(result["archive_hdfs_uri"], "hdfs://host/scene.tar")
            self.assertTrue((processing / "point-eviction.json").exists())

    def test_blob_publication_receipt_preserves_blob_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            processing, publication, replay, publication_sha, replay_sha, _, _ = self.blob_fixture(Path(tmp))
            result = evict_points(
                processing,
                publication,
                replay,
                expected_publication_sha256=publication_sha,
                expected_replay_sha256=replay_sha,
            )
            self.assertEqual(result["archive_blob"]["key"], "datasets/scene-records-v1/scene/scientific/archive.tar")
            self.assertNotIn("archive_hdfs_uri", result)

    def test_blob_archive_identity_mismatch_refuses_before_any_deletion(self):
        with tempfile.TemporaryDirectory() as tmp:
            processing, publication, replay, _, _, payload, archive = self.blob_fixture(Path(tmp))
            publication_receipt = publication / "receipt.json"
            publication_record = json.loads(publication_receipt.read_text())
            publication_record["archive_blob"]["bytes"] += 1
            publication_receipt.write_text(json.dumps(publication_record))
            replay_receipt = replay / "receipt.json"
            replay_record = json.loads(replay_receipt.read_text())
            replay_record["publication_receipt_sha256"] = file_sha256(publication_receipt)
            replay_receipt.write_text(json.dumps(replay_record))

            with self.assertRaises(ValueError):
                evict_points(
                    processing,
                    publication,
                    replay,
                    expected_publication_sha256=file_sha256(publication_receipt),
                    expected_replay_sha256=file_sha256(replay_receipt),
                )
            self.assertTrue(payload.exists())
            self.assertTrue(archive.exists())
            self.assertFalse((processing / "point-eviction.json").exists())

    def test_changed_payload_archive_or_receipt_refused_before_any_deletion(self):
        for mutation in ("payload", "archive", "receipt"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                processing, publication, replay, publication_sha, replay_sha, payload, archive = self.fixture(Path(tmp))
                if mutation == "payload":
                    payload.write_bytes(b"changed")
                elif mutation == "archive":
                    archive.write_bytes(b"changed")
                else:
                    (replay / "receipt.json").write_text("{}")
                with self.assertRaises(ValueError):
                    evict_points(
                        processing,
                        publication,
                        replay,
                        expected_publication_sha256=publication_sha,
                        expected_replay_sha256=replay_sha,
                    )
                self.assertTrue(payload.exists())
                self.assertTrue(archive.exists())
                self.assertFalse((processing / "point-eviction.json").exists())


if __name__ == "__main__":
    unittest.main()
