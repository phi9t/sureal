import tempfile,unittest
from pathlib import Path
from cohort.retention_sources import REQUIRED,freeze_host_sources,validate_host_sources
class RetentionSourcesTests(unittest.TestCase):
 def fixture(self,root):
  for name in REQUIRED:
   p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(name)
 def test_snapshot_verifies_after_current_edit_extra_file_and_checkout_move(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)/'repo';self.fixture(root);pins=freeze_host_sources(root,Path(temp)/'frozen');validate_host_sources(root,pins);self.assertEqual(set(pins['source_pins']),set(REQUIRED))
   (root/REQUIRED[0]).write_text('changed current checkout')
   (root/'cohort/unrelated.py').write_text('new helper')
   validate_host_sources(root,pins)
   moved=Path(temp)/'moved';self.fixture(moved);validate_host_sources(moved,pins)
 def test_missing_or_altered_snapshot_refused(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)/'repo';self.fixture(root);pins=freeze_host_sources(root,Path(temp)/'frozen')
   snapshot=Path(pins['source_snapshot_store'])/pins['source_snapshot_sha256'];snapshot.write_bytes(b'altered snapshot')
   with self.assertRaises(ValueError):validate_host_sources(root,pins)
   snapshot.unlink()
   with self.assertRaises(FileNotFoundError):validate_host_sources(root,pins)
 def test_changed_materialized_snapshot_source_refused(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)/'repo';self.fixture(root);pins=freeze_host_sources(root,Path(temp)/'frozen')
   (Path(pins['source_snapshot_root'])/REQUIRED[0]).write_text('changed frozen source')
   with self.assertRaises(ValueError):validate_host_sources(root,pins)
 def test_missing_or_symlinked_source_refused(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)/'repo';self.fixture(root);p=root/REQUIRED[0];p.unlink()
   with self.assertRaises(ValueError):freeze_host_sources(root,Path(temp)/'missing')
   p.symlink_to(root/REQUIRED[1])
   with self.assertRaises(ValueError):freeze_host_sources(root,Path(temp)/'symlinked')
