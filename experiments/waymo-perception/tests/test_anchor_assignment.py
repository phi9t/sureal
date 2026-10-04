"""Hand-specified target assignment thresholds, ties and missing targets."""
import unittest
import numpy as np
from pipeline.anchor_assignment import assign_overlaps


class AnchorAssignmentTests(unittest.TestCase):
    def test_threshold_gap_and_forced_ties_survive_background_overwrite(self):
        overlap=np.array([[.6,0],[.5,0],[.45,0],[.3,.4],[.1,.4],[0,0]])
        result=assign_overlaps(overlap,np.array([1,2]),positive=.6,negative=.45)
        np.testing.assert_array_equal(result['labels'],[1,-1,-1,2,2,0])
        np.testing.assert_array_equal(result['target_indices'],[0,-1,-1,1,1,-1])

    def test_no_overlap_never_forces_positive_and_empty_catalogs(self):
        for overlap,classes in [(np.zeros((3,2)),np.array([1,2])),
                                (np.empty((3,0)),np.array([],dtype=np.int64))]:
            result=assign_overlaps(overlap,classes,positive=.6,negative=.45)
            np.testing.assert_array_equal(result['labels'],[0,0,0])
            np.testing.assert_array_equal(result['target_indices'],[-1,-1,-1])
        result=assign_overlaps(np.empty((0,2)),np.array([1,2]),positive=.6,negative=.45)
        self.assertEqual(result['labels'].shape,(0,))

    def test_tied_target_assignment_uses_first_target(self):
        result=assign_overlaps(np.array([[.7,.7]]),np.array([2,1]),positive=.6,negative=.45)
        np.testing.assert_array_equal(result['labels'],[2])
        np.testing.assert_array_equal(result['target_indices'],[0])

    def test_malformed_overlap_and_invalid_thresholds_refused(self):
        for overlap,classes,positive,negative in [
                (np.array([[float('nan')]]),np.array([1]),.6,.45),
                (np.array([[1.1]]),np.array([1]),.6,.45),
                (np.array([[.5]]),np.array([0]),.6,.45),
                (np.array([[.5]]),np.array([1]),.4,.6)]:
            with self.assertRaises(ValueError):assign_overlaps(overlap,classes,positive=positive,negative=negative)


if __name__=='__main__':unittest.main()
