import unittest
from segmentation.supervision_alignment import summarize_frame_support

class SupervisionAlignmentTests(unittest.TestCase):
    def test_distinct_task_targets_and_joint_annotation_overlap(self):
        r=summarize_frame_support([10,20,30],[10,20],[20,30])
        self.assertEqual(r['point_semantic_eval_frames'],[10,20])
        self.assertEqual(r['camera_mask_eval_frames'],[20,30])
        self.assertEqual(r['joint_annotation_frames'],[20])

    def test_disjoint_camera_labels_do_not_reduce_point_evaluation(self):
        r=summarize_frame_support([10,20,30,40],[30,40],[10,20])
        self.assertEqual(r['point_semantic_eval_frames'],[30,40])
        self.assertEqual(r['camera_conditioned_point_frames'],[30,40])
        self.assertEqual(r['joint_annotation_frames'],[])

    def test_missing_measurements_reported_without_dropping_targets(self):
        r=summarize_frame_support([10],[10,20],[10,30])
        self.assertEqual(r['point_semantic_eval_frames'],[10,20])
        self.assertEqual(r['point_labels_missing_camera_measurements'],[20])
        self.assertEqual(r['camera_labels_missing_measurements'],[30])
        self.assertEqual(summarize_frame_support([10],[10],[])['point_semantic_eval_frames'],[10])

    def test_absent_or_invalid_frame_catalogs_rejected(self):
        for bad in (None,[True],[1.0],[-1],[10,10]):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):summarize_frame_support([10],[10],bad)

if __name__=='__main__':unittest.main()
