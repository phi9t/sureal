import copy,json,tempfile,shutil,hashlib,unittest
from pathlib import Path
from segmentation.semantic_recovery_receipt import verify_receipt
class ReceiptTests(unittest.TestCase):
 def test_fixture_and_rehashed_mutants(self):
  original=json.loads(Path('/source/receipt.json').read_text()); expected=original['input_identity']; runtime=original['runtime_lock']; pins=original['candidate_hashes']
  mutations=[None,lambda r:r['checks'][0].update(exit_code=1),lambda r:r.update(candidate_hashes={}),lambda r:r.update(artifacts={}),lambda r:r['transfer'].update(sha256='0'*64),lambda r:r['transfer'].update(working_limit_bytes=10),lambda r:r['runtime_lock'].update(rootfs_sha256='0'*64),lambda r:r['input_identity'].update(scene='other'),lambda r:r['validation'].update(eligible_point_elements=0)]
  for mutation in mutations:
   with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)/'receipt';shutil.copytree('/source',root);r=copy.deepcopy(original)
    if mutation:mutation(r)
    (root/'receipt.json').write_text(json.dumps(r));digest=hashlib.sha256((root/'receipt.json').read_bytes()).hexdigest()
    args=dict(expected_sha256=digest,expected_record=expected,expected_runtime=runtime,expected_code=pins,code_root=Path('/experiment'))
    if mutation:
     with self.assertRaises(ValueError):verify_receipt(root,**args)
    else:verify_receipt(root,**args)
if __name__=='__main__':unittest.main()
