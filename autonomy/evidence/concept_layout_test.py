import tempfile
import unittest
from pathlib import Path


class EvidenceConceptLayoutTests(unittest.TestCase):
    def test_evidence_scope_modules_are_importable_from_the_concept_package(self):
        import importlib

        for module in (
            "evidence.journal",
            "evidence.pins",
            "evidence.projection",
            "evidence.publish",
            "evidence.source_integrity",
            "evidence.source_snapshot",
            "evidence.tracker",
        ):
            with self.subTest(module=module):
                self.assertIsNotNone(importlib.import_module(module))

    def test_moved_digest_helpers_reject_symlinked_evidence(self):
        from evidence.journal import digest
        from evidence.source_snapshot import file_sha256

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proof = root / "proof.json"
            proof.write_text('{"passed": true}\n')
            link = root / "proof-link.json"
            link.symlink_to(proof)

            self.assertEqual(digest(proof), file_sha256(proof))
            with self.assertRaisesRegex(ValueError, "regular non-symlinked file required"):
                digest(link)


if __name__ == "__main__":
    unittest.main()
