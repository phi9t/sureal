import unittest
import numpy as np
import torch
from range_view.sparse_window_attention import SparseWindowAttention

class SparseWindowAttentionTests(unittest.TestCase):
    def test_uniform_attention_ignores_padding_and_other_windows(self):
        layer=SparseWindowAttention(2,1,window_shape=(2,2),shift=(0,0))
        with torch.no_grad():
            layer.attention.in_proj_weight.zero_();layer.attention.in_proj_weight[4:6]=torch.eye(2)
            layer.attention.in_proj_bias.zero_();layer.attention.out_proj.weight.copy_(torch.eye(2));layer.attention.out_proj.bias.zero_()
        features=torch.tensor([[1.,2.],[3.,4.],[5.,6.],[99.,100.]],requires_grad=True)
        coordinates=np.array([[0,0,0],[0,0,1],[0,1,1],[0,0,2]])
        result=layer(features,coordinates)
        torch.testing.assert_close(result,torch.tensor([[3.,4.],[3.,4.],[3.,4.],[99.,100.]]))
        result.sum().backward()
        self.assertTrue(torch.isfinite(features.grad).all())
        self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in layer.parameters()))
    def test_permutation_equivariance_and_batch_isolation(self):
        torch.manual_seed(17);layer=SparseWindowAttention(8,2,window_shape=(2,2),shift=(1,1))
        coordinates=np.array([[0,0,0],[0,0,1],[0,1,1],[1,0,0]])
        features=torch.randn(4,8);order=np.array([2,0,3,1])
        torch.testing.assert_close(layer(features[order],coordinates[order]),layer(features,coordinates)[order],rtol=1e-5,atol=1e-6)
        changed=features.clone();changed[3]+=100
        torch.testing.assert_close(layer(changed,coordinates)[:3],layer(features,coordinates)[:3])
    def test_empty_support_and_shape_refusal(self):
        layer=SparseWindowAttention(8,2,window_shape=(2,2),shift=(0,0))
        self.assertEqual(layer(torch.empty((0,8)),np.empty((0,3),dtype=np.int64)).shape,(0,8))
        with self.assertRaises(ValueError):layer(torch.ones(2,7),np.array([[0,0,0],[0,0,1]]))

if __name__ == '__main__':
    unittest.main()
