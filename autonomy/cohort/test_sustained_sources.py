import hashlib,tempfile,unittest
from pathlib import Path
from cohort.sustained_sources import validate_sources,REQUIRED

class SustainedSourceTests(unittest.TestCase):
 def fixture(self,root):
  for name in REQUIRED:
   p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('# frozen source\n')
  hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*.py')}
  lock={'rootfs_sha256':'a'*64,'image_id':'sha256:'+'b'*64};return hashes,lock
 def test_empty_missing_extra_and_changed_sources_refused(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);hashes,lock=self.fixture(root);validate_sources(root,hashes,lock,lock)
   for bad in [{},{k:v for k,v in hashes.items() if k!='tier1/catalog.py'},{**hashes,'outside.py':'a'*64}]:
    with self.assertRaises(ValueError):validate_sources(root,bad,lock,lock)
   (root/'tier1/catalog.py').write_text('# changed recipe\n')
   with self.assertRaises(ValueError):validate_sources(root,hashes,lock,lock)
 def test_new_helper_must_be_in_frozen_inventory(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);hashes,lock=self.fixture(root);(root/'cohort/new_helper.py').write_text('# new\n')
   with self.assertRaises(ValueError):validate_sources(root,hashes,lock,lock)
 def test_runtime_admission_cannot_be_recorded_without_matching(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);hashes,lock=self.fixture(root)
   for bad in [{},{**lock,'rootfs_sha256':'c'*64}]:
    with self.assertRaises(ValueError):validate_sources(root,hashes,bad,lock)

if __name__=='__main__':unittest.main()
