import unittest
from segmentation.segmentation_export import validate_frame

class SegmentationExportTests(unittest.TestCase):
    def test_both_returns_preserve_identity_and_semantic_order(self):
        frame={'context_name':'scene','frame_timestamp_micros':10,'returns':[[1,2,0],[3,4]]}
        self.assertEqual(validate_frame(frame),('scene',10,[[1,2,0],[3,4]]))

    def test_invalid_keys_categories_and_missing_returns_fail_before_encoding(self):
        for frame in ({'context_name':'','frame_timestamp_micros':10,'returns':[[1],[2]]},
                      {'context_name':'scene','frame_timestamp_micros':10,'returns':[[23],[2]]},
                      {'context_name':'scene','frame_timestamp_micros':10,'returns':[[True],[2]]},
                      {'context_name':'scene','frame_timestamp_micros':10,'returns':[[1.5],[2]]},
                      {'context_name':'scene','frame_timestamp_micros':10,'returns':[[1]]}):
            with self.subTest(frame=frame),self.assertRaises(ValueError):validate_frame(frame)

if __name__=='__main__':unittest.main()
