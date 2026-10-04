import unittest
import numpy as np
from pipeline.camera_coordinates import pixel_centers,box_edges
class CoordinateTests(unittest.TestCase):
 def test_half_pixel_and_distinct_axis_scales(self):
  x=np.array([[0.,0.],[6.,4.]])
  y=pixel_centers(x,original_hw=(5,7),resized_hw=(3,4),pad_xy=(2,1))
  np.testing.assert_allclose(y,[[2+2/7-.5,1+.3-.5],[2+26/7-.5,1+2.7-.5]])
  np.testing.assert_allclose(pixel_centers(y,original_hw=(5,7),resized_hw=(3,4),pad_xy=(2,1),inverse=True),x,atol=1e-14)
 def test_box_edges_and_roundtrip(self):
  b=np.array([[0.,0.,7.,5.],[1.,2.,4.,3.]])
  y=box_edges(b,original_hw=(5,7),resized_hw=(3,4),pad_xy=(2,1));np.testing.assert_allclose(y[0],[2.,1.,6.,4.]);np.testing.assert_allclose(box_edges(y,original_hw=(5,7),resized_hw=(3,4),pad_xy=(2,1),inverse=True),b,atol=1e-14)
 def test_no_implicit_clipping_and_empty(self):
  x=np.array([[-2.,8.]])
  y=pixel_centers(x,original_hw=(5,7),resized_hw=(3,4),pad_xy=(0,0));self.assertLess(y[0,0],0);self.assertGreater(y[0,1],3)
  self.assertEqual(box_edges(np.zeros((0,4)),original_hw=(5,7),resized_hw=(3,4),pad_xy=(0,0)).shape,(0,4))
 def test_invalid_refused(self):
  for kwargs in [{'original_hw':(0,7),'resized_hw':(3,4),'pad_xy':(0,0)},{'original_hw':(5,7),'resized_hw':(3.5,4),'pad_xy':(0,0)},{'original_hw':(5,7),'resized_hw':(3,4),'pad_xy':(-1,0)}]:
   with self.assertRaises(ValueError):pixel_centers(np.zeros((1,2)),**kwargs)
  with self.assertRaises(ValueError):box_edges(np.array([[2.,0.,1.,3.]]),original_hw=(5,7),resized_hw=(3,4),pad_xy=(0,0))
if __name__=='__main__':unittest.main()
