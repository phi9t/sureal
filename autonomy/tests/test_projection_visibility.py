import unittest
import numpy as np
from pipeline.projection_visibility import measured_projection_visibility

class ProjectionVisibilityTests(unittest.TestCase):
    def test_nearest_measured_depth_and_tolerance_preserve_all_slots(self):
        projection=np.array([[1,2,3,0,0,0],[1,2,3,0,0,0],[1,2,3,0,0,0]])
        depth=np.array([[10,np.nan],[10.05,np.nan],[20,np.nan]])
        result=measured_projection_visibility(projection,depth,{1:(8,8)},depth_tolerance_m=.1)
        np.testing.assert_array_equal(result['supported'],[[True,False],[True,False],[False,False]])
        self.assertEqual(result['reasons'][2,0],'behind_measured_surface')
        self.assertEqual(result['reasons'][0,1],'no_projection')
        self.assertEqual(result['supported'].shape,(3,2))
    def test_camera_names_and_pixel_bounds_are_independent(self):
        projection=np.array([[1,0,0,2,0,0],[1,0,0,2,2,0],[3,0,0,1,8,0]])
        depth=np.array([[10,2],[2,2],[1,1]])
        result=measured_projection_visibility(projection,depth,{1:(4,8),2:(2,2)},depth_tolerance_m=0)
        self.assertEqual(result['reasons'][0,0],'behind_measured_surface')
        self.assertTrue(result['supported'][0,1])
        self.assertEqual(result['reasons'][1,1],'outside_image')
        self.assertEqual(result['reasons'][2,0],'camera_unavailable')
        self.assertEqual(result['reasons'][2,1],'outside_image')
    def test_invalid_forward_depth_is_unknown_and_bad_contract_refused(self):
        projection=np.array([[1,0,0,0,0,0],[1,1,0,0,0,0]])
        result=measured_projection_visibility(projection,np.array([[0,np.nan],[np.inf,np.nan]]),{1:(2,2)},depth_tolerance_m=0)
        self.assertFalse(result['supported'].any())
        self.assertEqual(result['reasons'][0,0],'invalid_forward_depth')
        with self.assertRaises(ValueError):
            measured_projection_visibility(projection,np.ones((2,2)),{1:(2,2)},depth_tolerance_m=-1)
