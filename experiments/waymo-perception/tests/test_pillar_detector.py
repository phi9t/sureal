import unittest
import torch
from pipeline.pillar_detector import PillarDetector


class PillarDetectorTests(unittest.TestCase):
    def test_native_pillars_to_stride_two_anchor_outputs_and_backward(self):
        torch.manual_seed(17)
        model=PillarDetector(nx=16,ny=24,classes=4,anchors_per_cell=2,cell_size=(.5,.5),origin=(-4.,-6.)).eval()
        points=torch.tensor([[[0.,0.,0.,.5],[.1,.1,.1,.7]],[[1.,1.,0.,.4],[1.2,1.1,.2,.5]]])
        counts=torch.tensor([2,2]);coordinates=torch.tensor([[0,0,12,8],[0,0,14,10]])
        output=model(points,counts,coordinates,batch_size=1)
        self.assertEqual(output['classification'].shape,(1,192,4))
        self.assertEqual(output['box_residuals'].shape,(1,192,7))
        self.assertEqual(output['direction'].shape,(1,192,2))
        sum(value.square().mean() for value in output.values()).backward()
        for parameter in model.parameters():
            self.assertIsNotNone(parameter.grad)
            self.assertTrue(torch.isfinite(parameter.grad).all())


if __name__=='__main__':unittest.main()
