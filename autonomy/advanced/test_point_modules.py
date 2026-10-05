import unittest,torch,numpy as np
from detection.pillar_encoder import PillarFeatureNet,decorate
from advanced.point_modules import RaggedPillar,PointAttention,PointMLP,decorate_ragged

class PointContract(unittest.TestCase):
 def setUp(self):torch.manual_seed(17);torch.set_num_threads(2)
 def test_ragged_decoration_and_gradients_match_literal_segments(self):
  points=torch.tensor([[0.,0.,0.,1.],[.1,.2,.3,2.],[1.,1.,1.,3.]],requires_grad=True);counts=torch.tensor([2,1]);coords=torch.tensor([[0,0,256,256],[0,0,260,260]])
  actual=decorate_ragged(points,counts,coords,cell_size=(.25,.25),origin=(-64.,-64.));expected=[]
  for part,coord in [(points[:2],coords[0]),(points[2:],coords[1])]:
   mean=part[:,:3].mean(0);center=torch.stack(((coord[3]+.5)*.25-64,(coord[2]+.5)*.25-64));expected.append(torch.cat((part,part[:,:3]-mean,part[:,:2]-center),1))
  expected=torch.cat(expected);torch.testing.assert_close(actual,expected);a=torch.autograd.grad(actual.square().sum(),points,retain_graph=True)[0];b=torch.autograd.grad(expected.square().sum(),points)[0];torch.testing.assert_close(a,b)
 def test_ragged_eval_matches_uncapped_fixed_pillars(self):
  raw=torch.rand(2,3,4);counts=torch.tensor([3,3]);coords=torch.tensor([[0,0,256,256],[0,0,257,257]]);base=PillarFeatureNet().eval();ragged=RaggedPillar(base).eval();packed=decorate(raw,counts,coords,cell_size=(.25,.25),origin=(-64.,-64.));flat=decorate_ragged(raw.reshape(-1,4),counts,coords,cell_size=(.25,.25),origin=(-64.,-64.));torch.testing.assert_close(ragged(flat,counts),base(packed))
 def test_point_attention_and_control_are_masked_permutation_invariant(self):
  counts=torch.tensor([3,2]);values=torch.rand(2,5,9);values[:,3:]=0;values[1,2]=0;permutation=torch.tensor([2,0,1,4,3]);mask=torch.arange(5)[None]<counts[:,None]
  for factory in [PointAttention,PointMLP]:
   module=factory(PillarFeatureNet()).eval();out=module(values,counts);torch.testing.assert_close(out,module(torch.cat([values,torch.zeros(2,2,9)],1),counts),rtol=1e-5,atol=1e-6)
   shuffled=values.clone();shuffled[0,:3]=values[0,torch.tensor([2,0,1])];shuffled[1,:2]=values[1,torch.tensor([1,0])];torch.testing.assert_close(out,module(shuffled,counts),rtol=1e-5,atol=1e-6)
   out.square().sum().backward();self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in module.parameters()))
 def test_attention_control_parameter_count_matches(self):
  a=PointAttention(PillarFeatureNet());b=PointMLP(PillarFeatureNet());self.assertEqual(sum(p.numel() for p in a.parameters()),sum(p.numel() for p in b.parameters()))
 def test_ragged_invalid_lengths_rejected(self):
  with self.assertRaises(ValueError):decorate_ragged(torch.zeros(3,4),torch.tensor([2,2]),torch.zeros(2,4,dtype=torch.long),cell_size=(.25,.25),origin=(-64.,-64.))
