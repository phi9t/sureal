import json,tempfile,unittest
from pathlib import Path
from dataset.cohort_checkpoint import verify_checkpoint
from evidence.source_snapshot import file_sha256
class CohortCheckpointTests(unittest.TestCase):
 def fixture(self,root):
  code=root/'code';code.mkdir();worker=code/'worker.py';worker.write_text('pass\n');base=root/'scene';base.mkdir();receipt=base/'worker-receipt.json';lock={'rootfs_sha256':'locked'}
  sha=lambda p:file_sha256(p)
  receipt.write_text(json.dumps({'checks':[{'exit_code':0}],'candidate_hashes':{'worker.py':sha(worker)},'runtime_lock':lock,'artifacts':{}}))
  cp=base/'receipt.json';cp.write_text(json.dumps({'scene':'scene','manifest_sha256':'manifest','source_record_hashes':{'camera_image':'source'},'runtime_lock':lock,'checks':[{'exit_code':0}],'retained_evidence_hashes':{str(receipt):sha(receipt)}}));return cp,code,lock,sha(cp),receipt
 def test_current_nested_candidate_and_runtime_verified(self):
  with tempfile.TemporaryDirectory() as tmp:
   p,code,lock,h,_=self.fixture(Path(tmp));r=verify_checkpoint(p,expected_checkpoint_sha256=h,code_root=code,expected_runtime_lock=lock,expected_manifest_sha256='manifest',expected_source_hashes={'camera_image':'source'});self.assertEqual(r['scene'],'scene')
 def test_external_registry_required_and_historical_driver_preserved(self):
  from dataset.cohort_resume import verify_registered_checkpoint
  with tempfile.TemporaryDirectory() as tmp:
   p,code,lock,h,_=self.fixture(Path(tmp));registry=Path(tmp)/'trusted.json';registry.write_text(json.dumps({'scene':h}));rh=file_sha256(registry)
   kwargs=dict(code_root=code,expected_runtime_lock=lock,expected_manifest_sha256='manifest',expected_source_hashes={'camera_image':'source'})
   result=verify_registered_checkpoint(p,scene='scene',registry=registry,expected_registry_sha256=rh,**kwargs);self.assertEqual(result['scene'],'scene');self.assertEqual(file_sha256(p),h)
   for values in [(None,None),(registry,'changed')]:
    with self.assertRaises(ValueError):verify_registered_checkpoint(p,scene='scene',registry=values[0],expected_registry_sha256=values[1],**kwargs)
   registry.write_text('{}');rh=file_sha256(registry)
   with self.assertRaises(ValueError):verify_registered_checkpoint(p,scene='scene',registry=registry,expected_registry_sha256=rh,**kwargs)
 def test_changed_checkpoint_nested_worker_and_runtime_refused(self):
  for kind in ['checkpoint','worker','runtime','retained']:
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
    p,code,lock,h,receipt=self.fixture(Path(tmp))
    if kind=='checkpoint':p.write_text('{}')
    elif kind=='worker':(code/'worker.py').write_text('changed')
    elif kind=='runtime':lock={'rootfs_sha256':'changed'}
    else:receipt.write_text('{}')
    with self.assertRaises(ValueError):verify_checkpoint(p,expected_checkpoint_sha256=h,code_root=code,expected_runtime_lock=lock,expected_manifest_sha256='manifest',expected_source_hashes={'camera_image':'source'})
 def test_explicit_readonly_mount_path_remapping(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);p,code,lock,h,receipt=self.fixture(root);d=json.loads(p.read_text());d['retained_evidence_hashes']={'/historical/root/scene/worker-receipt.json':file_sha256(receipt)};p.write_text(json.dumps(d));h=file_sha256(p);r=verify_checkpoint(p,expected_checkpoint_sha256=h,code_root=code,expected_runtime_lock=lock,expected_manifest_sha256='manifest',expected_source_hashes={'camera_image':'source'},path_remap={'/historical/root':str(root)});self.assertEqual(r['worker_receipts'],1)
if __name__=='__main__':unittest.main()
