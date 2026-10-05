import hashlib,tempfile,unittest
from pathlib import Path
from evidence.source_snapshot import LocalSnapshotStore,archive_sources
from cohort.sustained_sources import REQUIRED,SNAPSHOT_TARGET,validate_sources

class SustainedSourceTests(unittest.TestCase):
 def fixture(self,root,store_root,names=None):
  names=sorted(REQUIRED) if names is None else names
  for name in names:
   p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(name+'\n')
  archive,pins=archive_sources(root,names)
  digest=hashlib.sha256(archive).hexdigest();LocalSnapshotStore(store_root).store(digest,archive)
  receipt={'schema_version':1,'source_snapshot_sha256':digest,'source_snapshot_target':SNAPSHOT_TARGET,'source_snapshot_store':str(store_root),'source_pins':pins}
  lock={'rootfs_sha256':'a'*64,'image_id':'sha256:'+'b'*64};return receipt,lock
 def test_snapshot_verification_accepts_moved_checkout_and_ignores_unrelated_sources(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)/'checkout-a';store=Path(tmp)/'snapshots';receipt,lock=self.fixture(root,store)
   self.assertEqual(validate_sources(root,receipt,lock,lock)['source_files'],len(REQUIRED))
   (root/'cohort/new_unrelated_helper.py').write_text('not in the admitted snapshot\n')
   self.assertEqual(validate_sources(root,receipt,lock,lock)['source_snapshot_sha256'],receipt['source_snapshot_sha256'])
   moved=Path(tmp)/'checkout-b'
   for name in receipt['source_pins']:
    destination=moved/name;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes((root/name).read_bytes())
   self.assertEqual(validate_sources(moved,receipt,lock,lock)['source_pins'],receipt['source_pins'])
 def test_snapshot_without_required_sustained_file_refused(self):
  with tempfile.TemporaryDirectory() as tmp:
   names=sorted(name for name in REQUIRED if name!='cohort/train_sustained.py')
   root=Path(tmp)/'repo';store=Path(tmp)/'snapshots';receipt,lock=self.fixture(root,store,names)
   with self.assertRaises(ValueError):validate_sources(root,receipt,lock,lock)
 def test_altered_or_missing_snapshot_refused(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)/'repo';store=Path(tmp)/'snapshots';receipt,lock=self.fixture(root,store)
   snapshot=store/receipt['source_snapshot_sha256'];snapshot.write_bytes(b'altered snapshot')
   with self.assertRaises(ValueError):validate_sources(root,receipt,lock,lock)
   snapshot.unlink()
   with self.assertRaises(FileNotFoundError):validate_sources(root,receipt,lock,lock)
 def test_changed_frozen_package_source_refused(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)/'repo';store=Path(tmp)/'snapshots';receipt,lock=self.fixture(root,store)
   (root/'cohort/train_sustained.py').write_text('tampered execution package\n')
   with self.assertRaises(ValueError):validate_sources(root,receipt,lock,lock)
 def test_runtime_admission_cannot_be_recorded_without_matching(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)/'repo';store=Path(tmp)/'snapshots';receipt,lock=self.fixture(root,store)
   for bad in [{},{**lock,'rootfs_sha256':'c'*64}]:
    with self.assertRaises(ValueError):validate_sources(root,receipt,bad,lock)

if __name__=='__main__':unittest.main()
