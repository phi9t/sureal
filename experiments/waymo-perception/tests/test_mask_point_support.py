import unittest
import numpy as np
from pipeline.mask_point_support import mask_point_support
class SupportTests(unittest.TestCase):
 def prompt(self,identity='p',category=2):return {'prompt_id':identity,'camera_class':category,'mask':np.array([[False,True,False],[False,False,True]])}
 def test_boolean_array_like_masks_normalized_without_mutation(self):
  mask=[[False,True,False],[False,False,True]]
  p={"prompt_id":"p","camera_class":2,"mask":mask}
  r=mask_point_support(np.array([[1,1,0,0,0,0]]),np.array([[True,False]]),{1:[p]},origin="predicted-mask")
  self.assertEqual(r["camera_classes"].tolist(),[2]);self.assertTrue(r["support"][0]);self.assertIs(p["mask"],mask)
 def test_native_uv_and_preserved_order(self):
  cp=np.array([[1,1,0,0,0,0],[1,2,1,0,0,0],[1,0,0,0,0,0]])
  r=mask_point_support(cp,np.array([[True,False]]*3),{1:[self.prompt()]},origin='predicted-mask')
  self.assertEqual(r['camera_classes'].tolist(),[2,2,0]);self.assertEqual(r['support'].tolist(),[True,True,False]);self.assertEqual(r['points'],3)
 def test_visibility_bounds_missing_and_no_clipping(self):
  cp=np.array([[1,1,0,0,0,0],[1,-1,0,0,0,0],[2,1,0,0,0,0],[0,0,0,0,0,0]])
  r=mask_point_support(cp,np.zeros((4,2),dtype=bool),{1:[self.prompt()]},origin='predicted-mask');self.assertFalse(r['support'].any())
  r=mask_point_support(cp,np.ones((4,2),dtype=bool),{1:[self.prompt()]},origin='predicted-mask');self.assertEqual(r['support'].tolist(),[True,False,False,False])
 def test_overlap_and_cross_camera_conflict(self):
  cp=np.array([[1,1,0,2,1,0]])
  for masks in [{1:[self.prompt(),self.prompt('other')]},{1:[self.prompt()],2:[self.prompt(category=3)]}]:
   r=mask_point_support(cp,np.ones((1,2),dtype=bool),masks,origin='predicted-mask');self.assertFalse(r['support'][0]);self.assertIn('conflict',r['reasons'][0])
  r=mask_point_support(cp,np.ones((1,2),dtype=bool),{1:[self.prompt()],2:[self.prompt()]},origin='predicted-mask');self.assertTrue(r['support'][0])
 def test_invalid_and_annotation_origins_refused(self):
  cp=np.zeros((0,6),dtype=int)
  with self.assertRaises(ValueError):mask_point_support(cp,np.zeros((0,2),dtype=bool),{},origin='groundtruth')
  with self.assertRaises(ValueError):mask_point_support(np.zeros((1,6)),np.ones((1,2),dtype=bool),{},origin='predicted-mask')
  with self.assertRaises(ValueError):mask_point_support(np.array([[6,0,0,0,0,0]]),np.ones((1,2),dtype=bool),{},origin='predicted-mask')
if __name__=='__main__':unittest.main()
