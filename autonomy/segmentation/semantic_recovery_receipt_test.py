import copy,json,tempfile,shutil,unittest
from pathlib import Path
from evidence.source_snapshot import file_sha256
from segmentation.semantic_recovery_receipt import verify_receipt
HERE=Path(__file__).resolve().parent
TESTDATA=HERE/'testdata/semantic_receipts/exact'
def fixture_paths():
 source=Path('/source');code=Path('/experiment')
 if (source/'receipt.json').exists():return source,code
 source=TESTDATA/'source'
 return source,TESTDATA/'code'
def remove_output_mount(r):
 check=r['checks'][0]
 if 'command' in check:check['command'].remove('/outputs')
 else:check['launch_plan']['mounts']=[m for m in check['launch_plan']['mounts'] if m.get('inside_path')!='/outputs']
class ReceiptTests(unittest.TestCase):
 def test_fixture_and_rehashed_mutants(self):
  source,code=fixture_paths()
  original=json.loads((source/'receipt.json').read_text()); expected=original['input_identity']; runtime=original['runtime_lock']; pins=original['candidate_hashes']
  mutations=[None,lambda r:r['checks'][0].update(exit_code=1),lambda r:r.update(candidate_hashes={}),lambda r:r.update(artifacts={}),lambda r:r['transfer'].update(sha256='0'*64),lambda r:r['transfer'].update(working_limit_bytes=10),lambda r:r['runtime_lock'].update(rootfs_sha256='0'*64),lambda r:r['input_identity'].update(scene='other'),lambda r:r['validation'].update(eligible_point_elements=0),remove_output_mount]
  for mutation in mutations:
   with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)/'receipt';shutil.copytree(source,root);r=copy.deepcopy(original)
    if mutation:mutation(r)
    (root/'receipt.json').write_text(json.dumps(r));digest=file_sha256(root/'receipt.json')
    args=dict(expected_sha256=digest,expected_record=expected,expected_runtime=runtime,expected_code=pins,code_root=code)
    if mutation:
     with self.assertRaises(ValueError):verify_receipt(root,**args)
    else:verify_receipt(root,**args)
if __name__=='__main__':unittest.main()
