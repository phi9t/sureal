import copy,unittest
import numpy as np
import torch
from cohort.sustained_replay_values import require_exact_state,require_exact_heads

class ReplayValueTests(unittest.TestCase):
 def test_every_nested_state_value_is_compared(self):
  state={'model':{'w':torch.tensor([1.])},'optimizer':{'state':{0:{'exp_avg':torch.tensor([2.])}}},'rng':{'python':(3,(4,5),None),'torch':torch.tensor([6],dtype=torch.uint8)},'steps':19,'frame_cursor':3,'identity':{'recipe':'baseline'}}
  require_exact_state(state,copy.deepcopy(state))
  for path in [('model','w'),('optimizer','state',0,'exp_avg'),('rng','torch')]:
   altered=copy.deepcopy(state);node=altered
   for key in path[:-1]:node=node[key]
   node[path[-1]][0]+=1
   with self.assertRaises(ValueError):require_exact_state(state,altered)
  for key in ['steps','frame_cursor','identity']:
   altered=copy.deepcopy(state);altered.pop(key)
   with self.assertRaises(ValueError):require_exact_state(state,altered)
 def test_elapsed_time_is_the_only_explicit_exclusion(self):
  require_exact_state({'training_seconds':1.,'steps':19},{'training_seconds':2.,'steps':19},exclude_training_seconds=True)
  with self.assertRaises(ValueError):require_exact_state({'training_seconds':1.},{'training_seconds':2.})
 def test_dtype_shape_finiteness_and_container_type(self):
  for left,right in [(torch.tensor([1.]),torch.tensor([1.],dtype=torch.float64)),(torch.tensor([1.]),torch.tensor([[1.]])),(float('nan'),float('nan')),([1],(1,))]:
   with self.assertRaises(ValueError):require_exact_state(left,right)
 def test_all_head_channels_and_values(self):
  heads={'classification':np.zeros((2,4),dtype=np.float32),'box':np.ones((2,7),dtype=np.float32)}
  require_exact_heads(heads,copy.deepcopy(heads))
  for altered in [{'classification':heads['classification']},{**heads,'box':heads['box'].astype(np.float64)},{**heads,'box':np.full((2,7),np.nan,dtype=np.float32)}]:
   with self.assertRaises(ValueError):require_exact_heads(heads,altered)
  changed=copy.deepcopy(heads);changed['box'][0,0]+=1
  with self.assertRaises(ValueError):require_exact_heads(heads,changed)
if __name__=='__main__':unittest.main()
