import unittest,torch
from pipeline.range_frontend import RangeFrontend
class FrontendTests(unittest.TestCase):
 def test_odd_shape_full_support_backward(self):
  torch.manual_seed(17);model=RangeFrontend();raw=torch.rand(2,3,7,13,requires_grad=True);valid=torch.ones(2,7,13,dtype=torch.bool);valid[:,0,0]=False
  result=model(raw,valid)
  self.assertEqual(result['features'].shape,(2,32,7,13));self.assertEqual(result['semantic_logits'].shape,(2,23,7,13));self.assertEqual(result['foreground_logits'].shape,(2,1,7,13))
  for value in result.values():self.assertTrue(torch.isfinite(value).all());self.assertTrue((value[:,:,0,0]==0).all())
  sum(value.square().mean() for value in result.values()).backward()
  self.assertTrue(torch.isfinite(raw.grad).all());self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters()))
 def test_invalid_measurements_do_not_change_valid_output(self):
  model=RangeFrontend().eval();raw=torch.rand(1,3,9,17);valid=torch.ones(1,9,17,dtype=torch.bool);valid[:,2,3]=False
  changed=raw.clone();changed[:,:,2,3]=1000
  with torch.no_grad():
   a=model(raw,valid);b=model(changed,valid)
  for key in a:torch.testing.assert_close(a[key],b[key],rtol=0,atol=0)
 def test_bad_shapes_and_measurements(self):
  model=RangeFrontend()
  for raw,valid in [(torch.zeros(1,4,8,8),torch.ones(1,8,8,dtype=torch.bool)),(torch.zeros(1,3,8,8),torch.ones(1,8,8)),(torch.full((1,3,8,8),float('nan')),torch.ones(1,8,8,dtype=torch.bool))]:
   with self.assertRaises(ValueError):model(raw,valid)
if __name__=='__main__':unittest.main()
