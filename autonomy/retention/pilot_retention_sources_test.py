import copy,shutil,tempfile,unittest
from pathlib import Path
from evidence.source_snapshot import LocalSnapshotStore,copy_source_snapshot,file_sha256
from retention.pilot_retention_sources import REQUIRED,SNAPSHOT_TARGET,freeze_host_sources,validate_host_sources
HISTORICAL_REQUIRED=(
 'retention/publish_sustained_pilot.py','retention/sustained_pilot_inventory.py',
 'retention/pilot_retention_audit.py','retention/pilot_retention_sources.py',
 'resources/scientific_budget.py','resources/scientific_payload.py',
 'resources/resource_archive.py','resources/resource_archive_cli.py',
 'resources/resource_rehydrate.py','resources/resource_release_plan.py',
 'evidence/source_snapshot.py','insula/entry.py','insula/runtime_identity.py',
)
HISTORICAL_TARGET='//autonomy:sustained-pilot-retention-host'
class PilotRetentionSourcesTests(unittest.TestCase):
 def fixture(self,root,names=REQUIRED):
  for name in names:
   p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(name)
 def historical_receipt(self,base):
  root=base/'legacy';self.fixture(root,HISTORICAL_REQUIRED)
  receipt=copy_source_snapshot(root,HISTORICAL_REQUIRED,base/'legacy-host',LocalSnapshotStore(base/'legacy-store'),target=HISTORICAL_TARGET)
  return root,receipt
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
   self.assertIn('autonomy/retention/publish_sustained_pilot.py',pins['source_pins'])
   shutil.rmtree(pins['source_snapshot_root'])
   validate_host_sources(root,pins)
   self.assertTrue((Path(pins['source_snapshot_root'])/'autonomy/retention/publish_sustained_pilot.py').is_file())
 def test_snapshot_verifies_after_current_edit_extra_file_and_checkout_move(self):
  with tempfile.TemporaryDirectory() as temp:
   base=Path(temp);root,pins=self.historical_receipt(base);validate_host_sources(root,pins);self.assertEqual(set(pins['source_pins']),set(HISTORICAL_REQUIRED))
   (root/HISTORICAL_REQUIRED[0]).write_text('changed current checkout')
   (root/'retention/unrelated.py').write_text('new helper')
   validate_host_sources(root,pins)
   moved=base/'moved';self.fixture(moved,HISTORICAL_REQUIRED);validate_host_sources(moved,pins)
 def test_missing_or_altered_snapshot_refused(self):
  with tempfile.TemporaryDirectory() as temp:
   root,pins=self.historical_receipt(Path(temp))
   snapshot=Path(pins['source_snapshot_store'])/pins['source_snapshot_sha256'];snapshot.write_bytes(b'altered snapshot')
   with self.assertRaises(ValueError):validate_host_sources(root,pins)
   snapshot.unlink()
   with self.assertRaises(FileNotFoundError):validate_host_sources(root,pins)
 def test_changed_materialized_snapshot_source_refused(self):
  with tempfile.TemporaryDirectory() as temp:
   root,pins=self.historical_receipt(Path(temp))
   (Path(pins['source_snapshot_root'])/HISTORICAL_REQUIRED[0]).write_text('changed frozen source')
   with self.assertRaises(ValueError):validate_host_sources(root,pins)
 def test_historical_schema1_receipt_omits_publisher_runtime_and_rehydrates_unchanged(self):
  with tempfile.TemporaryDirectory() as temp:
   root,pins=self.historical_receipt(Path(temp));before=copy.deepcopy(pins)
   archive=Path(pins['source_snapshot_store'])/pins['source_snapshot_sha256'];archive_before=file_sha256(archive)
   shutil.rmtree(pins['source_snapshot_root'])
   result=validate_host_sources(root,pins)
   self.assertEqual(result['source_files'],len(HISTORICAL_REQUIRED))
   self.assertNotIn('retention/publisher_runtime.py',pins['source_pins'])
   self.assertTrue((Path(pins['source_snapshot_root'])/'retention/publish_sustained_pilot.py').is_file())
   self.assertEqual(pins,before);self.assertEqual(file_sha256(archive),archive_before)
 def test_malformed_historical_schema1_receipt_still_refused(self):
  with tempfile.TemporaryDirectory() as temp:
   root,pins=self.historical_receipt(Path(temp));bad=copy.deepcopy(pins);bad['source_pins'].pop(HISTORICAL_REQUIRED[0])
   with self.assertRaises(ValueError):validate_host_sources(root,bad)
 def test_new_creation_without_target_context_is_refused(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)/'repo';self.fixture(root)
   with self.assertRaises(ValueError):freeze_host_sources(root,Path(temp)/'frozen')
 def test_missing_or_symlinked_source_refused(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)/'repo';self.fixture(root);p=root/REQUIRED[0];p.unlink()
   with self.assertRaises(ValueError):freeze_host_sources(root,Path(temp)/'missing')
   p.symlink_to(root/REQUIRED[1])
   with self.assertRaises(ValueError):freeze_host_sources(root,Path(temp)/'symlinked')

if __name__ == '__main__':
 unittest.main()
