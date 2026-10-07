import shutil,tempfile,unittest
from pathlib import Path
from evidence.source_snapshot import LocalSnapshotStore
from retention.retention_sources import REQUIRED,SNAPSHOT_TARGET,freeze_host_sources,validate_host_sources
class RetentionSourcesTests(unittest.TestCase):
 def fixture(self,root):
  for name in REQUIRED:
   p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(name)
 def query_runner(self,names):
  def run(command,**kwargs):
   self.assertIn('query',command)
   class Result:pass
   result=Result();result.stdout=''.join('//'+name.rsplit('/',1)[0]+':'+name.rsplit('/',1)[1]+'\n' for name in sorted(names));return result
  return run
 def test_repo_checkout_uses_executable_target_snapshot_and_rehydrates_empty_cache(self):
  with tempfile.TemporaryDirectory() as temp:
   base=Path(temp);repo=base/'repo';root=repo/'autonomy';self.fixture(root)
   names=['autonomy/'+name for name in REQUIRED]
   pins=freeze_host_sources(root,base/'frozen',store=LocalSnapshotStore(base/'store'),repo_root=repo,bazel=repo/'bazelw',runner=self.query_runner(names))
   self.assertEqual(pins['schema_version'],2)
   self.assertEqual(pins['source_snapshot_target'],SNAPSHOT_TARGET)
   self.assertIn('autonomy/retention/publish_native_cache.py',pins['source_pins'])
   shutil.rmtree(pins['source_snapshot_root'])
   validate_host_sources(root,pins)
   self.assertTrue((Path(pins['source_snapshot_root'])/'autonomy/retention/publish_native_cache.py').is_file())
 def test_snapshot_verifies_after_current_edit_extra_file_and_checkout_move(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)/'repo';self.fixture(root);pins=freeze_host_sources(root,Path(temp)/'frozen');validate_host_sources(root,pins);self.assertEqual(set(pins['source_pins']),set(REQUIRED))
   (root/REQUIRED[0]).write_text('changed current checkout')
   (root/'retention/unrelated.py').write_text('new helper')
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

if __name__ == '__main__':
 unittest.main()
