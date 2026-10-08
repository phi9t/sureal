import unittest,torch
from detection.packed_point_features import packed_point_features
class PackedFeaturesTests(unittest.TestCase):
 def test_source_order_padding_and_gradients(self):
  features=torch.arange(15,dtype=torch.float32).reshape(5,3).requires_grad_();indices=torch.tensor([[4,0,-1],[3,2,-1]]);counts=torch.tensor([2,2]);packed=packed_point_features(features,indices,counts)
  torch.testing.assert_close(packed[:,:2],features[indices[:,:2]],rtol=0,atol=0);self.assertTrue((packed[:,2]==0).all());packed.sum().backward()
  torch.testing.assert_close(features.grad,torch.tensor([[1.,1.,1.],[0.,0.,0.],[1.,1.,1.],[1.,1.,1.],[1.,1.,1.]]),rtol=0,atol=0)
 def test_invalid_correspondence(self):
  features=torch.ones(5,3);counts=torch.tensor([2,2])
  for indices in [torch.tensor([[4,0,1],[3,2,-1]]),torch.tensor([[4,0,-1],[4,2,-1]]),torch.tensor([[5,0,-1],[3,2,-1]]),torch.tensor([[4,-1,-1],[3,2,-1]])]:
   with self.assertRaises(ValueError):packed_point_features(features,indices,counts)
if __name__=='__main__':unittest.main()
