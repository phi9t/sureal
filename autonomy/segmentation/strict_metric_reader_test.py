import unittest
from segmentation.strict_metric_reader import EXPECTED_CLASSES,parse_result

REAL_REPORT='''1 frames found in prediction.
1 frames found in groundtruth.
Processing example 0 out of 1
TYPE_TRAFFIC_LIGHT:0
TYPE_BUILDING:0
TYPE_OTHER_VEHICLE:1
TYPE_MOTORCYCLE:1
TYPE_ROAD:0
TYPE_BUS:1
TYPE_SIGN:0
TYPE_CURB:0
TYPE_SIDEWALK:0
TYPE_PEDESTRIAN:0
TYPE_BICYCLE:0
TYPE_TRUCK:0
TYPE_WALKABLE:0
TYPE_CONSTRUCTION_CONE:0
TYPE_TREE_TRUNK:0
TYPE_CAR:0
TYPE_BICYCLIST:1
TYPE_OTHER_GROUND:0
TYPE_VEGETATION:0.0237512
TYPE_MOTORCYCLIST:1
TYPE_POLE:0
TYPE_LANE_MARKER:0
miou=0.228352
'''

class SegmentationStrictMetricReaderTests(unittest.TestCase):
    def test_real_retained_report_is_complete_and_finite(self):
        parsed=parse_result(REAL_REPORT)
        self.assertEqual(set(parsed['classes']),EXPECTED_CLASSES)
        self.assertEqual(parsed['frames']['prediction'],1)
        self.assertEqual(parsed['frames']['groundtruth'],1)
        self.assertEqual(parsed['examples_processed'],[0])
        self.assertAlmostEqual(parsed['classes']['TYPE_VEGETATION'],0.0237512)
        self.assertAlmostEqual(parsed['miou'],0.228352)

    def test_progress_lines_cover_each_frame_in_order(self):
        two_frame=REAL_REPORT.replace('1 frames found in prediction.','2 frames found in prediction.')
        two_frame=two_frame.replace('1 frames found in groundtruth.','2 frames found in groundtruth.')
        complete=two_frame.replace('Processing example 0 out of 1','Processing example 0 out of 2\nProcessing example 1 out of 2')
        self.assertEqual(parse_result(complete)['examples_processed'],[0,1])
        cases=[
            two_frame.replace('Processing example 0 out of 1','Processing example 0 out of 2'),
            complete.replace('Processing example 0 out of 2\nProcessing example 1 out of 2','Processing example 1 out of 2\nProcessing example 0 out of 2'),
            complete.replace('Processing example 1 out of 2','Processing example 1 out of 3'),
        ]
        for report in cases:
            with self.subTest(report=report),self.assertRaises(ValueError):
                parse_result(report)

    def test_unknown_preamble_missing_duplicate_and_unknown_classes_fail(self):
        cases=[
            REAL_REPORT.replace('1 frames found in prediction.','native metric banner'),
            REAL_REPORT.replace('TYPE_POLE:0\n',''),
            REAL_REPORT.replace('TYPE_POLE:0\n','TYPE_POLE:0\nTYPE_POLE:0\n'),
            REAL_REPORT.replace('TYPE_POLE:0','TYPE_UNKNOWN:0'),
        ]
        for report in cases:
            with self.subTest(report=report),self.assertRaises(ValueError):
                parse_result(report)

    def test_duplicate_miou_nonfinite_and_out_of_bounds_fail(self):
        cases=[
            REAL_REPORT+'miou=0.2\n',
            REAL_REPORT.replace('TYPE_POLE:0','TYPE_POLE:nan'),
            REAL_REPORT.replace('miou=0.228352','miou=inf'),
            REAL_REPORT.replace('TYPE_POLE:0','TYPE_POLE:1.1'),
        ]
        for report in cases:
            with self.subTest(report=report),self.assertRaises(ValueError):
                parse_result(report)

if __name__=='__main__':unittest.main()
