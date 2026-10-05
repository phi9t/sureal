import copy,json,shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cohort.sustained_controller_backend import NativeBackend,sha
class ControllerGuardTests(unittest.TestCase):
 def backend(self,root):
  b=NativeBackend.__new__(NativeBackend);b.R=root;b.package=root/'code';b.package.mkdir();b.verifier=root/'verifier';b.verifier.mkdir();b.source=root/'input';b.source.mkdir();(b.source/'manifest.json').write_text('{}');b.manifest_sha=sha(b.source/'manifest.json');b.runtime={'rootfs_sha256':'1'*64,'image_id':'gpu'};b.metric_runtime={'rootfs_sha256':'2'*64,'image_id':'metrics'};b.runtime_path=root/'runtime.json';b.runtime_path.write_text(json.dumps(b.runtime));b.output=root/'payload';b.output.mkdir();b.host_pins={};b.old={'driver_hashes':{}};b.pins={}
  for name in ['audit_sustained_transition.py','sustained_chunk_reference.py']:
   p=b.package/'cohort'/name;p.parent.mkdir(exist_ok=True);p.write_text('original '+name);q=b.verifier/name;q.write_bytes(p.read_bytes());b.pins['cohort/'+name]=sha(p)
  (b.source/'anchor-templates.json').write_text('admitted anchors');b.anchor_sha=sha(b.source/'anchor-templates.json');b.verifier_pins={str(p):sha(p) for p in b.verifier.iterdir()};return b
 def guard(self,b):
  research=b.R/'research';research.mkdir(exist_ok=True);(research/'training-anchor-candidate-verified.json').write_text(json.dumps({'expected':{'candidate_sha256':b.anchor_sha}}))
  with patch('cohort.sustained_controller_backend.P',b.R),patch('cohort.sustained_controller_backend.validate_host_sources'),patch('cohort.sustained_controller_backend.validate_sources'),patch('cohort.sustained_controller_backend.unique_payload_bytes',return_value=0):b.guard()
 def test_current_worker_edit_invalidates_resume(self):
  from cohort.sustained_sources import REQUIRED
  with tempfile.TemporaryDirectory() as temp:
   b=self.backend(Path(temp))
   for name in REQUIRED:
    path=b.package/name;path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():path.write_text('pinned worker')
   b.pins={str(p.relative_to(b.package)):sha(p) for p in b.package.rglob('*.py')};current=b.R/'current';shutil.copytree(b.package,current);(current/'research').mkdir();(current/'research/training-anchor-candidate-verified.json').write_text(json.dumps({'expected':{'candidate_sha256':b.anchor_sha}}))
   with patch('cohort.sustained_controller_backend.P',current),patch('cohort.sustained_controller_backend.validate_host_sources'),patch('cohort.sustained_controller_backend.unique_payload_bytes',return_value=0):
    b.guard();(current/'cohort/train_sustained.py').write_text('changed worker')
    with self.assertRaises(ValueError):b.guard()
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
   b=self.backend(Path(temp));inputs=b.R/'train-1000-input';inputs.mkdir();manifest=inputs/'manifest.json';manifest.write_text('{}');artifact=b.output/'live.log';artifact.write_text('fixture');receipt={'stage':'train-1000','requested_stage':'train-1000','exit_code':0,'manifest_sha256':b.manifest_sha,'source_hashes':b.pins,'runtime_lock':b.runtime,'driver_hashes':{},'verifier_source_pins':{},'input_hashes':{str(manifest):sha(manifest)},'artifacts':{str(artifact):sha(artifact)},'output_directory':str(b.output),'command':['bwrap','--ro-bind',str(b.package),'/experiment','--ro-bind',str(inputs),'/source','--ro-bind',str(inputs),'/tmp/inputs','--bind',str(b.output),'/outputs','--','/experiment/cohort/train_sustained.py']};b.check_stage(receipt)
   for fault in ['runtime','worker','mount','empty-inputs','empty-artifacts']:
    bad=copy.deepcopy(receipt)
    if fault=='runtime':bad['runtime_lock']=b.metric_runtime
    elif fault=='worker':bad['command'][-1]='/experiment/unsafe.py'
    elif fault=='mount':bad['command'][bad['command'].index('/experiment')-1]=str(b.R/'foreign')
    elif fault=='empty-inputs':bad['input_hashes']={}
    else:bad['artifacts']={}
    with self.assertRaises(ValueError):b.check_stage(bad)
if __name__=='__main__':unittest.main()
