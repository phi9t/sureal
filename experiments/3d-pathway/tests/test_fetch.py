from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))


class FetchPromotionContractTest(unittest.TestCase):
    def test_locked_zip_extraction_is_safe_atomic_and_manifested(self) -> None:
        from fetch import extract_locked_asset

        asset = {
            "id": "zip-sample",
            "extraction": {"mode": "zip", "roots": ["one", "two"]},
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "sample.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("one/a.txt", "a")
                bundle.writestr("two/b.txt", "b")
            extracted = extract_locked_asset(asset, archive, root / "assets")
            self.assertEqual((extracted / "one/a.txt").read_text(), "a")
            self.assertEqual((extracted / "two/b.txt").read_text(), "b")
            manifest = json.loads(
                (root / "assets/zip-sample.extraction.json").read_text()
            )
            self.assertEqual(manifest["roots"], ["one", "two"])

            unsafe = root / "unsafe.zip"
            with zipfile.ZipFile(unsafe, "w") as bundle:
                bundle.writestr("../escape", "bad")
            with self.assertRaisesRegex(ValueError, "unsafe archive member"):
                extract_locked_asset(
                    {"id": "unsafe", "extraction": {"mode": "zip", "roots": ["one"]}},
                    unsafe,
                    root / "unsafe-assets",
                )
            self.assertFalse((root / "escape").exists())

    def test_hash_mismatch_stays_quarantined_and_correct_hash_promotes(self) -> None:
        from fetch import promote_candidate

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "asset.candidate"
            target = root / "asset.archive"
            candidate.write_bytes(b"canonical sample")
            actual = hashlib.sha256(candidate.read_bytes()).hexdigest()

            with self.assertRaisesRegex(ValueError, actual):
                promote_candidate(candidate, target, "0" * 64, "sample")
            self.assertTrue(candidate.is_file())
            self.assertFalse(target.exists())

            promote_candidate(candidate, target, actual, "sample")
            self.assertFalse(candidate.exists())
            self.assertEqual(target.read_bytes(), b"canonical sample")


if __name__ == "__main__":
    unittest.main()
