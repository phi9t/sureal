import copy,io,random,unittest
import numpy as np
import torch
from training_execution.sustained_state import capture_state,restore_state

class SustainedStateTests(unittest.TestCase):
 def setup_model(self):
  m=torch.nn.Linear(2,1);return m,torch.optim.Adam(m.parameters(),lr=1e-4,foreach=False)
 def seed(self):torch.manual_seed(17);random.seed(17);np.random.seed(17)
 def updates(self,m,opt,start,end):
  for step in range(start,end):
   x=torch.tensor([[step%16/16.,random.random()+float(np.random.random())]])+torch.rand(1,2);opt.zero_grad();loss=m(x).square().sum();loss.backward();opt.step()
 def equal(self,a,b):
  if isinstance(a,torch.Tensor):self.assertTrue(torch.equal(a,b))
  elif isinstance(a,dict):self.assertEqual(a.keys(),b.keys());[self.equal(a[k],b[k]) for k in a]
  elif isinstance(a,(list,tuple)):self.assertEqual(len(a),len(b));[self.equal(x,y) for x,y in zip(a,b)]
  else:self.assertEqual(a,b)
 def test_serialized_restart_preserves_cycle_adam_and_all_rng(self):
  self.seed();m,opt=self.setup_model();identity={'manifest':'a'*64,'source':'b'*64,'runtime':'c'*64};self.updates(m,opt,0,19);saved=capture_state(m,opt,identity,19,1.25)
  stream=io.BytesIO();torch.save(saved,stream);stream.seek(0);saved=torch.load(stream,weights_only=True)
  self.updates(m,opt,19,35);expected=capture_state(m,opt,identity,35,2.5)
  n,other=self.setup_model();step,cursor,seconds=restore_state(saved,n,other,identity);self.assertEqual((step,cursor,seconds),(19,3,1.25));self.updates(n,other,step,35)
  self.equal(capture_state(n,other,identity,35,2.5),expected)
 def test_changed_identity_cursor_or_optimizer_refused(self):
  self.seed();m,opt=self.setup_model();self.updates(m,opt,0,1);identity={'manifest':'a'*64};saved=capture_state(m,opt,identity,1,.5)
  for mutate in [lambda d:d['identity'].update(manifest='b'*64),lambda d:d.update(frame_cursor=9),lambda d:d['optimizer'].pop('state'),lambda d:d['optimizer']['param_groups'][0].update(lr=.1),lambda d:d.pop('rng')]:
   bad=copy.deepcopy(saved);mutate(bad);n,other=self.setup_model()
   with self.assertRaises(ValueError):restore_state(bad,n,other,identity)
 def test_capture_is_immutable_and_nonfinite_refused(self):
  self.seed();m,opt=self.setup_model();self.updates(m,opt,0,1);saved=capture_state(m,opt,{},1,.5);original=saved['model']['weight'].clone()
  self.updates(m,opt,1,2);self.assertTrue(torch.equal(saved['model']['weight'],original))
  saved['model']['weight'].fill_(float('nan'))
  with self.assertRaises(ValueError):restore_state(saved,m,opt,{})

 def test_restored_optimizer_does_not_alias_checkpoint(self):
  self.seed();m,opt=self.setup_model();self.updates(m,opt,0,1);identity={'manifest':'a'*64};saved=capture_state(m,opt,identity,1,.5);original=copy.deepcopy(saved)
  n,other=self.setup_model();restore_state(saved,n,other,identity);self.updates(n,other,1,2);self.equal(saved,original)
  restore_state(saved,n,other,identity)
 def test_invalid_rng_refused_before_any_live_mutation(self):
  self.seed();m,opt=self.setup_model();self.updates(m,opt,0,1);identity={'manifest':'a'*64};saved=capture_state(m,opt,identity,1,.5);saved['rng']['torch'].zero_()
  n,other=self.setup_model();before=capture_state(n,other,identity,0,0.)
  with self.assertRaises((ValueError,RuntimeError)):restore_state(saved,n,other,identity)
  self.equal(capture_state(n,other,identity,0,0.),before)

if __name__=='__main__':unittest.main()
