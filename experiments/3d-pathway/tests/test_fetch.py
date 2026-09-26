from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))


class FetchPromotionContractTest(unittest.TestCase):
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
