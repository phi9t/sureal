import copy,hashlib,tempfile,unittest
from pathlib import Path
from resources.resource_release_plan import release_plan
class RetentionTests(unittest.TestCase):
 def fixture(self,root):
  (root/'checkpoint.pt').write_bytes(b'Adam state')
  member={'path':'checkpoint.pt','bytes':10,'sha256':hashlib.sha256(b'Adam state').hexdigest()}
  return {'closure_complete':True,'manifest_readback_exact':True,'chunks':[{'archive_hdfs_uri':'hdfs://example/unique/archive.tar.gz','manifest':{'members':[member]},'checks':[{'stage':s,'exit_code':0} for s in ['create-live','archive-put','archive-get','manifest-put','manifest-get','verify-live','rehydrate-live']]}]}
 def test_verified_complete_inventory_is_planned_without_deleting(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);publication=self.fixture(root);plan=release_plan(root,publication)
   self.assertEqual(len(plan),1);self.assertTrue((root/'checkpoint.pt').exists())
 def test_missing_gate_extra_payload_and_hash_corruption_rejected(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);publication=self.fixture(root)
   for field in ['closure_complete','manifest_readback_exact']:
    bad=copy.deepcopy(publication);bad[field]=False
    with self.assertRaises(ValueError):release_plan(root,bad)
   bad=copy.deepcopy(publication);bad['chunks'][0]['checks'][2]['exit_code']=1
   with self.assertRaises(ValueError):release_plan(root,bad)
   (root/'unexpected.pt').write_bytes(b'extra')
   with self.assertRaises(ValueError):release_plan(root,publication)
   (root/'unexpected.pt').unlink();(root/'checkpoint.pt').write_bytes(b'changed')
   with self.assertRaises(ValueError):release_plan(root,publication)
if __name__=='__main__':unittest.main()
