import unittest
from training_execution.sustained_workflow import execute_case
class Backend:
 def __init__(self,*,passing=False,fail_stage=None,fail_publication=False,time_cap=False):self.events=[];self.passing=passing;self.fail_stage=fail_stage;self.fail_publication=fail_publication;self.time_cap=time_cap
 def validate_resume(self,records):self.events.append(('validate',len(records)))
 def train_and_admit(self,previous,target):
  self.events.append(('sample',target))
  if self.fail_stage==target:raise RuntimeError('independent native gate failed')
  actual=777 if self.time_cap and target==1000 else target
  report={'updates':actual,'requested_updates':target,'stop_reason':'time_cap' if actual!=target else 'sample','cumulative_train_seconds':7200 if actual!=target else actual*.1,'resource_gate_passed':True}
  return {'step':actual,'report':report,'sample':{'step':actual,'APH':{str(c):.9 if self.passing and actual>=1000 else .1 for c in range(1,5)}},'released':False}
 def persist(self,records,decision=None,diagnostic=None):self.events.append(('persist',tuple(r['step'] for r in records),decision))
 def publish_and_release(self,record):
  self.events.append(('archive',record['step']))
  if self.fail_publication:raise RuntimeError('HDFS readback failed')
  return {'external_receipt':'fixture'}
class WorkflowTests(unittest.TestCase):
 def test_exact_confirmation_and_keep_two_until_next_admission(self):
  b=Backend(passing=True);records,decision=execute_case(b);self.assertEqual([r['step'] for r in records],[0,1000,2000]);self.assertEqual(decision['status'],'sustained native overfit');self.assertEqual([e for e in b.events if e[0]=='archive'],[('archive',0),('archive',1000),('archive',2000)]);self.assertLess(b.events.index(('sample',2000)),b.events.index(('archive',0)));self.assertTrue(all(r['released'] for r in records))
 def test_stage_failure_never_retires_old_checkpoint_or_advances(self):
  b=Backend(fail_stage=2000)
  with self.assertRaises(RuntimeError):execute_case(b)
  self.assertFalse(any(e[0]=='archive' for e in b.events));self.assertEqual([e[1] for e in b.events if e[0]=='sample'],[0,1000,2000])
 def test_hdfs_failure_prevents_next_chunk_and_marks_no_release(self):
  b=Backend(fail_publication=True)
  with self.assertRaises(RuntimeError):execute_case(b)
  self.assertEqual([e[1] for e in b.events if e[0]=='sample'],[0,1000,2000]);self.assertEqual([e for e in b.events if e[0]=='archive'],[('archive',0)])
 def test_time_censored_partial_interval_cannot_confirm_fit(self):
  b=Backend(passing=True,time_cap=True);records,decision=execute_case(b);self.assertEqual([r['step'] for r in records],[0,777]);self.assertEqual(decision['status'],'training-time censored without sustained overfit')
 def test_no_progress_time_cap_cannot_become_second_confirmation(self):
  class NoProgress(Backend):
   def train_and_admit(self,previous,target):
    result=super().train_and_admit(previous,target)
    if target==2000:
     result['step']=1000;result['sample']['step']=1000;result['report'].update(updates=1000,stop_reason='time_cap',cumulative_train_seconds=7200)
    return result
  b=NoProgress(passing=True);records,decision=execute_case(b)
  self.assertEqual([r['step'] for r in records],[0,1000]);self.assertEqual(decision['status'],'unconfirmed terminal pass')
  self.assertEqual(len([e for e in b.events if e[0]=='archive']),3)
 def test_fixed_full_grid_stops_at_cap(self):
  b=Backend();records,decision=execute_case(b);self.assertEqual([r['step'] for r in records],[0,1000,2000,4000,8000,12000,16000,24000,32000]);self.assertEqual(decision['status'],'failed to overfit by 32000 updates')
 def test_resume_starts_after_admitted_checkpoint_and_rechecks_state(self):
  initial=Backend();record=initial.train_and_admit(None,0);b=Backend(passing=True);records,decision=execute_case(b,[record]);self.assertEqual([e[1] for e in b.events if e[0]=='sample'],[1000,2000]);self.assertEqual(b.events[0],('validate',1));self.assertEqual(decision['status'],'sustained native overfit')
if __name__=='__main__':unittest.main()
