import json,runpy,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
class NativeMetricGateTests(unittest.TestCase):
 def execute(self,scores,*,decoder=3):
  with tempfile.TemporaryDirectory() as temp:
   worker=Path(__file__).with_name('metrics_sustained_v3.py');root=Path(temp);out=root/'outputs';source=root/'source';out.mkdir();source.mkdir();(source/'predictions.json').write_text('[]');(source/'groundtruth.json').write_text('[]');prep={'decoder_version':decoder,'groundtruth_policy':'all native four-class boxes; native evaluator handles eligibility','frames':[{} for _ in range(16)],'native_groundtruth':0,'groundtruth_by_class':{str(c):1 for c in range(1,5)}};(source/'preparation.json').write_text(json.dumps(prep))
   stdout='\n'.join(f'OBJECT_TYPE_TYPE_{name}_LEVEL_2: [mAP {score}] [mAPH {score}]' for name,score in zip(['VEHICLE','PEDESTRIAN','SIGN','CYCLIST'],scores));result=types.SimpleNamespace(returncode=0,stdout=stdout,stderr='');real_path=Path
   def paths(value):
    if value=='/outputs':return out
    if value.startswith('/source/'):return source/value.split('/')[-1]
    return real_path(value)
   with patch('pathlib.Path',side_effect=paths),patch('detection.detection_export.export_objects',return_value=b'unit fixture'),patch('subprocess.run',return_value=result):runpy.run_path(str(worker),run_name='__main__')
   return json.loads((out/'check.json').read_text())
 def test_high_mean_cannot_hide_one_failed_class(self):
  report=self.execute([.99,.99,.99,.79]);self.assertGreater(report['mean_populated_class_APH'],.8);self.assertFalse(report['all_class_APH_gate_passed']);self.assertFalse(report['APH_gate_passed'])
 def test_each_class_pass_still_requires_checkpoint_confirmation(self):
  report=self.execute([.8,.9,.95,.99]);self.assertTrue(report['all_class_APH_gate_passed']);self.assertTrue(report['checkpoint_confirmation_required'])
 def test_nonfinite_native_scores_and_legacy_decoder_refused(self):
  for values in [[float('nan'),.9,.9,.9],[1.1,.9,.9,.9]]:
   with self.assertRaises(ValueError):self.execute(values)
  with self.assertRaises(ValueError):self.execute([.9]*4,decoder=2)
if __name__=='__main__':unittest.main()
