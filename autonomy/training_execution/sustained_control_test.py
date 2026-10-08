import copy,unittest
from training_execution.sustained_control import decide_next

def sample(step,passed=False):return {'step':step,'APH':{str(i):(.9 if passed else .1) for i in range(1,5)}}
def report(step,requested=None,reason='sample',seconds=1.,admitted=True):return {'updates':step,'requested_updates':step if requested is None else requested,'stop_reason':reason,'cumulative_train_seconds':seconds,'resource_gate_passed':admitted}
class SustainedControlTests(unittest.TestCase):
 def test_first_pass_requires_confirm_and_two_passes_stop(self):
  self.assertEqual(decide_next([sample(0)],report(0))['target_step'],1000)
  first=[sample(0),sample(1000),sample(2000,True)]
  self.assertEqual(decide_next(first,report(2000))['target_step'],3000)
  self.assertEqual(decide_next(first+[sample(3000,True)],report(3000))['status'],'sustained native overfit')
 def test_early_time_cap_pass_cannot_confirm_before_scheduled_sample(self):
  samples=[sample(0),sample(1000,True),sample(1001,True)]
  result=decide_next(samples,report(1001,2000,'time_cap',7199.9))
  self.assertEqual(result['action'],'stop');self.assertEqual(result['status'],'unconfirmed terminal pass')
 def test_finite_budget_terminals_do_not_continue(self):
  grid=[0,1000,2000,4000,8000,12000,16000,24000,32000]
  self.assertEqual(decide_next([sample(x) for x in grid],report(32000))['status'],'failed to overfit by 32000 updates')
  self.assertEqual(decide_next([sample(x,x==32000) for x in grid],report(32000))['status'],'unconfirmed terminal pass')
  self.assertEqual(decide_next([sample(0),sample(1000),sample(1234)],report(1234,2000,'time_cap',7199.9))['status'],'training-time censored without sustained overfit')
  result=decide_next([sample(0),sample(1000),sample(1001,True)],report(1001,2000,'resource_overrun',7201.,False))
  self.assertFalse(result['resource_admitted']);self.assertEqual(result['action'],'stop');self.assertEqual(result['status'],'resource censored; promotion forbidden')
 def test_premature_missing_changed_or_unscored_samples_refused(self):
  for samples,r in [([sample(0),sample(35)],report(35)),([sample(0),sample(2000)],report(2000)),([sample(0),sample(1000)],report(1001)),([sample(0),sample(1000)],report(1000,2000)),([sample(0),sample(1000)],report(1000,1000,'gate')),([sample(0)],report(0,seconds=float('nan')))]:
   with self.assertRaises(ValueError):decide_next(samples,r)
  bad=sample(1000,True);bad['APH']['4']=float('nan')
  with self.assertRaises(ValueError):decide_next([sample(0),bad],report(1000))
 def test_resource_claim_cannot_admit_over_budget_or_hide_failure(self):
  for r in [report(0,seconds=7201.),report(0,admitted=False),report(0,reason='resource_overrun',admitted=True)]:
   with self.assertRaises(ValueError):decide_next([sample(0)],r)
if __name__=='__main__':unittest.main()
