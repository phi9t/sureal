import unittest,torch
from detection.expanded_batch.sparse_sets import window_sets,pool_tokens
from detection.expanded_batch.spatial_modules import SparseBlock

class SparseContract(unittest.TestCase):
 def setUp(self):torch.manual_seed(17);torch.set_num_threads(2)
 def test_shifted_bounded_sets_cover_each_token_once(self):
  coordinates=torch.tensor([[b,0,y,x] for b in range(2) for y in range(10) for x in [0,3,7,8,15]])
  for shift,axis in [(0,'x'),(4,'y')]:
   indices,valid=window_sets(coordinates,window=8,max_tokens=7,shift=shift,axis=axis);flat=indices[valid];self.assertEqual(sorted(flat.tolist()),list(range(len(coordinates))));self.assertTrue(torch.all(indices[~valid]==-1));self.assertEqual(indices.shape[1],7)
   for row,mask in zip(indices,valid):
    points=coordinates[row[mask]];keys={(int(p[0]),(int(p[2])-shift)//8,(int(p[3])-shift)//8) for p in points};self.assertEqual(len(keys),1)
 def test_duplicate_coordinates_rejected(self):
  with self.assertRaises(ValueError):window_sets(torch.zeros(2,4,dtype=torch.long))
 def test_pooling_values_coordinates_and_gradients(self):
  coords=torch.tensor([[0,0,0,0],[0,0,1,1],[0,0,2,2]]);features=torch.tensor([[1.,3.],[3.,5.],[7.,9.]],requires_grad=True);pooled,coarse=pool_tokens(features,coords);torch.testing.assert_close(pooled,torch.tensor([[2.,4.],[7.,9.]]));self.assertEqual(coarse.tolist(),[[0,0,0,0],[0,0,1,1]]);pooled.sum().backward();torch.testing.assert_close(features.grad,torch.tensor([[.5,.5],[.5,.5],[1.,1.]]))
 def test_sparse_block_is_permutation_equivariant_with_finite_gradients(self):
  coords=torch.tensor([[0,0,y,x] for y in range(5) for x in [0,2,8]]);features=torch.rand(len(coords),64,requires_grad=True);block=SparseBlock(64,spacing=.5,axis='y',shift=4);actual=block(features,coords);permutation=torch.randperm(len(coords));torch.testing.assert_close(block(features[permutation],coords[permutation]),actual[permutation],rtol=1e-5,atol=1e-6);actual.square().sum().backward();self.assertTrue(torch.isfinite(features.grad).all());self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in block.parameters()))
