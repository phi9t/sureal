import random,unittest
import numpy as np
import torch
from cohort.sustained_loop import advance
from cohort.sustained_state import capture_state

class Toy(torch.nn.Module):
 def __init__(self):super().__init__();self.layer=torch.nn.Linear(2,1)
 def forward(self,x,*,batch_size):return {'value':self.layer(x)*torch.rand(())}

def objective(output,target):
 return {'total':(output['value']-target).square().mean()}

class SustainedLoopTests(unittest.TestCase):
 def fixture(self):
  torch.manual_seed(17);random.seed(17);np.random.seed(17);m=Toy();opt=torch.optim.Adam(m.parameters(),lr=1e-4,foreach=False)
  frames=[((torch.tensor([[i/16.,1.]]),),torch.tensor([[.2]])) for i in range(16)];return m,opt,frames
 def clock(self):
  state=[0.]
  def now():state[0]+=.001;return state[0]
  return now
 def test_round_robin_and_resumed_model_adam_rng_match(self):
  m,opt,frames=self.fixture();identity={'manifest':'a'*64};whole,records,reason=advance(m,opt,frames,objective,identity,35,clock=self.clock());self.assertEqual([r['frame_index'] for r in records],[i%16 for i in range(35)])
  n,other,frames=self.fixture();first,_,_=advance(n,other,frames,objective,identity,19,clock=self.clock());resumed,records,_=advance(n,other,frames,objective,identity,35,checkpoint=first,clock=self.clock())
  for key in whole['model']:self.assertTrue(torch.equal(whole['model'][key],resumed['model'][key]))
  for pid in whole['optimizer']['state']:
   for key in whole['optimizer']['state'][pid]:self.assertTrue(torch.equal(whole['optimizer']['state'][pid][key],resumed['optimizer']['state'][pid][key]))
  self.assertTrue(torch.equal(whole['rng']['torch'],resumed['rng']['torch']));self.assertEqual([r['frame_index'] for r in records],[i%16 for i in range(19,35)]);self.assertEqual(resumed['frame_cursor'],3)
 def test_invalid_update_and_incomplete_frame_batch_refused(self):
  m,opt,frames=self.fixture()
  for target in [-1,32001,1.5,True]:
   with self.assertRaises(ValueError):advance(m,opt,frames,objective,{},target)
  with self.assertRaises(ValueError):advance(m,opt,frames[:-1],objective,{},1)
 def test_nonfinite_loss_and_time_budget_fail_closed(self):
  m,opt,frames=self.fixture()
  with self.assertRaises(ValueError):advance(m,opt,frames,lambda o,t:{'total':o['value'].sum()*float('nan')},{},1)
  saved=capture_state(m,opt,{},0,7200.)
  found,records,reason=advance(m,opt,frames,objective,{},1,checkpoint=saved);self.assertEqual((found['steps'],records,reason),(0,[],'time_cap'))

 def test_rewind_refused_before_model_or_optimizer_mutation(self):
  m,opt,frames=self.fixture();older,_,_=advance(m,opt,frames,objective,{},19,clock=self.clock());current,_,_=advance(m,opt,frames,objective,{},35,checkpoint=older,clock=self.clock())
  with self.assertRaises(ValueError):advance(m,opt,frames,objective,{},18,checkpoint=older)
  for key,value in current['model'].items():self.assertTrue(torch.equal(value,m.state_dict()[key]))
  for pid,values in current['optimizer']['state'].items():
   for key,value in values.items():self.assertTrue(torch.equal(value,opt.state_dict()['state'][pid][key]))
 def test_reserved_budget_stop_preserves_actual_progress(self):
  m,opt,frames=self.fixture();saved=capture_state(m,opt,{},0,7198.8);found,records,reason=advance(m,opt,frames,objective,{},10,checkpoint=saved,clock=iter([0.,.3]).__next__)
  self.assertEqual(found['steps'],1);self.assertEqual(len(records),1);self.assertAlmostEqual(found['training_seconds'],7199.1);self.assertEqual(reason,'time_cap')
 def test_atomic_overrun_is_preserved_and_cannot_be_promoted(self):
  m,opt,frames=self.fixture();found,records,reason=advance(m,opt,frames,objective,{},10,clock=iter([0.,7201.]).__next__)
  self.assertEqual(found['steps'],1);self.assertEqual(len(records),1);self.assertEqual(found['training_seconds'],7201.);self.assertEqual(reason,'resource_overrun')

if __name__=='__main__':unittest.main()
