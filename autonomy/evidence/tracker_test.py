import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evidence import tracker
from evidence.journal import append_entry


class TrackerEvidenceTests(unittest.TestCase):
    def test_optional_metadata_digest_matches_the_parsed_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "result.json"
            original = b'{"version": 1}'
            source.write_bytes(original)
            read_bytes = Path.read_bytes

            def replace_after_read(path):
                data = read_bytes(path)
                if path == source:
                    path.write_bytes(b'{"version": 2}')
                return data

            with patch.object(Path, "read_bytes", replace_after_read):
                value, digest = tracker.read_optional(source)

            self.assertEqual(value, json.loads(original))
            self.assertEqual(digest, hashlib.sha256(original).hexdigest())

    def test_snapshot_address_matches_the_captured_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "result.json"
            original = b'{"version": 1}'
            source.write_bytes(original)
            read_bytes = Path.read_bytes

            def replace_after_read(path):
                data = read_bytes(path)
                if path == source:
                    path.write_bytes(b'{"version": 2}')
                return data

            with (
                patch.object(Path, "read_bytes", replace_after_read),
                patch.object(tracker, "R", root),
            ):
                destination = tracker.snapshot(source)

            self.assertEqual(destination.name, hashlib.sha256(original).hexdigest())
            self.assertEqual(destination.read_bytes(), original)

    def test_verify_journal_reads_active_and_legacy_publication_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            journal = root / "research-journal.jsonl"
            append_entry(journal, "observation", ["journal"], "Journal verifier fixture.", [])
            active = root / "research-journal-hdfs-verified.json"
            legacy = root / "research-journal-hdfs-legacy-verified.json"
            active.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "store_descriptor": {"kind": "local", "root": "store"},
                        "tool_sha256": {"waystone-cli": "1" * 64},
                        "verified_by_readback": True,
                        "blobs": {
                            "manifest": {
                                "key": "runs/perception-research-journal/r/snapshot/manifest.json",
                                "sha256": "2" * 64,
                                "bytes": 10,
                            },
                            "files": [
                                {
                                    "key": "runs/perception-research-journal/r/snapshot/research-journal.jsonl",
                                    "sha256": "3" * 64,
                                    "bytes": 20,
                                }
                            ],
                        },
                    }
                )
            )
            legacy.write_text(
                json.dumps(
                    {
                        "all_results_uploaded_and_readback_exact": True,
                        "hdfs_prefix": "hdfs://fixture/runs/perception-research-journal/snapshot-old",
                        "files": {
                            "research-journal.jsonl": {
                                "hdfs_uri": "hdfs://fixture/runs/perception-research-journal/snapshot-old/research-journal.jsonl",
                                "sha256": "4" * 64,
                                "bytes": 30,
                            }
                        },
                    }
                )
            )

            with patch.object(tracker, "R", root), patch.object(tracker, "JOURNAL", journal):
                report = tracker.verify_journal()

            self.assertEqual(report["journal_entries"], 1)
            self.assertEqual(
                report["publication_records"],
                [
                    "research-journal-hdfs-legacy-verified.json",
                    "research-journal-hdfs-verified.json",
                ],
            )


if __name__ == "__main__":
    unittest.main()
