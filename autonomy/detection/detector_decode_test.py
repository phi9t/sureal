import math
import unittest
import numpy as np
from detection.detector_decode import decode_proposals


class DetectorDecodeTests(unittest.TestCase):
    def test_raw_yaw_direction_precedes_canonical_wrapping(self):
        anchors=np.array([[0.,0.,.5,4.,2.,1.5,3.]])
        residuals=np.zeros((1,7));residuals[0,6]=1
        result=decode_proposals(np.array([[10.,0.,0.,0.]]),residuals,np.array([[0.,1.]]),anchors,
                               iou_threshold=.5,score_floor=.05,pre_limit=10,post_limit=10)
        self.assertAlmostEqual(result['boxes'][0,6],4-2*math.pi,places=12)
        np.testing.assert_array_equal(result['classes'],[1])
        np.testing.assert_array_equal(result['anchor_indices'],[0])

    def test_stable_sigmoid_empty_predictions_and_class_namespace(self):
        settings=dict(iou_threshold=.5,score_floor=.05,pre_limit=10,post_limit=10)
        anchors=np.array([[0.,0.,.5,4.,2.,1.5,0.]])
        result=decode_proposals(np.array([[-1000.,-1000.,-1000.,1000.]]),np.zeros((1,7)),np.zeros((1,2)),anchors,**settings)
        self.assertEqual(result['classes'].tolist(),[4]);self.assertEqual(result['scores'].tolist(),[1.])
        empty=decode_proposals(np.empty((0,4)),np.empty((0,7)),np.empty((0,2)),np.empty((0,7)),**settings)
        self.assertEqual(empty['boxes'].shape,(0,7))
        with self.assertRaises(ValueError):decode_proposals(np.zeros((1,23)),np.zeros((1,7)),np.zeros((1,2)),anchors,**settings)


if __name__=='__main__':unittest.main()
