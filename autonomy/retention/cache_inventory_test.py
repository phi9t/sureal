import tempfile,json,unittest
from pathlib import Path
from evidence.source_snapshot import file_sha256
from retention.cache_inventory import freeze_cache_inventory
sha=lambda p:file_sha256(p)
class CacheInventoryTests(unittest.TestCase):
 def fixture(self,root):
  frame=root/'scene/1';frame.mkdir(parents=True);(frame/'data.bin').write_bytes(b'data')
  receipt=frame/'receipt.json';receipt.write_text(json.dumps({'artifacts':{'data.bin':sha(frame/'data.bin')}}))
  admission=root.parent/'admitted.json';admission.write_text(json.dumps({'receipt':str(receipt),'receipt_sha256':sha(receipt)}))
  return admission
 def test_exact_inventory_and_parent_bindings(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)/'cache';root.mkdir();admission=self.fixture(root);result=freeze_cache_inventory(root,[admission]);self.assertEqual(set(result['source_sha256']),{'scene/1/data.bin','scene/1/receipt.json'});self.assertEqual(result['parent_receipts'][str(admission)],sha(admission))
 def test_missing_duplicate_admission_and_changed_payload_refused(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)/'cache';root.mkdir();admission=self.fixture(root)
   for parents in [[],[admission,admission]]:
    with self.assertRaises(ValueError):freeze_cache_inventory(root,parents)
   (root/'scene/1/data.bin').write_bytes(b'changed')
   with self.assertRaises(ValueError):freeze_cache_inventory(root,[admission])
 def test_foreign_parent_unsafe_artifact_and_symlink_refused(self):
  for fault in ['foreign','unsafe','symlink']:
   with tempfile.TemporaryDirectory() as temp:
    root=Path(temp)/'cache';root.mkdir();admission=self.fixture(root);r=json.loads(admission.read_text())
    if fault=='foreign':r['receipt']=str(Path(temp)/'foreign/receipt.json')
    elif fault=='unsafe':
     receipt=root/'scene/1/receipt.json';receipt.write_text(json.dumps({'artifacts':{'../outside': '0'*64}}));r['receipt_sha256']=sha(receipt)
    else:(root/'link').symlink_to(root/'scene/1/data.bin')
    admission.write_text(json.dumps(r))
    with self.assertRaises(ValueError):freeze_cache_inventory(root,[admission])

if __name__ == '__main__':
 unittest.main()
