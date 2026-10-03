import unittest,torch
from torch.nn import functional as F
from pipeline.pillar_encoder import PillarFeatureNet
from advanced.range_fusion import RangePillar,RangeFeatures,bilinear_resize

class RangeContract(unittest.TestCase):
 def setUp(self):torch.manual_seed(17);torch.set_num_threads(2)
 def test_bilinear_values_and_gradients_match_independent_builtin(self):
  x=torch.rand(1,4,3,5,requires_grad=True);actual=bilinear_resize(x,(7,8));expected=F.interpolate(x,size=(7,8),mode='bilinear',align_corners=False);torch.testing.assert_close(actual,expected,rtol=2e-5,atol=1e-6);a=torch.autograd.grad(actual.square().sum(),x,retain_graph=True)[0];b=torch.autograd.grad(expected.square().sum(),x)[0];torch.testing.assert_close(a,b,rtol=2e-5,atol=1e-6)
 def test_frontend_returns_only_physical_features_and_masks_invalid_pixels(self):
  model=RangeFeatures();raw=torch.rand(2,3,4,6);valid=torch.ones(2,4,6,dtype=torch.bool);valid[:,0,0]=False;features=model(raw,valid);self.assertEqual(features.shape,(2,32,4,6));self.assertTrue(torch.all(features[:,:,0,0]==0));features.square().sum().backward();self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters()))
 def test_zero_fusion_equivalence_then_frontend_receives_gradients(self):
  base=PillarFeatureNet().eval();module=RangePillar(base).eval();decorated=torch.rand(2,3,9);counts=torch.tensor([2,3]);pixels=torch.tensor([[[0,0,1],[9,1,2],[-1,-1,-1]],[[0,1,1],[9,2,2],[0,2,3]]]);aux={'range_pixels':pixels}
  for l in range(1,6):
   for r in (1,2):aux[f'range_raw_{l}_{r}']=torch.rand(1,3,4,6);aux[f'range_valid_{l}_{r}']=torch.ones(1,4,6,dtype=torch.bool)
  module.set_observations(aux);actual=module(decorated,counts);torch.testing.assert_close(actual,base(decorated),rtol=0,atol=0);actual.sum().backward();self.assertTrue(module.projection.weight.grad.abs().sum()>0)
  module.zero_grad();module.projection.weight.data.fill_(.01);module(decorated,counts).square().sum().backward();self.assertTrue(any(p.grad is not None and p.grad.abs().sum()>0 for p in module.frontend.parameters()));self.assertFalse(any(k.startswith('range_raw_') for k in module.state_dict()))
 def test_padded_or_unknown_range_id_is_rejected(self):
  module=RangePillar(PillarFeatureNet());aux={'range_pixels':torch.tensor([[[10,0,0]]])}
  with self.assertRaises(ValueError):module.set_observations(aux)
