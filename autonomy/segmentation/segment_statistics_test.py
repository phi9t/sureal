import unittest
import numpy as np
from segmentation.segment_statistics import native_semantic_iou,paired_segment_bootstrap

class SegmentStatisticsTests(unittest.TestCase):
    def test_native_undefined_and_absent_class_rules_match_hand_counts(self):
        c=np.zeros((23,23),dtype=np.int64);c[0,1]=100;c[1,1]=5
        self.assertEqual(native_semantic_iou(c),1.)
        c[1,1]=0;c[1,0]=5
        self.assertAlmostEqual(native_semantic_iou(c),21/22)

    def test_paired_cluster_effect_matches_exact_constant_treatment(self):
        base=np.zeros((2,3,23,23),dtype=np.int64);treatment=base.copy()
        base[:,:,1,1]=10;treatment[:,:,1,0]=10
        result=paired_segment_bootstrap(base,treatment,replicates=200,seed=17)
        self.assertAlmostEqual(result['effect'],-1/22)
        np.testing.assert_allclose(result['interval_95'],[-1/22,-1/22],atol=1e-15)

    def test_heterogeneous_segments_retain_cluster_uncertainty(self):
        base=np.zeros((1,2,23,23),dtype=np.int64);other=base.copy()
        base[:,:,1,1]=10;other[:,0,1,0]=10;other[:,1,1,1]=10
        result=paired_segment_bootstrap(base,other,replicates=1000,seed=17)
        self.assertAlmostEqual(result['effect'],-1/44)
        np.testing.assert_allclose(result['interval_95'],[-1/22,0],atol=1e-15)

    def test_segment_draws_are_shared_across_seed_pairs(self):
        base=np.zeros((2,2,23,23),dtype=np.int64);other=base.copy()
        base[:,:,1,1]=10
        other[0,0,1,0]=10;other[0,1,1,1]=10
        other[1,0,1,1]=10;other[1,1,1,0]=10
        result=paired_segment_bootstrap(base,other,replicates=1000,seed=17)
        np.testing.assert_allclose(result['interval_95'],[-1/44,-1/44],atol=1e-15)

    def test_different_eligible_support_cannot_be_compared(self):
        base=np.zeros((1,2,23,23),dtype=np.int64);treatment=base.copy();treatment[:,:,1,1]=1
        with self.assertRaises(ValueError):paired_segment_bootstrap(base,treatment,replicates=20,seed=17)

if __name__=='__main__':unittest.main()
