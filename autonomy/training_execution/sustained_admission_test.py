import copy,unittest
from cohort.sustained_admission import admit_sample
class SustainedAdmissionTests(unittest.TestCase):
 def fixture(self):
  identities=[f'frame-{i}' for i in range(16)];heads={f'heads-{i:02d}.npz':'0'*64 for i in range(16)};manifest={'recipe':'baseline','frames':[{'identity':v} for v in identities]};producer={'updates':1000,'manifest_sha256':'1'*64,'head_hashes':heads,'checkpoint_sha256':'2'*64,'resource_gate_passed':True,'peak_allocated_bytes':1024,'peak_rss_kib':1024};replay={'updates':1000,'manifest_sha256':'1'*64,'checkpoint_sha256':'2'*64,'head_hashes':heads,'checked_frames':identities};transition={'manifest_sha256':'1'*64,'checkpoint_sha256':'2'*64,'previous_checkpoint_sha256':'3'*64,'start_step':0,'terminal_step':1000,'literal_updates':1000,'state_exact_excluding_training_seconds':True,'producer_synchronized_seconds_reconciled':True,'peak_allocated_bytes':1024,'peak_rss_kib':1024};loss={'frames':16,'recipe':'baseline','updates':1000,'manifest_sha256':'1'*64,'report_sha256':'4'*64,'head_hashes':heads,'rows':[{'identity':v} for v in identities]};proposals={'frames':16,'predictions':8000,'native_groundtruth':1279,'literal_score_first_decode_nms_and_measurement_metadata':True,'all_native_GT_retained':True};score={'frames':[{'identity':v} for v in identities],'native_groundtruth':1279,'predictions':8000,'manifest_sha256':'1'*64,'head_hashes':heads,'decoder_version':3,'groundtruth_policy':'all native four-class boxes; native evaluator handles eligibility','LEVEL2_per_class':{str(c):{'AP':.9,'APH':.85} for c in range(1,5)},'all_class_APH_gate_passed':True,'APH_gate_passed':True};metric={'all_export_fields_independently_reread':True,'native_metric_replay_exact':True,'all_class_APH_gate_passed':True};return {'manifest':manifest,'manifest_sha256':'1'*64,'producer':producer,'producer_sha256':'4'*64,'replay':replay,'transition':transition,'previous_checkpoint_sha256':'3'*64,'start_step':0,'loss':loss,'proposals':proposals,'score':score,'metric':metric}
 def test_complete_native_sample(self):
  self.assertEqual(admit_sample(**self.fixture()),{'step':1000,'APH':{str(c):.85 for c in range(1,5)}})
 def test_repinning_one_report_cannot_hide_foreign_manifest_head_or_frame(self):
  for field,key,value in [('producer','manifest_sha256','9'*64),('replay','head_hashes',{}),('replay','checked_frames',['foreign']*16),('loss','recipe','residual_bev'),('score','head_hashes',{}),('score','native_groundtruth',1053),('transition','previous_checkpoint_sha256','9'*64)]:
   d=self.fixture();d[field][key]=value
   with self.assertRaises(ValueError):admit_sample(**d)
 def test_partial_or_self_asserted_native_gates_refused(self):
  for field,key in [('transition','state_exact_excluding_training_seconds'),('transition','producer_synchronized_seconds_reconciled'),('proposals','all_native_GT_retained'),('metric','native_metric_replay_exact'),('metric','all_export_fields_independently_reread'),('producer','resource_gate_passed')]:
   d=self.fixture();d[field][key]=False
   with self.assertRaises(ValueError):admit_sample(**d)
 def test_missing_nonfinite_out_of_bounds_class_and_false_gate_refused(self):
  for fault in ['missing','nan','boolean','range','gate']:
   d=self.fixture();classes=d['score']['LEVEL2_per_class']
   if fault=='missing':del classes['4']
   elif fault=='gate':d['metric']['all_class_APH_gate_passed']=False
   else:classes['4']['APH']={'nan':float('nan'),'boolean':True,'range':1.1}[fault]
   with self.assertRaises(ValueError):admit_sample(**d)
if __name__=='__main__':unittest.main()
