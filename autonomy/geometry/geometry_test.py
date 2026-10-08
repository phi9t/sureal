import unittest
import numpy as np
from geometry.geometry import range_to_points

class NativeRangeGeometryTests(unittest.TestCase):
    def test_axial_ray_and_row_order(self):
        ri=np.zeros((2,1,4));ri[...,0]=2
        result=range_to_points(ri,{'extrinsic':np.eye(4),'inclinations':[0,np.pi/2]},return_index=1,motion_policy='uncompensated')
        np.testing.assert_allclose(result['xyz'],[[0,0,2],[2,0,0]],atol=1e-6)
        self.assertEqual(result['pixels'].tolist(),[[0,0],[1,0]])

    def test_yaw_correction_and_invalid_mask(self):
        ri=np.zeros((1,4,4));ri[...,0]=[2,0,np.nan,2]
        e=np.eye(4);e[:3,:3]=[[0,-1,0],[1,0,0],[0,0,1]];e[:3,3]=[1,2,3]
        r=range_to_points(ri,{'extrinsic':e,'inclinations':[0]},return_index=2,motion_policy='uncompensated')
        np.testing.assert_allclose(r['xyz'],[[1-np.sqrt(2),2+np.sqrt(2),3],[1-np.sqrt(2),2-np.sqrt(2),3]],atol=1e-6)
        self.assertEqual(r['pixels'].tolist(),[[0,0],[0,3]])

    def test_pose_compensation_and_second_return(self):
        ri=np.zeros((1,1,4));ri[0,0,:3]=[2,.4,.5]
        pixel=np.array([[[0,0,np.pi/2,10,0,0]]]);frame=np.eye(4);frame[:3,3]=[3,0,0]
        for return_index in [1,2]:
            r=range_to_points(ri,{'extrinsic':np.eye(4),'inclinations':[0]},pixel_pose=pixel,frame_pose=frame,return_index=return_index,motion_policy='compensated')
            np.testing.assert_allclose(r['xyz'],[[7,2,0]],atol=1e-6)
            np.testing.assert_allclose(r['physical_features'],[[2,.4,.5]])
        with self.assertRaises(ValueError):
            range_to_points(ri,{'extrinsic':np.eye(4),'inclinations':[0]},return_index=1,motion_policy='compensated')

    def test_interpolated_inclinations_and_empty(self):
        ri=np.zeros((2,1,4));ri[...,0]=2
        r=range_to_points(ri,{'extrinsic':np.eye(4),'inclination_min':-.4,'inclination_max':.4},return_index=1,motion_policy='uncompensated')
        np.testing.assert_allclose(r['xyz'],[[2*np.cos(.2),0,2*np.sin(.2)],[2*np.cos(.2),0,-2*np.sin(.2)]],atol=1e-6)
        ri[...,0]=0
        r=range_to_points(ri,{'extrinsic':np.eye(4),'inclinations':[0,0]},return_index=1,motion_policy='uncompensated')
        self.assertEqual(r['xyz'].shape,(0,3))

if __name__ == '__main__':
    unittest.main()
