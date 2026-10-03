import hashlib,json,tempfile,unittest
from pathlib import Path
from cohort.sustained_checkpoint_inventory import freeze_checkpoint_inventory
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
class CheckpointInventoryTests(unittest.TestCase):
 def fixture(self,base,step=1000,reason='sample',requested=None):
  manifest=base/'manifest.json';manifest.write_text('{}')
  root=base/'checkpoint';root.mkdir();(root/'heads').mkdir();(root/'checkpoint.pt').write_bytes(b'checkpoint');(root/'live.log').write_text('producer')
  heads={}
  for i in range(16):
   p=root/'heads'/f'heads-{i:02d}.npz';p.write_bytes(bytes([i]));heads[p.name]=sha(p)
  report={'manifest_sha256':sha(manifest),'updates':step,'requested_updates':step if requested is None else requested,'stop_reason':reason,'resource_gate_passed':True,'checkpoint_sha256':sha(root/'checkpoint.pt'),'head_hashes':heads}
  (root/'check.json').write_text(json.dumps(report));manifest=base/'manifest.json';manifest.write_text('{}');refs={}
  for name in ['train','audit','literal-loss','export','proposals','score','metrics-audit']:
   artifact=root/'check.json' if name=='train' else base/(name+'.log')
   if name!='train':artifact.write_text(name)
   artifacts={str(p):sha(p) for p in root.rglob('*') if p.is_file()} if name=='train' else {str(artifact):sha(artifact)}
   p=base/(name+'.json');p.write_text(json.dumps({'stage':f'{name}-{step}','exit_code':0,'manifest_sha256':sha(manifest),'artifacts':artifacts}));refs[name]={'path':str(p),'sha256':sha(p)}
  final=base/'final.json';final.write_text(json.dumps({'output_directory':str(root),'manifest_path':str(manifest),'manifest_sha256':sha(manifest),'step':step,'stage_receipts':refs}));return root,final
 def repin(self,final,name,mutate):
  d=json.loads(final.read_text());p=Path(d['stage_receipts'][name]['path']);r=json.loads(p.read_text());mutate(r);p.write_text(json.dumps(r));d['stage_receipts'][name]['sha256']=sha(p);final.write_text(json.dumps(d))
 def test_complete_sample_and_time_censored_terminal(self):
  for step,reason,requested in [(0,'sample',0),(1000,'sample',1000),(789,'time_cap',1000),(32000,'sample',32000)]:
   with tempfile.TemporaryDirectory() as temp:
    root,final=self.fixture(Path(temp),step,reason,requested);r=freeze_checkpoint_inventory(root,final,sha(final));self.assertEqual(len(r['source_sha256']),19);self.assertEqual(r['stage_admissions'],7);self.assertEqual(len(r['parent_receipts']),8)
 def test_missing_failed_foreign_manifest_and_changed_artifacts_refused(self):
  for fault in ['missing','failed','manifest','artifact','duplicate']:
   with tempfile.TemporaryDirectory() as temp:
    root,final=self.fixture(Path(temp));d=json.loads(final.read_text())
    if fault=='missing':del d['stage_receipts']['metrics-audit'];final.write_text(json.dumps(d))
    elif fault=='failed':self.repin(final,'audit',lambda r:r.update(exit_code=1))
    elif fault=='manifest':self.repin(final,'audit',lambda r:r.update(manifest_sha256='0'*64))
    elif fault=='artifact':(Path(temp)/'audit.log').write_text('changed')
    else:d['stage_receipts']['audit']=d['stage_receipts']['score'];final.write_text(json.dumps(d))
    with self.assertRaises(ValueError):freeze_checkpoint_inventory(root,final,sha(final))
 def test_extra_missing_symlink_and_unpinned_payload_refused(self):
  for fault in ['extra','missing','symlink','unpin']:
   with tempfile.TemporaryDirectory() as temp:
    root,final=self.fixture(Path(temp))
    if fault=='extra':(root/'foreign.bin').write_bytes(b'x')
    elif fault=='missing':(root/'heads/heads-15.npz').unlink()
    elif fault=='symlink':(root/'link').symlink_to(root/'checkpoint.pt')
    with self.assertRaises(ValueError):freeze_checkpoint_inventory(root,final,'0'*64 if fault=='unpin' else sha(final))
 def test_repinned_bad_producer_state_refused(self):
  for field,value in [('manifest_sha256','0'*64),('updates',999),('updates',True),('resource_gate_passed',False),('requested_updates',999),('stop_reason','other'),('head_hashes',{}),('checkpoint_sha256','0'*64)]:
   with tempfile.TemporaryDirectory() as temp:
    root,final=self.fixture(Path(temp));p=root/'check.json';r=json.loads(p.read_text());r[field]=value;p.write_text(json.dumps(r));self.repin(final,'train',lambda record:record['artifacts'].update({str(p):sha(p)}))
    with self.assertRaises(ValueError):freeze_checkpoint_inventory(root,final,sha(final))
if __name__=='__main__':unittest.main()
