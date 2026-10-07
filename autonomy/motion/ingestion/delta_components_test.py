import unittest
import numpy as np
from motion.ingestion.delta_components import decode_components
class DeltaTests(unittest.TestCase):
 def test_channel_major_cross_channel_delta_and_zero_leading_run(self):
  out=decode_components([2,2,2],[.5,2],[0,1,2,1,1,1,1,1],[2,0,-5,7]);np.testing.assert_array_equal(out,np.array([[[0,-6],[1,0]],[[1,8],[0,0]]],dtype=float))
 def test_all_zero_and_all_nonzero(self):
  np.testing.assert_array_equal(decode_components([1,2,1],[.25],[0,2],[]),np.zeros((1,2,1)));np.testing.assert_array_equal(decode_components([1,2,1],[.5],[2],[2,2]),np.array([[[1],[2]]]))
 def test_shape_precision_mask_and_residual_refusals(self):
  cases=[([1,2],[1],[2],[1,1]),([0,2,1],[1],[2],[1,1]),([1,2,1],[0],[2],[1,1]),([1,2,1],[float('nan')],[2],[1,1]),([1,2,1],[1,1],[2],[1,1]),([1,2,1],[1],[1],[1]),([1,2,1],[1],[2],[1]),([1,2,1],[1],[-2],[1,1]),([1,2,1],[1],[2],[1.5,1]),([1,2,1],[1],[2],[2**63-1,1])]
  for args in cases:
   with self.subTest(args=args),self.assertRaises(ValueError):decode_components(*args)
 def test_limit_is_checked_before_dense_allocation(self):
  with self.assertRaises(ValueError):decode_components([100,100,4],[1]*4,[40000],[1]*40000,max_values=100)
if __name__=='__main__':unittest.main()
