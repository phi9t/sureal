import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evidence import tracker


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


if __name__ == "__main__":
    unittest.main()
