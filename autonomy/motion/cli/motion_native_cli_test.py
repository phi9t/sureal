"""Analytic CLI boundaries; execute only in the locked native Motion runtime."""
import json,subprocess,tempfile,unittest
from pathlib import Path
BINARY='/motion-cli-build/compute_motion_metrics'
class MotionNativeCliTests(unittest.TestCase):
 def fixture(self,root,offset=0,mode_offsets=None):
  scene='scenario_id: "analytic" current_time_index: 10 '
  scene+=' '.join('timestamps_seconds: '+str(i/10) for i in range(91))
  scene+=' tracks { id: 1 object_type: TYPE_VEHICLE '
  scene+=' '.join('states { center_x: '+str(i/10)+' center_y: 0 center_z: 0 length: 4 width: 2 height: 1.5 heading: 0 velocity_x: 1 velocity_y: 0 valid: true }' for i in range(91))
  scene+=' } tracks_to_predict { track_index: 0 difficulty: LEVEL_1 }'
  prediction='scenario_id: "analytic" multi_modal_predictions { '
  for value in mode_offsets or [offset]:
   prediction+='joint_predictions { confidence: 1 trajectories { object_id: 1 '
   prediction+=' '.join('center_x: '+str((15+i*5)/10+value)+' center_y: 0' for i in range(16))
   prediction+=' } } '
  prediction+=' }'
  config='track_steps_per_second: 10 prediction_steps_per_second: 2 track_history_samples: 10 track_future_samples: 80 max_predictions: 1 step_configurations { measurement_step: 15 lateral_miss_threshold: 3 longitudinal_miss_threshold: 6 }'
  for name,text in [('scenario',scene),('predictions',prediction),('config',config)]:(root/(name+'.textproto')).write_text(text)
  return [BINARY,str(root/'scenario.textproto'),str(root/'predictions.textproto'),str(root/'config.textproto'),str(root/'result.json')]
 def run_case(self,offset=0,mode_offsets=None):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);cmd=self.fixture(root,offset,mode_offsets);r=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr);return json.loads((root/'result.json').read_text())
 def test_perfect_and_constant_offset_have_analytic_errors_and_counts(self):
  for error in [0,2]:
   with self.subTest(error=error):
    result=self.run_case(error);bundles=result['metrics']['metricsBundles'];vehicle=next(x for x in bundles if x.get('objectFilter')=='TYPE_VEHICLE');self.assertAlmostEqual(float(vehicle['minAde']),error,places=5);self.assertAlmostEqual(float(vehicle['minFde']),error,places=5)
    count=next(x for x in result['counts'] if x['object_type']==1 and x['measurement_step']==15);self.assertEqual(count['min_ade'],1);self.assertEqual(count['min_fde'],1)
 def test_first_serialized_k_modes_not_confidence_reranking(self):
  result=self.run_case(mode_offsets=[2,0]);vehicle=next(x for x in result['metrics']['metricsBundles'] if x.get('objectFilter')=='TYPE_VEHICLE');self.assertAlmostEqual(float(vehicle['minFde']),2,places=5)
 def test_malformed_identity_and_endpoint_refuse_without_output(self):
  for kind in ['malformed','identity','endpoint']:
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);cmd=self.fixture(root)
    if kind=='malformed':(root/'scenario.textproto').write_text('not a proto')
    elif kind=='identity':p=root/'predictions.textproto';p.write_text(p.read_text().replace('"analytic"','"other"'))
    else:p=root/'config.textproto';p.write_text(p.read_text().replace('measurement_step: 15','measurement_step: 16'))
    r=subprocess.run(cmd,capture_output=True,text=True);self.assertNotEqual(r.returncode,0);self.assertFalse((root/'result.json').exists())
 def test_missing_future_labels_have_zero_measurement_counts(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);cmd=self.fixture(root);p=root/'scenario.textproto';text=p.read_text();prefix,tail=text.split('center_x: 1.1 ',1);p.write_text(prefix+'center_x: 1.1 '+tail.replace('valid: true','valid: false'))
   r=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr);result=json.loads((root/'result.json').read_text());count=next(x for x in result['counts'] if x['object_type']==1 and x['measurement_step']==15);self.assertEqual(count['min_ade'],0);self.assertEqual(count['min_fde'],0);self.assertEqual(count['miss_rate'],0)
 def test_confident_wrong_mode_reduces_map_while_best_error_is_zero(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);cmd=self.fixture(root,mode_offsets=[20,0]);p=root/'config.textproto';p.write_text(p.read_text().replace('max_predictions: 1','max_predictions: 2'))
   p=root/'predictions.textproto';p.write_text(p.read_text().replace('confidence: 1','confidence: 0.9',1).replace('confidence: 1','confidence: 0.1',1))
   r=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr);result=json.loads((root/'result.json').read_text());vehicle=next(x for x in result['metrics']['metricsBundles'] if x.get('objectFilter')=='TYPE_VEHICLE');self.assertAlmostEqual(float(vehicle['minFde']),0,places=5);self.assertAlmostEqual(float(vehicle['meanAveragePrecision']),0.5,places=5)
 def test_nonfinite_speed_and_invalid_scaling_refused(self):
  for kind in ['velocity','scale']:
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);cmd=self.fixture(root)
    if kind=='velocity':p=root/'scenario.textproto';p.write_text(p.read_text().replace('velocity_x: 1','velocity_x: nan'))
    else:p=root/'config.textproto';p.write_text(p.read_text()+' speed_lower_bound: 11 speed_upper_bound: 1.4')
    r=subprocess.run(cmd,capture_output=True,text=True);self.assertNotEqual(r.returncode,0);self.assertFalse((root/'result.json').exists())
if __name__=='__main__':unittest.main()
