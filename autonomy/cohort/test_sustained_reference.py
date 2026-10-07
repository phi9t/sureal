import unittest
import torch
from cohort import test_sustained_loop as fixture_module
objective=fixture_module.objective
from cohort.sustained_loop import advance
from cohort.sustained_reference import reference_updates
from resources.replay_values import require_exact_state

class IndependentContinuationTests(unittest.TestCase):
 def test_independent_mid_cycle_restart_matches_full_trajectory(self):
  fixture=fixture_module.SustainedLoopTests();identity={'external':'pinned'}
  m,opt,frames=fixture.fixture();whole,_,_=advance(m,opt,frames,objective,identity,35,clock=fixture.clock())
  m,opt,frames=fixture.fixture();partial,_,_=advance(m,opt,frames,objective,identity,19,clock=fixture.clock())
  actual=reference_updates(m,opt,frames,objective,identity,35,checkpoint=partial)
  require_exact_state(whole,actual,exclude_training_seconds=True)
 def test_bad_target_cannot_mutate_model(self):
  fixture=fixture_module.SustainedLoopTests();m,opt,frames=fixture.fixture();partial,_,_=advance(m,opt,frames,objective,{},19,clock=fixture.clock())
  old={k:v.clone() for k,v in m.state_dict().items()}
  for step in [18,36,True]:
   with self.assertRaises(ValueError):reference_updates(m,opt,frames,objective,{},step,checkpoint=partial)
  for key,value in old.items():self.assertTrue(torch.equal(value,m.state_dict()[key]))
 def test_incomplete_frames_and_nonfinite_loss_refused(self):
  fixture=fixture_module.SustainedLoopTests();m,opt,frames=fixture.fixture()
  with self.assertRaises(ValueError):reference_updates(m,opt,frames[:-1],objective,{},1)
  with self.assertRaises(ValueError):reference_updates(m,opt,frames,lambda o,t:{'total':o['value'].sum()*float('nan')},{},1)
if __name__=='__main__':unittest.main()
