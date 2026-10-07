import unittest
import numpy as np
from geometry.reconstruction_validate import check_coordinates

class CoordinateValidationTests(unittest.TestCase):
    def test_independent_ray_and_wrong_extrinsic_detection(self):
        ri=np.array([[[2.,.1,.2,-1]]]);pix=np.array([[0,0]])
        cal={'extrinsic':np.eye(4),'inclinations':[0]}
        self.assertLess(check_coordinates(np.array([[2.,0,0]]),pix,ri,cal,None,None),1e-6)
        with self.assertRaises(ValueError):check_coordinates(np.array([[3.,0,0]]),pix,ri,cal,None,None)
        wrong=dict(cal);wrong['extrinsic']=np.eye(4);wrong['extrinsic'][0,3]=1
        with self.assertRaises(ValueError):check_coordinates(np.array([[2.,0,0]]),pix,ri,wrong,None,None)

    def test_independent_pose_reference(self):
        ri=np.array([[[2.,.1,.2,-1]]]);pix=np.array([[0,0]])
        cal={'extrinsic':np.eye(4),'inclinations':[0]}
        pose=np.array([[[0,0,np.pi/2,10,0,0]]]);frame=np.eye(4);frame[0,3]=3
        self.assertLess(check_coordinates(np.array([[7.,2,0]]),pix,ri,cal,pose,frame),1e-6)
        with self.assertRaises(ValueError):check_coordinates(np.array([[2.,0,0]]),pix,ri,cal,pose,frame)


if __name__ == "__main__":
    unittest.main()
