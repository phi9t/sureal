import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from studies.expanded_batch.expanded_verifier import verify
from resources.scientific_payload import sha
class AdmissionVerifierTests(unittest.TestCase):
 def test_swapping_architecture_identity_is_rejected(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);run=root/'run';run.mkdir();admission=root/'admission.json';result=root/'results.json'
   case={'architecture':'point_attention'}
   admission.write_text(json.dumps({'cases':{'point_attention':{'exit_code':0,'validation':{'case':{'architecture':'ragged_pillars'},'exact_repeated_three_update_model_adam_rng':True,'finite_all_parameter_gradients':True,'fixed_head_shape':True},'artifacts':{}}},'source_pins':{}}))
   (run/'run.json').write_text(json.dumps({'matrix':{'point_attention':case}}))
   (run/'admission-reference.json').write_text(json.dumps({'path':str(admission),'sha256':sha(admission)}))
   result.write_text(json.dumps({'run_directory':str(run)}))
   with patch('studies.expanded_batch.expanded_verifier.native.verify',return_value={'rows':[]}):
    with self.assertRaises(AssertionError):verify(result)
if __name__=='__main__':unittest.main()
