import unittest,numpy as np
from pipeline.foreground_support import foreground_support,selection_diagnostics
class SupportTests(unittest.TestCase):
 def test_rotated_boxes_boundary_overlap_and_native_classes(self):
  points=np.array([[0.,1.5,0.],[0.,2.,0.],[1.5,0.,0.],[0.,0.,2.]])
  boxes=np.array([[0,0,0,4,2,2,np.pi/2],[0,1.5,0,1,1,1,0.]])
  t=foreground_support(points,boxes,np.array([1,2]));np.testing.assert_array_equal(t['object_point_indices'][0],[0,1]);np.testing.assert_array_equal(t['object_point_indices'][1],[0,1])
  np.testing.assert_array_equal(t['class_membership'][:,0],[1,1,0,0]);np.testing.assert_array_equal(t['class_membership'][:,1],[1,1,0,0])
 def test_selection_recall_and_no_observation_denominator(self):
  p=np.array([[0.,0.,0.],[1.,0.,0.],[5.,0.,0.]])
  b=np.array([[0,0,0,4,2,2,0],[20,0,0,1,1,1,0],[5,0,0,1,1,1,0]])
  t=foreground_support(p,b,np.array([1,1,2]));d=selection_diagnostics(t,np.array([True,False,False]),minimum_points=2)
  self.assertEqual(d['classes']['1']['point_recall'],.5);self.assertEqual(d['classes']['1']['objects_without_observed_support'],1);self.assertEqual(d['classes']['1']['supported_objects'],1);self.assertEqual(d['classes']['1']['objects_retaining_one'],1);self.assertEqual(d['classes']['1']['objects_retaining_minimum'],0)
  self.assertEqual(d['classes']['2']['point_recall'],0);self.assertIsNone(d['classes']['3']['point_recall']);self.assertEqual(d['selected_points'],1)
 def test_invalid_inputs(self):
  with self.assertRaises(ValueError):foreground_support(np.zeros((1,3)),np.zeros((1,7)),np.array([1]))
  with self.assertRaises(ValueError):foreground_support(np.zeros((1,3)),np.array([[0,0,0,1,1,1,0]]),np.array([0]))
  t=foreground_support(np.zeros((1,3)),np.empty((0,7)),np.empty(0,dtype=int))
  with self.assertRaises(ValueError):selection_diagnostics(t,np.array([1]),minimum_points=1)
if __name__=='__main__':unittest.main()
