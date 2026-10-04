import unittest,torch
from pipeline.pillar_detector import PillarDetector
from pipeline.pillar_encoder import decorate
from pipeline.range_pillar_hybrid import SharedPillarHead,RangePillarFeatureNet
class HybridTests(unittest.TestCase):
 def test_shared_head_matches_original(self):
  torch.manual_seed(17);original=PillarDetector(nx=16,ny=16,classes=3,anchors_per_cell=2,cell_size=(.25,.25),origin=(-2.,-2.)).eval();head=SharedPillarHead(original).eval()
  points=torch.tensor([[[0.,0.,0.,1.],[0.1,0.,0.,.5]],[[1.,1.,0.,1.],[0.,0.,0.,0.]]]);counts=torch.tensor([2,1]);coordinates=torch.tensor([[0,0,8,8],[0,0,12,12]])
  with torch.no_grad():
   features=original.encoder(decorate(points,counts,coordinates,cell_size=(.25,.25),origin=(-2.,-2.)));a=original(points,counts,coordinates,batch_size=1);b=head(features,coordinates,batch_size=1)
  for key in a:torch.testing.assert_close(a[key],b[key],rtol=0,atol=0)
  self.assertIs(head.box_head,original.box_head);self.assertIs(head.class_head,original.class_head)
 def test_augmented_encoding_backward_padding(self):
  model=RangePillarFeatureNet(32);decorated=torch.randn(3,4,9,requires_grad=True);features=torch.randn(3,4,32,requires_grad=True);counts=torch.tensor([4,2,1]);valid=torch.arange(4)[None,:]<counts[:,None]
  a=model(decorated,features,counts);changed=features.detach().clone();changed[~valid]=1000
  torch.testing.assert_close(a,model(decorated,changed,counts),rtol=0,atol=0)
  a.square().mean().backward();self.assertTrue(torch.isfinite(features.grad).all());self.assertTrue((features.grad[~valid]==0).all());self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters()))
 def test_invalid_shape(self):
  with self.assertRaises(ValueError):RangePillarFeatureNet(32)(torch.zeros(2,4,9),torch.zeros(2,4,31),torch.tensor([4,4]))
if __name__=='__main__':unittest.main()
