"""Analytic assignment rectangles and deterministic suppression fixtures."""
import math
import unittest
import numpy as np
from detection.detector_geometry import nearest_bev_iou


class DetectorGeometryTests(unittest.TestCase):
    def test_nearest_orientation_swap_and_periodic_headings(self):
        first=np.array([[0.,0.,0.,4.,2.,2.,0.]])
        other=np.repeat(first,3,axis=0);other[:,6]=[0,math.pi/2,math.pi]
        np.testing.assert_allclose(nearest_bev_iou(first,other),[[1.,1/3,1.]],atol=1e-12)
        self.assertEqual(nearest_bev_iou(first,np.empty((0,7))).shape,(1,0))

    def test_enclosing_suppression_and_original_index_ties(self):
        from detection.detector_geometry import enclosing_bev_nms
        boxes=np.array([[0.,0.,0.,4.,2.,2.,math.pi/4],
                        [0.,0.,0.,4.,2.,2.,-math.pi/4],
                        [20.,0.,0.,4.,2.,2.,0.]])
        kept=enclosing_bev_nms(boxes,np.array([.9,.9,.8]),iou_threshold=.5,score_floor=.05,pre_limit=10,post_limit=10)
        np.testing.assert_array_equal(kept,[0,2])

    def test_suppression_caps_floor_empty_and_invalid_input(self):
        from detection.detector_geometry import enclosing_bev_nms
        boxes=np.array([[0.,0.,0.,2.,2.,2.,0.],[10.,0.,0.,2.,2.,2.,0.],[20.,0.,0.,2.,2.,2.,0.]])
        params=dict(iou_threshold=.5,score_floor=.05,pre_limit=2,post_limit=1)
        np.testing.assert_array_equal(enclosing_bev_nms(boxes,np.array([.04,.8,.9]),**params),[2])
        self.assertEqual(enclosing_bev_nms(np.empty((0,7)),np.empty(0),**params).shape,(0,))
        with self.assertRaises(ValueError):enclosing_bev_nms(boxes,np.array([float('nan'),.8,.9]),**params)
        invalid=boxes.copy();invalid[0,3]=0
        with self.assertRaises(ValueError):nearest_bev_iou(invalid,boxes)


if __name__=='__main__':unittest.main()
