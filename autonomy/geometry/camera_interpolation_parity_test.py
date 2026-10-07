"""Independent actual Torch resampling versus coordinate geometry."""
import unittest
import numpy as np
import torch
from torch.nn import functional as F
from geometry.camera_coordinates import pixel_centers,box_edges
class InterpolationTests(unittest.TestCase):
 def test_actual_bilinear_ramp_coordinates_and_padding(self):
  h,w=5,7
  yy,xx=torch.meshgrid(torch.arange(h,dtype=torch.float64),torch.arange(w,dtype=torch.float64),indexing='ij')
  image=torch.stack((xx,yy))[None]
  for rh,rw in [(3,4),(10,14)]:
   with self.subTest(size=(rh,rw)):
    resized=F.interpolate(image,size=(rh,rw),mode='bilinear',align_corners=False,antialias=False)
    padded=F.pad(resized,(2,1,1,2),value=-999.)
    v,u=np.meshgrid(np.arange(rh),np.arange(rw),indexing='ij');output=np.column_stack((u.ravel()+2,v.ravel()+1))
    original=pixel_centers(output,original_hw=(h,w),resized_hw=(rh,rw),pad_xy=(2,1),inverse=True)
    # Actual interpolator clamps its sampling at image boundaries.
    expected=np.column_stack((np.clip(original[:,0],0,w-1),np.clip(original[:,1],0,h-1)))
    actual=padded[0,:,1:1+rh,2:2+rw].permute(1,2,0).reshape(-1,2).numpy()
    np.testing.assert_allclose(actual,expected,atol=1e-12)
    np.testing.assert_allclose(pixel_centers(original,original_hw=(h,w),resized_hw=(rh,rw),pad_xy=(2,1)),output,atol=1e-12)
    self.assertTrue(torch.equal(padded[0,:,0,:],torch.full_like(padded[0,:,0,:],-999.)))
 def test_edge_coordinates_do_not_use_center_shift(self):
  box=np.array([[0.,0.,7.,5.]])
  transformed=box_edges(box,original_hw=(5,7),resized_hw=(3,4),pad_xy=(2,1))
  np.testing.assert_array_equal(transformed,[[2.,1.,6.,4.]])
  centers=pixel_centers(box.reshape(-1,2),original_hw=(5,7),resized_hw=(3,4),pad_xy=(2,1)).reshape(1,4)
  self.assertFalse(np.allclose(transformed,centers))
if __name__=='__main__':unittest.main()
