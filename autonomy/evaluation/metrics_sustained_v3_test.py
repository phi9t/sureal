import hashlib,json,os,runpy,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch

BREAKDOWNS=(
 "OBJECT_TYPE_TYPE_VEHICLE_LEVEL_1",
 "OBJECT_TYPE_TYPE_VEHICLE_LEVEL_2",
 "OBJECT_TYPE_TYPE_PEDESTRIAN_LEVEL_1",
 "OBJECT_TYPE_TYPE_PEDESTRIAN_LEVEL_2",
 "OBJECT_TYPE_TYPE_SIGN_LEVEL_1",
 "OBJECT_TYPE_TYPE_SIGN_LEVEL_2",
 "OBJECT_TYPE_TYPE_CYCLIST_LEVEL_1",
 "OBJECT_TYPE_TYPE_CYCLIST_LEVEL_2",
 "RANGE_TYPE_VEHICLE_[0, 30)_LEVEL_1",
 "RANGE_TYPE_VEHICLE_[0, 30)_LEVEL_2",
 "RANGE_TYPE_VEHICLE_[30, 50)_LEVEL_1",
 "RANGE_TYPE_VEHICLE_[30, 50)_LEVEL_2",
 "RANGE_TYPE_VEHICLE_[50, +inf)_LEVEL_1",
 "RANGE_TYPE_VEHICLE_[50, +inf)_LEVEL_2",
 "RANGE_TYPE_PEDESTRIAN_[0, 30)_LEVEL_1",
 "RANGE_TYPE_PEDESTRIAN_[0, 30)_LEVEL_2",
 "RANGE_TYPE_PEDESTRIAN_[30, 50)_LEVEL_1",
 "RANGE_TYPE_PEDESTRIAN_[30, 50)_LEVEL_2",
 "RANGE_TYPE_PEDESTRIAN_[50, +inf)_LEVEL_1",
 "RANGE_TYPE_PEDESTRIAN_[50, +inf)_LEVEL_2",
 "RANGE_TYPE_SIGN_[0, 30)_LEVEL_1",
 "RANGE_TYPE_SIGN_[0, 30)_LEVEL_2",
 "RANGE_TYPE_SIGN_[30, 50)_LEVEL_1",
 "RANGE_TYPE_SIGN_[30, 50)_LEVEL_2",
 "RANGE_TYPE_SIGN_[50, +inf)_LEVEL_1",
 "RANGE_TYPE_SIGN_[50, +inf)_LEVEL_2",
 "RANGE_TYPE_CYCLIST_[0, 30)_LEVEL_1",
 "RANGE_TYPE_CYCLIST_[0, 30)_LEVEL_2",
 "RANGE_TYPE_CYCLIST_[30, 50)_LEVEL_1",
 "RANGE_TYPE_CYCLIST_[30, 50)_LEVEL_2",
 "RANGE_TYPE_CYCLIST_[50, +inf)_LEVEL_1",
 "RANGE_TYPE_CYCLIST_[50, +inf)_LEVEL_2",
)
CLASS_BREAKDOWNS={
 1:"OBJECT_TYPE_TYPE_VEHICLE_LEVEL_2",
 2:"OBJECT_TYPE_TYPE_PEDESTRIAN_LEVEL_2",
 3:"OBJECT_TYPE_TYPE_SIGN_LEVEL_2",
 4:"OBJECT_TYPE_TYPE_CYCLIST_LEVEL_2",
}
KNOWN_STDERR="""WARNING: Logging before InitGoogleLogging() is written to STDERR
W20261003 07:16:14.727084     5 iou.cc:172] Tiny box dim seen, return 0.0 IOU.
b1: center_x: 16.576610254024722
center_y: 15.012704453096376
center_z: 12.068397189884765
width: 0.0018523699306077972
length: 1.0424807764507029e-14
height: 2.6744237701485357e-13
heading: 2.76738943655627

b2: center_x: -22.493484775371144
center_y: 9.195233822244063
center_z: 0.74115756813910139
width: 1.9570524265672498
length: 4.9495852117525452
height: 1.5099999999999909
heading: 3.0167059680111592
"""

def native_stdout(scores):
 level2={CLASS_BREAKDOWNS[index]:score for index,score in enumerate(scores,start=1)}
 lines=["7 examples found.",""]
 for breakdown in BREAKDOWNS:
  score=level2.get(breakdown,0.0)
  lines.append(f"{breakdown}: [mAP {score}] [mAPH {score}]")
 return "\n".join(lines)+"\n"

def native_metrics(scores):
 level2={CLASS_BREAKDOWNS[index]:score for index,score in enumerate(scores,start=1)}
 return {breakdown:{'AP':level2.get(breakdown,0.0),'APH':level2.get(breakdown,0.0)} for breakdown in BREAKDOWNS}

def sha256(path):
 return hashlib.sha256(path.read_bytes()).hexdigest()

class NativeMetricGateTests(unittest.TestCase):
 def execute(self,scores,*,decoder=3,stdout=None,stderr=KNOWN_STDERR):
  with tempfile.TemporaryDirectory(dir=os.environ.get('TEST_TMPDIR')) as temp:
   worker=Path(__file__).with_name('metrics_sustained_v3.py');root=Path(temp);out=root/'outputs';source=root/'source';out.mkdir();source.mkdir();(source/'predictions.json').write_text('[]');(source/'groundtruth.json').write_text('[]');prep={'decoder_version':decoder,'groundtruth_policy':'all native four-class boxes; native evaluator handles eligibility','frames':[{} for _ in range(16)],'native_groundtruth':0,'groundtruth_by_class':{str(c):1 for c in range(1,5)}};(source/'preparation.json').write_text(json.dumps(prep))
   result=types.SimpleNamespace(returncode=0,stdout=stdout or native_stdout(scores),stderr=stderr);real_path=Path
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
 def test_strict_reader_diagnostics_and_range_keys_are_recorded(self):
  report=self.execute([.81,.82,.83,.84])
  self.assertEqual(report['LEVEL2_per_class'],{str(index):{'AP':score,'APH':score} for index,score in enumerate([.81,.82,.83,.84],start=1)})
  self.assertEqual(report['diagnostics'],{'glog_preinit':1,'iou.cc:172 Tiny box dim seen':1})
  self.assertEqual(report['metrics']['RANGE_TYPE_VEHICLE_[0, 30)_LEVEL_1'],{'AP':0.0,'APH':0.0})
  self.assertNotIn('30)_LEVEL_1',report['metrics'])
 def test_malformed_native_report_is_rejected(self):
  with self.assertRaisesRegex(ValueError,'missing native example count'):
   self.execute([.9]*4,stdout=native_stdout([.9]*4).replace('7 examples found.\n\n',''))
 def test_nonfinite_native_scores_and_legacy_decoder_refused(self):
  for values in [[float('nan'),.9,.9,.9],[1.1,.9,.9,.9]]:
   with self.assertRaises(ValueError):self.execute(values)
  with self.assertRaises(ValueError):self.execute([.9]*4,decoder=2)

class SustainedMetricAuditTests(unittest.TestCase):
 def test_audit_rereads_strict_report_and_compares_diagnostics(self):
  with tempfile.TemporaryDirectory(dir=os.environ.get('TEST_TMPDIR')) as temp:
   worker=Path(__file__).with_name('audit_metrics_sustained_v3.py');root=Path(temp);source=root/'source';scored=root/'scored';tmp=root/'tmp';out=root/'outputs'
   for directory in (source,scored,tmp,out):directory.mkdir()
   for name in ['predictions','groundtruth']:
    (source/(name+'.json')).write_text('[]');(scored/(name+'.bin')).write_bytes(b'fixture')
   scores=[.81,.82,.83,.84]
   validation={'metrics':native_metrics(scores),'diagnostics':{'glog_preinit':1,'iou.cc:172 Tiny box dim seen':1},'LEVEL2_per_class':{str(index):{'AP':score,'APH':score} for index,score in enumerate(scores,start=1)},'mean_populated_class_APH':sum(scores)/4,'APH_gate_passed':True,'all_class_APH_gate_passed':True,'decoder_version':3,'groundtruth_policy':'all native four-class boxes; native evaluator handles eligibility'}
   receipt={'parent_artifacts':{'prepared/predictions.json':sha256(source/'predictions.json'),'prepared/groundtruth.json':sha256(source/'groundtruth.json')},'artifacts':{'scored/predictions.bin':sha256(scored/'predictions.bin'),'scored/groundtruth.bin':sha256(scored/'groundtruth.bin')},'validation':validation}
   score_receipt=tmp/'score-receipt.json';score_receipt.write_text(json.dumps(receipt,sort_keys=True));(tmp/'expected.json').write_text(json.dumps({'receipt':receipt,'receipt_sha256':sha256(score_receipt)},sort_keys=True));real_path=Path
   def paths(value):
    text=os.fspath(value)
    if text=='/outputs':return out
    if text.startswith('/outputs/'):return out/text.split('/')[-1]
    if text=='/tmp/expected.json':return tmp/'expected.json'
    if text=='/tmp/score-receipt.json':return score_receipt
    if text=='/tmp/scored':return scored
    if text=='/source':return source
    if text.startswith('/tmp/scored/'):return scored/text.split('/')[-1]
    if text.startswith('/source/'):return source/text.split('/')[-1]
    return real_path(value)
   def run_side_effect(command,**kwargs):
    if command[0]=='protoc':return types.SimpleNamespace(returncode=0,stdout=b'',stderr=b'')
    return types.SimpleNamespace(returncode=0,stdout=native_stdout(scores),stderr=KNOWN_STDERR)
   def audit_sha(value):
    text=os.fspath(value)
    if text=='/tmp/score-receipt.json':return sha256(score_receipt)
    if text.startswith('/tmp/scored/'):return sha256(scored/text.split('/')[-1])
    if text.startswith('/source/'):return sha256(source/text.split('/')[-1])
    return sha256(real_path(text))
   with patch('pathlib.Path',side_effect=paths),patch('subprocess.run',side_effect=run_side_effect),patch('evidence.source_snapshot.file_sha256',side_effect=audit_sha):
    runpy.run_path(str(worker),run_name='__main__')
   report=json.loads((out/'check.json').read_text())
   self.assertTrue(report['native_metric_replay_exact'])
   self.assertEqual(report['all_class_APH_gate_passed'],True)
   self.assertEqual(report['diagnostics'],{'glog_preinit':1,'iou.cc:172 Tiny box dim seen':1})
if __name__=='__main__':unittest.main()
