"""Extend the shared literal/native/replay closure with architecture admission."""
import json,sys
from pathlib import Path
from studies.fixed_batch import fixed_batch_verifier as native

def verify(path):
 closure=native.verify(path)
 result=json.loads(Path(path).read_text());run=Path(result['run_directory'])
 reference=json.loads(native.read(run/'admission-reference.json'))
 assert native.sha(reference['path'])==reference['sha256']
 admission=json.loads(native.read(reference['path']))
 metadata=json.loads(native.read(run/'run.json'))
 assert set(admission['cases'])==set(metadata['matrix'])
 for case,evidence in admission['cases'].items():
  assert evidence['exit_code']==0
  assert evidence['validation']['case']==metadata['matrix'][case]
  assert evidence['validation']['fixed_head_shape']
  assert evidence['validation']['exact_repeated_three_update_model_adam_rng']
  assert evidence['validation']['finite_all_parameter_gradients']
  for p,h in evidence['artifacts'].items():assert native.sha(p)==h
 for p,h in admission['source_pins'].items():assert native.sha(p)==h
 closure['architecture_admission_receipt_sha256']=reference['sha256']
 closure['scope']='all eight planned-architecture/control treatments; unchanged four-class training-only native fitting and exact full replay'
 return closure
if __name__=='__main__':
 path=Path(sys.argv[1]);result=verify(path);path.with_name(path.stem+'-closed.json').write_text(json.dumps(result,indent=2));print('ADMITTED expanded results',len(result['rows']))
