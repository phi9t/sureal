import tempfile
import unittest
from pathlib import Path
from dataset import scientific_dataset_test as fixtures
from pipeline.semantic_archive_support import archive_semantic_support

class SemanticArchiveSupportTests(unittest.TestCase):
    def test_both_returns_unassigned_instance_and_undefined_coverage(self):
        for semantic,eligible in [(14,2),(0,0)]:
            with self.subTest(semantic=semantic),tempfile.TemporaryDirectory() as tmp:
                archive,pub,digest=fixtures.ScientificDatasetTests().fixture(Path(tmp),instance_id=-1,semantic_id=semantic)
                r=archive_semantic_support(archive,pub,expected_publication_sha256=digest,usage='engineering')
                self.assertEqual(r['native_counts'][semantic],2)
                self.assertEqual(r['eligible_point_elements'],eligible)
                self.assertEqual(r['annotated_returns'],2)
                self.assertEqual(r['independent_reference_records'],10)
    def test_missing_return_stays_unannotated_not_background(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive,pub,digest=fixtures.ScientificDatasetTests().fixture(Path(tmp),missing=True)
            r=archive_semantic_support(archive,pub,expected_publication_sha256=digest,usage='engineering')
            self.assertEqual(r['eligible_point_elements'],1)
            self.assertEqual(r['annotated_returns'],1)
            self.assertEqual(r['unannotated_returns'],9)
    def test_changed_source_and_illegal_membership_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive,pub,digest=fixtures.ScientificDatasetTests().fixture(Path(tmp))
            with self.assertRaises(ValueError):
                archive_semantic_support(archive,pub,expected_publication_sha256=digest,usage='train')
            archive.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                archive_semantic_support(archive,pub,expected_publication_sha256=digest,usage='engineering')
