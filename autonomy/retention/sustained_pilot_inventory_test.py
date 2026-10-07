import tempfile,json,hashlib,unittest
from pathlib import Path
from retention.sustained_pilot_inventory import freeze_pilot_inventory
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
class PilotInventoryTests(unittest.TestCase):
 def fixture(self,base):
  root=base/'payload';root.mkdir();run=base/'run';run.mkdir();manifest=run/'input/manifest.json';manifest.parent.mkdir();manifest.write_text('{}');refs={}
  for step in [0,19,35]:
   out=root/f'update-{step:02d}';out.mkdir();(out/'heads').mkdir();(out/'checkpoint.pt').write_bytes(b'checkpoint'+bytes([step]));(out/'live.log').write_text('producer')
   heads={}
   for i in range(16):
    p=out/'heads'/f'heads-{i:02d}.npz';p.write_bytes(bytes([step,i]));heads[p.name]=sha(p)
   report={'updates':step,'stop_reason':'sample','resource_gate_passed':True,'checkpoint_sha256':sha(out/'checkpoint.pt'),'head_hashes':heads};(out/'check.json').write_text(json.dumps(report))
   for stage in ['train','audit','literal-loss','export','proposals','score','metrics-audit']:
    key=f'{stage}-{step}';artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file()} if stage=='train' else {};receipt=run/(key+'.json');receipt.write_text(json.dumps({'stage':key,'exit_code':0,'manifest_sha256':sha(manifest),'artifacts':artifacts}));refs[key]={'path':str(receipt),'sha256':sha(receipt)}
  final=base/'final.json';final.write_text(json.dumps({'run_directory':str(run),'output_directory':str(root),'manifest_sha256':sha(manifest),'stage_receipts':refs}));return root,final
 def test_complete_all_three_payloads_bound_to_all21_stages(self):
  with tempfile.TemporaryDirectory() as temp:
   root,final=self.fixture(Path(temp));r=freeze_pilot_inventory(root,final,sha(final));self.assertEqual(len(r['source_sha256']),57);self.assertEqual(len(r['parent_receipts']),22)
 def test_changed_receipt_or_payload_and_extra_member_refused(self):
  for fault in ['parent','payload','extra']:
   with tempfile.TemporaryDirectory() as temp:
    root,final=self.fixture(Path(temp));expected=sha(final)
    if fault=='parent':(Path(temp)/'run/audit-35.json').write_text('{}')
    elif fault=='payload':(root/'update-19/checkpoint.pt').write_bytes(b'changed')
    else:(root/'unverified.bin').write_bytes(b'extra')
    with self.assertRaises(ValueError):freeze_pilot_inventory(root,final,expected)
 def test_repinned_missing_stage_or_failed_stage_refused(self):
  for fault in ['missing','failed','identity']:
   with tempfile.TemporaryDirectory() as temp:
    root,final=self.fixture(Path(temp));d=json.loads(final.read_text())
    if fault=='missing':del d['stage_receipts']['metrics-audit-35']
    else:
     ref=d['stage_receipts']['audit-35'];p=Path(ref['path']);r=json.loads(p.read_text());r['exit_code']=1 if fault=='failed' else 0
     if fault=='identity':r['manifest_sha256']='0'*64
     p.write_text(json.dumps(r));ref['sha256']=sha(p)
    final.write_text(json.dumps(d))
    with self.assertRaises(ValueError):freeze_pilot_inventory(root,final,sha(final))
 def test_wrong_root_symlink_and_unpinned_final_refused(self):
  with tempfile.TemporaryDirectory() as temp:
   root,final=self.fixture(Path(temp))
   with self.assertRaises(ValueError):freeze_pilot_inventory(root,final,'0'*64)
   (root/'link').symlink_to(root/'update-00/checkpoint.pt')
   with self.assertRaises(ValueError):freeze_pilot_inventory(root,final,sha(final))
if __name__=='__main__':unittest.main()
