import unittest
import numpy as np
from pipeline.camera_semantic_scoring import score

class CameraScoringTests(unittest.TestCase):
    def test_native_camera_classes_and_ignored_pixels_have_exact_denominators(self):
        result=score(np.array([2,2,3,0]),np.array([2,3,3,28]),np.ones(4,dtype=bool))
        self.assertEqual(result['eligible_pixels'],3)
        self.assertEqual(result['per_class_iou'][2],0.5)
        self.assertEqual(result['per_class_iou'][3],0.5)
        self.assertEqual(result['mean_iou'],0.5)
        self.assertEqual(result['classes_in_mean'],[2,3])

    def test_missing_versus_annotated_no_eligible_support_stay_distinct(self):
        self.assertEqual(score(None,None,None)['coverage'],'missing_annotation')
        result=score(np.array([0]),np.array([2]),np.array([True]))
        self.assertEqual(result['coverage'],'annotated_no_eligible_pixels')
        self.assertIsNone(result['mean_iou'])

    def test_unlabeled_prediction_on_supported_ground_truth_is_a_false_negative(self):
        result=score(np.array([2]),np.array([0]),np.array([True]))
        self.assertEqual(result['per_class_iou'][2],0)
        self.assertEqual(result['eligible_pixels'],1)

    def test_malformed_labels_shapes_and_support_masks_fail(self):
        for truth,pred,support in (([29],[2],[True]),([2],[2.5],[True]),([2],[2],[1]),([2,3],[2],[True])):
            with self.subTest(truth=truth),self.assertRaises(ValueError):
                score(np.array(truth),np.array(pred),np.array(support))

if __name__=='__main__':unittest.main()
