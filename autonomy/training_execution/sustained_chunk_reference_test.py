import unittest
import torch
from training_execution import sustained_loop_test as fixtures
objective=fixtures.objective
from training_execution.sustained_loop import advance
from training_execution.sustained_chunk_reference import reference_chunk
from resources.replay_values import require_exact_state

class ChunkReferenceTests(unittest.TestCase):
 def test_beyond_pilot_and_mid_cycle_restart_matches_original_loop(self):
  fixture=fixtures.SustainedLoopTests();identity={'externally_admitted':'recipe'}
  m,opt,frames=fixture.fixture();whole,_,_=advance(m,opt,frames,objective,identity,1000,clock=fixture.clock())
  m,opt,frames=fixture.fixture();partial,_,_=advance(m,opt,frames,objective,identity,47,clock=fixture.clock())
  actual=reference_chunk(m,opt,frames,objective,identity,1000,checkpoint=partial)
  require_exact_state(whole,actual,exclude_training_seconds=True)
 def test_invalid_range_and_cursor_refused_before_mutation(self):
  fixture=fixtures.SustainedLoopTests();m,opt,frames=fixture.fixture();partial,_,_=advance(m,opt,frames,objective,{},47,clock=fixture.clock())
  old={k:v.clone() for k,v in m.state_dict().items()}
  for target in [46,8048,32001,True]:
   with self.assertRaises(ValueError):reference_chunk(m,opt,frames,objective,{},target,checkpoint=partial)
  bad=dict(partial);bad['frame_cursor']=0
  with self.assertRaises(ValueError):reference_chunk(m,opt,frames,objective,{},48,checkpoint=bad)
  for k,v in old.items():self.assertTrue(torch.equal(v,m.state_dict()[k]))
 def test_initial_and_exact_terminal_with_no_extra_update(self):
  fixture=fixtures.SustainedLoopTests();identity={};m,opt,frames=fixture.fixture()
  initial=reference_chunk(m,opt,frames,objective,identity,0)
  require_exact_state(initial,reference_chunk(m,opt,frames,objective,identity,0,checkpoint=initial))
  with self.assertRaises(ValueError):reference_chunk(m,opt,frames[:-1],objective,identity,1)
  with self.assertRaises(ValueError):reference_chunk(m,opt,frames,lambda o,t:{'total':o['value'].sum()*float('nan')},identity,1)
if __name__=='__main__':unittest.main()
