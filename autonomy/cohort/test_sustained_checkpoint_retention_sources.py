import tempfile,unittest
from pathlib import Path
from cohort.checkpoint_retention_sources import REQUIRED,freeze_host_sources,validate_host_sources
class CheckpointRetentionSourcesTests(unittest.TestCase):
 def fixture(self,root):
  for name in REQUIRED:
   p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(name)
 def test_complete_frozen_sources(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)/'repo';self.fixture(root);pins=freeze_host_sources(root,Path(temp)/'frozen');validate_host_sources(root,pins);self.assertEqual(set(pins),set(REQUIRED))
 def test_missing_binding_or_modified_original_or_snapshot_refused(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)/'repo';self.fixture(root);pins=freeze_host_sources(root,Path(temp)/'frozen')
   incomplete=dict(pins);incomplete.pop(REQUIRED[0])
   with self.assertRaises(ValueError):validate_host_sources(root,incomplete)
   original=root/REQUIRED[0];original.write_text('changed')
   with self.assertRaises(ValueError):validate_host_sources(root,pins)
   original.write_text(REQUIRED[0]);Path(pins[REQUIRED[0]]['snapshot']).write_text('changed')
   with self.assertRaises(ValueError):validate_host_sources(root,pins)
 def test_missing_or_symlinked_source_refused(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)/'repo';self.fixture(root);p=root/REQUIRED[0];p.unlink()
   with self.assertRaises(ValueError):freeze_host_sources(root,Path(temp)/'missing')
   p.symlink_to(root/REQUIRED[1])
   with self.assertRaises(ValueError):freeze_host_sources(root,Path(temp)/'symlinked')
