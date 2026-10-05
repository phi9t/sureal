import math,unittest
import torch
from segmentation.point_semantic_encoder import PointSemanticEncoder, semantic_loss
class PointTests(unittest.TestCase):
 def test_permutation_singleton_empty_and_feature_contract(self):
  torch.manual_seed(17);m=PointSemanticEncoder().eval();x=torch.tensor([[1.,2.,3.,.5,.2],[4.,5.,6.,.7,.3],[7.,8.,9.,.1,.4]])
  p=m(x);self.assertEqual(p.shape,(3,23));order=torch.tensor([2,0,1]);torch.testing.assert_close(m(x[order]),p[order]);self.assertEqual(m(x[:1]).shape,(1,23));self.assertEqual(m(x[:0]).shape,(0,23))
  for bad in [torch.zeros(1,6),torch.tensor([[float('nan'),0.,0.,0.,0.]])]:
   with self.assertRaises(ValueError):m(bad)
 def test_loss_native_zero_mask_and_known_value(self):
  p=torch.zeros(3,23,requires_grad=True);r=semantic_loss(p,torch.tensor([0,1,22]));self.assertEqual(r['eligible_points'],2);self.assertAlmostEqual(float(r['loss']),math.log(23),places=6);r['loss'].backward();self.assertTrue(torch.equal(p.grad[0],torch.zeros(23)));self.assertTrue(torch.isfinite(p.grad).all())
 def test_missing_and_empty_targets_explicit(self):
  for target in [None,torch.zeros(2,dtype=torch.int64)]:
   p=torch.zeros(2,23,requires_grad=True);r=semantic_loss(p,target);self.assertEqual(r['eligible_points'],0);self.assertEqual(r['labels_present'],target is not None);r['loss'].backward();self.assertTrue(torch.equal(p.grad,torch.zeros_like(p)))
  with self.assertRaises(ValueError):semantic_loss(torch.zeros(1,23),torch.tensor([23]))
 def test_full_encoder_backward(self):
  torch.manual_seed(17);m=PointSemanticEncoder();p=m(torch.randn(8,5));r=semantic_loss(p,torch.tensor([0,1,2,3,4,5,21,22]));r['loss'].backward()
  for x in m.parameters():self.assertIsNotNone(x.grad);self.assertTrue(torch.isfinite(x.grad).all())
if __name__=='__main__':unittest.main()
