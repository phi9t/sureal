import copy,hashlib,json,shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from evidence.source_snapshot import LocalSnapshotStore,archive_sources
from cohort.sustained_controller_backend import NativeBackend,sha
from cohort.sustained_controller_sources import REQUIRED as HOST_REQUIRED,freeze_host_sources
from cohort.sustained_sources import REQUIRED as PACKAGE_REQUIRED,SNAPSHOT_TARGET
class ControllerGuardTests(unittest.TestCase):
 def source_snapshot(self,root,names,store_root):
  archive,pins=archive_sources(root,names);digest=hashlib.sha256(archive).hexdigest();LocalSnapshotStore(store_root).store(digest,archive)
  return {'schema_version':1,'source_snapshot_sha256':digest,'source_snapshot_target':SNAPSHOT_TARGET,'source_snapshot_store':str(store_root),'source_pins':pins}
 def checkout(self,root,anchor_sha):
  for name in HOST_REQUIRED:
   path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('host '+name)
  (root/'research').mkdir(exist_ok=True)
  (root/'research/training-anchor-candidate-verified.json').write_text(json.dumps({'expected':{'candidate_sha256':anchor_sha}}))
 def backend(self,root,checkout=None):
  root.mkdir(parents=True,exist_ok=True)
  b=NativeBackend.__new__(NativeBackend);b.R=root;b.package=root/'code';b.package.mkdir();b.verifier=root/'verifier';b.verifier.mkdir();b.source=root/'input';b.source.mkdir();(b.source/'manifest.json').write_text('{}');b.manifest_sha=sha(b.source/'manifest.json');b.runtime={'rootfs_sha256':'1'*64,'image_id':'gpu'};b.metric_runtime={'rootfs_sha256':'2'*64,'image_id':'metrics'};b.runtime_path=root/'runtime.json';b.runtime_path.write_text(json.dumps(b.runtime));b.output=root/'payload';b.output.mkdir();b.host_pins={};b.old={'driver_hashes':{}};b.pins={}
  for name in PACKAGE_REQUIRED:
   p=b.package/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('original '+name)
  for name in ['audit_sustained_transition.py','sustained_chunk_reference.py']:
   p=b.package/'cohort'/name;p.parent.mkdir(exist_ok=True);p.write_text('original '+name);q=b.verifier/name;q.write_bytes(p.read_bytes());b.pins['cohort/'+name]=sha(p)
  b.pins=self.source_snapshot(b.package,sorted(str(p.relative_to(b.package)) for p in b.package.rglob('*.py')),root/'source-snapshots')
  (b.source/'anchor-templates.json').write_text('admitted anchors');b.anchor_sha=sha(b.source/'anchor-templates.json');b.verifier_pins={str(p):sha(p) for p in b.verifier.iterdir()}
  checkout=root/'checkout' if checkout is None else checkout
  self.checkout(checkout,b.anchor_sha);b.checkout_path=checkout;b.host_pins=freeze_host_sources(checkout,root/'host-source')
  return b
 def guard(self,b):
  with patch('cohort.sustained_controller_backend.P',b.checkout_path),patch('cohort.sustained_controller_backend.unique_payload_bytes',return_value=0):b.guard()
 def test_current_checkout_edit_and_path_change_do_not_invalidate_snapshot_guard(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);checkout_a=root/'checkout-a';b=self.backend(root/'run',checkout_a)
   with patch('cohort.sustained_controller_backend.P',checkout_a),patch('cohort.sustained_controller_backend.unique_payload_bytes',return_value=0):
    b.guard();(checkout_a/'cohort/unrelated.py').write_text('new checkout helper\n');b.guard()
   checkout_b=root/'checkout-b';shutil.copytree(checkout_a,checkout_b)
   with patch('cohort.sustained_controller_backend.P',checkout_b),patch('cohort.sustained_controller_backend.unique_payload_bytes',return_value=0):b.guard()
 def test_altered_or_missing_source_snapshot_invalidates_guard(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);b=self.backend(root/'run',root/'checkout')
   snapshot=Path(b.pins['source_snapshot_store'])/b.pins['source_snapshot_sha256']
   with patch('cohort.sustained_controller_backend.P',root/'checkout'),patch('cohort.sustained_controller_backend.unique_payload_bytes',return_value=0):b.guard()
   snapshot.write_bytes(b'not the admitted snapshot')
   with patch('cohort.sustained_controller_backend.P',root/'checkout'),patch('cohort.sustained_controller_backend.unique_payload_bytes',return_value=0),self.assertRaises(ValueError):b.guard()
   snapshot.unlink()
   with patch('cohort.sustained_controller_backend.P',root/'checkout'),patch('cohort.sustained_controller_backend.unique_payload_bytes',return_value=0),self.assertRaises(FileNotFoundError):b.guard()
 def test_changed_decoder_anchors_refused_before_stage_or_resume(self):
  with tempfile.TemporaryDirectory() as temp:
   b=self.backend(Path(temp));self.guard(b);(b.source/'anchor-templates.json').write_text('different decoder')
   with self.assertRaises(ValueError):self.guard(b)
 def test_verifier_copy_matches_frozen_source(self):
  with tempfile.TemporaryDirectory() as temp:self.guard(self.backend(Path(temp)))
 def test_resume_cannot_rebaseline_a_tampered_verifier(self):
  with tempfile.TemporaryDirectory() as temp:
   b=self.backend(Path(temp));p=b.verifier/'sustained_chunk_reference.py';p.write_text('changed independent math');b.verifier_pins[str(p)]=sha(p)
   with self.assertRaises(ValueError):self.guard(b)
 def test_foreign_stage_runtime_worker_and_code_mount_refused(self):
  with tempfile.TemporaryDirectory() as temp:
   b=self.backend(Path(temp));inputs=b.R/'train-1000-input';inputs.mkdir();manifest=inputs/'manifest.json';manifest.write_text('{}');artifact=b.output/'live.log';artifact.write_text('fixture');receipt={'stage':'train-1000','requested_stage':'train-1000','exit_code':0,'manifest_sha256':b.manifest_sha,'source_hashes':b.pins,'runtime_lock':b.runtime,'driver_hashes':{},'verifier_source_pins':{},'input_hashes':{str(manifest):sha(manifest)},'artifacts':{str(artifact):sha(artifact)},'output_directory':str(b.output),'command':['bwrap','--ro-bind',str(b.package),'/experiment','--ro-bind',str(inputs),'/source','--ro-bind',str(inputs),'/tmp/inputs','--bind',str(b.output),'/outputs','--ro-bind',str(b.R/'source-snapshots'),'/tmp/source-snapshots','--setenv','SUREAL_SOURCE_SNAPSHOT_STORE','/tmp/source-snapshots','--','/experiment/cohort/train_sustained.py']};b.check_stage(receipt)
   for fault in ['runtime','worker','mount','snapshot-store','empty-inputs','empty-artifacts']:
    bad=copy.deepcopy(receipt)
    if fault=='runtime':bad['runtime_lock']=b.metric_runtime
    elif fault=='worker':bad['command'][-1]='/experiment/unsafe.py'
    elif fault=='mount':bad['command'][bad['command'].index('/experiment')-1]=str(b.R/'foreign')
    elif fault=='snapshot-store':bad['command'][bad['command'].index('/tmp/source-snapshots')-1]=str(b.R/'foreign-snapshots')
    elif fault=='empty-inputs':bad['input_hashes']={}
    else:bad['artifacts']={}
    with self.assertRaises(ValueError):b.check_stage(bad)
if __name__=='__main__':unittest.main()
