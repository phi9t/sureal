import unittest,numpy as np
from segmentation.point_mask_relation import point_mask_relation
class RelationTests(unittest.TestCase):
 def test_two_slots_untyped_and_visibility_absence(self):
  masks=np.zeros((2,3,4),dtype=bool);masks[0,1,1]=True;masks[1,0,0]=True
  cp=np.array([[1.,1.,1.,2.,1.,1.],[1.,0.,0.,1.,1.,1.],[1.,9.,9.,0.,0.,0.]])
  r=point_mask_relation(cp,masks,camera=1,visibility=None);np.testing.assert_array_equal(r['projected_hits'],[[1,0],[1,1],[0,0]]);self.assertFalse(r['visible_hits'].any());self.assertFalse(r['visibility_supplied']);self.assertNotIn('semantic_classes',r)
  v=np.array([[False,True],[True,False],[True,True]]);r=point_mask_relation(cp,masks,camera=1,visibility=v);np.testing.assert_array_equal(r['visible_hits'],[[0,0],[0,1],[0,0]])
 def test_fractional_projection_and_bad_visibility_refused(self):
  masks=np.ones((1,3,4),dtype=bool)
  with self.assertRaises(ValueError):point_mask_relation(np.array([[1.,1.1,0.,0.,0.,0.]]),masks,camera=1,visibility=None)
  with self.assertRaises(ValueError):point_mask_relation(np.zeros((1,6),dtype=int),masks,camera=1,visibility=np.ones((1,2)))
if __name__=='__main__':unittest.main()
