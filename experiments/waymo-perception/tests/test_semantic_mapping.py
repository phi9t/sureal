import unittest
import numpy as np
from pipeline.semantic_mapping import refine_point_classes


class SemanticMappingTests(unittest.TestCase):
    def test_fine_predictions_refine_only_supported_unambiguous_points(self):
        baseline=np.array([4,4,16,17,7],dtype=np.int64)
        camera=np.array([2,3,24,23,9],dtype=np.int64)
        result=refine_point_classes(baseline,camera,np.array([True,True,True,True,False]),semantic_origin='predicted-camera-semantic')
        np.testing.assert_array_equal(result['predictions'],[1,2,16,17,7])
        np.testing.assert_array_equal(result['transferred'],[True,True,False,False,False])
        self.assertEqual(result['reasons'].tolist(),['transferred','transferred','ambiguous taxonomy','ambiguous taxonomy','unsupported geometry'])
        np.testing.assert_array_equal(baseline,[4,4,16,17,7])

    def test_annotation_and_coarse_box_origins_refused(self):
        for origin in ['ground-truth-camera-segmentation','predicted-camera-box','oracle-prompt']:
            with self.assertRaises(ValueError):refine_point_classes(np.array([1]),np.array([2]),np.array([True]),semantic_origin=origin)

    def test_unmapped_and_undefined_preserve_full_support(self):
        baseline=np.array([3,12,14]);camera=np.array([0,8,25])
        result=refine_point_classes(baseline,camera,np.ones(3,dtype=bool),semantic_origin='predicted-camera-semantic')
        np.testing.assert_array_equal(result['predictions'],baseline);self.assertEqual(result['points'],3)
        np.testing.assert_array_equal(result['transferred'],[False,False,False])


if __name__=='__main__':unittest.main()
