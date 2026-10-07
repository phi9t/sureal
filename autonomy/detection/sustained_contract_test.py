import copy,math,unittest
from sustained.sustained_contract import validate_contract,next_checkpoint,fit_status

def fixture():
 frames=[{'identity':str(i),'split':'training','sha256':{'observations.npz':format(i,'064x'),'targets.npz':format(i+16,'064x'),'report.json':format(i+32,'064x')}} for i in range(16)]
 candidate={'schema_version':1,'frames':copy.deepcopy(frames),'seed':17,'recipes':['baseline','residual_bev','class_balanced','prior_bias'],'max_updates':32000,'max_training_seconds':7200,'checkpoint_grid':[0,1000,2000,4000,8000,12000,16000,24000,32000],'confirmation_gap':1000,'decoder_version':3,'APH_threshold':.8}
 return candidate,frames

class SustainedContractTests(unittest.TestCase):
 def test_full_admitted_training_identity_required(self):
  candidate,frames=fixture();validate_contract(candidate,frames)
  for mutate in [lambda c:c['frames'].pop(),lambda c:c['frames'][0].update(split='validation'),lambda c:c['frames'][0].update(identity='changed'),lambda c:c['frames'][0]['sha256'].update({'targets.npz':'f'*64}),lambda c:c['frames'].__setitem__(1,copy.deepcopy(c['frames'][0]))]:
   bad=copy.deepcopy(candidate);mutate(bad)
   with self.assertRaises(ValueError):validate_contract(bad,frames)
 def test_pinned_execution_cannot_silently_change(self):
  candidate,frames=fixture()
  for key,value in [('decoder_version',2),('seed',18),('max_updates',64000),('max_training_seconds',14400),('APH_threshold',.7),('checkpoint_grid',[0,32000]),('recipes',['baseline'])]:
   bad=copy.deepcopy(candidate);bad[key]=value
   with self.assertRaises(ValueError):validate_contract(bad,frames)
 def test_confirmation_uses_earlier_fixed_checkpoint(self):
  self.assertEqual(next_checkpoint(2000,2000),3000)
  self.assertEqual(next_checkpoint(3000,3000),4000)
  self.assertIsNone(next_checkpoint(32000,32000))
  with self.assertRaises(ValueError):next_checkpoint(32001,None)
 def samples(self,steps,passing=()):
  return [{'step':step,'APH':{str(i):(.9 if step in passing else .1) for i in range(1,5)}} for step in steps]
 def test_all_classes_two_consecutive_terminal_samples(self):
  samples=self.samples([0,1000,2000],{1000,2000})
  self.assertEqual(fit_status(samples,2000,'gate'),'sustained native overfit')
  for value in [.1,float('nan'),float('inf')]:
   bad=copy.deepcopy(samples);bad[-1]['APH']['4']=value
   with self.assertRaises(ValueError):fit_status(bad,2000,'gate')
  bad=copy.deepcopy(samples);del bad[-1]['APH']['4']
  with self.assertRaises(ValueError):fit_status(bad,2000,'gate')
 def test_cap_reason_and_sample_order_cannot_be_faked(self):
  steps=[0,1000,2000,4000,8000,12000,16000,24000,32000]
  self.assertEqual(fit_status(self.samples(steps),32000,'update_cap'),'failed to overfit by 32000 updates')
  self.assertEqual(fit_status(self.samples([0,1000,1234]),1234,'time_cap'),'training-time censored without sustained overfit')
  with self.assertRaises(ValueError):fit_status(self.samples([0,1000,1234]),1234,'update_cap')
  with self.assertRaises(ValueError):fit_status(self.samples([0,1000,1000]),1000,'time_cap')
 def test_missing_or_early_checkpoint_cannot_confirm(self):
  for steps in [[1000,1001],[0,1000,1001],[0,1000,4000]]:
   with self.assertRaises(ValueError):fit_status(self.samples(steps,set(steps[1:])),steps[-1],'gate')
 def test_early_time_terminal_cannot_confirm(self):
  samples=self.samples([0,1000,1001],{1000,1001})
  self.assertEqual(fit_status(samples,1001,'time_cap'),'unconfirmed terminal pass')
 def test_first_pass_cannot_end_at_gate(self):
  with self.assertRaises(ValueError):fit_status(self.samples([0,1000],{1000}),1000,'gate')
  steps=[0,1000,2000,4000,8000,12000,16000,24000,32000]
  self.assertEqual(fit_status(self.samples(steps,{32000}),32000,'update_cap'),'unconfirmed terminal pass')

if __name__=='__main__':unittest.main()
