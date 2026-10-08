import unittest
from detection import native_detection_adapter as adapter

VALID='20 examples found.\n\nVEHICLE: [mAP 0.25] [mAPH 0.2]\n'
FULL_REPORT='''1 examples found.

OBJECT_TYPE_TYPE_VEHICLE_LEVEL_1: [mAP 0.208277] [mAPH 0.162823]
OBJECT_TYPE_TYPE_VEHICLE_LEVEL_2: [mAP 0.20542] [mAPH 0.160523]
OBJECT_TYPE_TYPE_PEDESTRIAN_LEVEL_1: [mAP 0.129258] [mAPH 0.0984962]
OBJECT_TYPE_TYPE_PEDESTRIAN_LEVEL_2: [mAP 0.129258] [mAPH 0.0984962]
OBJECT_TYPE_TYPE_SIGN_LEVEL_1: [mAP 0] [mAPH 0]
OBJECT_TYPE_TYPE_SIGN_LEVEL_2: [mAP 0] [mAPH 0]
OBJECT_TYPE_TYPE_CYCLIST_LEVEL_1: [mAP 0] [mAPH 0]
OBJECT_TYPE_TYPE_CYCLIST_LEVEL_2: [mAP 0] [mAPH 0]
RANGE_TYPE_VEHICLE_[0, 30)_LEVEL_1: [mAP 0.208277] [mAPH 0.162823]
RANGE_TYPE_VEHICLE_[0, 30)_LEVEL_2: [mAP 0.20542] [mAPH 0.160523]
RANGE_TYPE_VEHICLE_[30, 50)_LEVEL_1: [mAP 0] [mAPH 0]
RANGE_TYPE_VEHICLE_[30, 50)_LEVEL_2: [mAP 0] [mAPH 0]
RANGE_TYPE_VEHICLE_[50, +inf)_LEVEL_1: [mAP 0] [mAPH 0]
RANGE_TYPE_VEHICLE_[50, +inf)_LEVEL_2: [mAP 0] [mAPH 0]
RANGE_TYPE_PEDESTRIAN_[0, 30)_LEVEL_1: [mAP 0] [mAPH 0]
RANGE_TYPE_PEDESTRIAN_[0, 30)_LEVEL_2: [mAP 0] [mAPH 0]
RANGE_TYPE_PEDESTRIAN_[30, 50)_LEVEL_1: [mAP 0.129258] [mAPH 0.0984962]
RANGE_TYPE_PEDESTRIAN_[30, 50)_LEVEL_2: [mAP 0.129258] [mAPH 0.0984962]
RANGE_TYPE_PEDESTRIAN_[50, +inf)_LEVEL_1: [mAP 0] [mAPH 0]
RANGE_TYPE_PEDESTRIAN_[50, +inf)_LEVEL_2: [mAP 0] [mAPH 0]
RANGE_TYPE_SIGN_[0, 30)_LEVEL_1: [mAP 0] [mAPH 0]
RANGE_TYPE_SIGN_[0, 30)_LEVEL_2: [mAP 0] [mAPH 0]
RANGE_TYPE_SIGN_[30, 50)_LEVEL_1: [mAP 0] [mAPH 0]
RANGE_TYPE_SIGN_[30, 50)_LEVEL_2: [mAP 0] [mAPH 0]
RANGE_TYPE_SIGN_[50, +inf)_LEVEL_1: [mAP 0] [mAPH 0]
RANGE_TYPE_SIGN_[50, +inf)_LEVEL_2: [mAP 0] [mAPH 0]
RANGE_TYPE_CYCLIST_[0, 30)_LEVEL_1: [mAP 0] [mAPH 0]
RANGE_TYPE_CYCLIST_[0, 30)_LEVEL_2: [mAP 0] [mAPH 0]
RANGE_TYPE_CYCLIST_[30, 50)_LEVEL_1: [mAP 0] [mAPH 0]
RANGE_TYPE_CYCLIST_[30, 50)_LEVEL_2: [mAP 0] [mAPH 0]
RANGE_TYPE_CYCLIST_[50, +inf)_LEVEL_1: [mAP 0] [mAPH 0]
RANGE_TYPE_CYCLIST_[50, +inf)_LEVEL_2: [mAP 0] [mAPH 0]
'''
KNOWN_STDERR='''WARNING: Logging before InitGoogleLogging() is written to STDERR
W20261003 07:16:14.727084     5 iou.cc:172] Tiny box dim seen, return 0.0 IOU.
b1: center_x: 16.576610254024722
center_y: 15.012704453096376
center_z: 12.068397189884765
width: 0.0018523699306077972
length: 1.0424807764507029e-14
height: 2.6744237701485357e-13
heading: 2.76738943655627

b2: center_x: -22.493484775371144
center_y: 9.195233822244063
center_z: 0.74115756813910139
width: 1.9570524265672498
length: 4.9495852117525452
height: 1.5099999999999909
heading: 3.0167059680111592
W20261003 07:16:14.727631     5 iou.cc:216] Huge box dim seen, return 0.0 IOU.
b1: center_x: 62.625414486790547
center_y: -2.2336403257662134
center_z: -15.387136206363234
width: 35993150.236126766
length: 6.8221938051976316
height: 3.7942323498902756e-06
heading: -0.41881843804127783

b2: center_x: 8.1506397471480341
center_y: 31.74016826168554
center_z: -1.2481602901513043
width: 1.0000000000002323
length: 1
height: 1.1100000000000136
heading: 1.0446584654981823
'''

class DetectionAdapterTests(unittest.TestCase):
    def test_complete_result_preserves_metrics_and_example_count(self):
        self.assertEqual(adapter.parse_result(0,VALID,'',{'VEHICLE'}),
                         {'examples':20,'metrics':{'VEHICLE':{'AP':0.25,'APH':0.2}},
                          'diagnostics':{}})

    def test_default_breakdowns_parse_full_native_report_and_range_names(self):
        parsed=adapter.parse_result(0,FULL_REPORT,'')
        self.assertEqual(len(adapter.EXPECTED_DEFAULT_BREAKDOWNS),32)
        self.assertEqual(len(parsed['metrics']),32)
        self.assertIn('RANGE_TYPE_VEHICLE_[0, 30)_LEVEL_1',parsed['metrics'])
        self.assertNotIn('30)_LEVEL_1',parsed['metrics'])

    def test_known_native_diagnostics_are_counted(self):
        parsed=adapter.parse_result(0,FULL_REPORT,KNOWN_STDERR)
        self.assertEqual(parsed['diagnostics'],
                         {'glog_preinit':1,'iou.cc:172 Tiny box dim seen':1,
                          'iou.cc:216 Huge box dim seen':1})

    def test_exit_zero_parse_failure_cannot_be_promoted(self):
        with self.assertRaises(ValueError):
            adapter.parse_result(0,VALID,'Failed to parse predictions.',{'VEHICLE'})

    def test_incomplete_duplicate_nonfinite_and_out_of_bounds_results_fail(self):
        for output in ('',VALID.replace('VEHICLE','OTHER'),VALID+VALID,
                       VALID.replace('0.25','nan'),VALID.replace('0.25','1.1')):
            with self.subTest(output=output),self.assertRaises(ValueError):
                adapter.parse_result(0,output,'',{'VEHICLE'})

    def test_nonzero_exit_and_empty_expected_configuration_fail(self):
        for code,expected in ((1,{'VEHICLE'}),(0,set())):
            with self.assertRaises(ValueError):adapter.parse_result(code,VALID,'',expected)

    def test_unknown_diagnostics_fail(self):
        with self.assertRaises(ValueError):
            adapter.parse_result(0,FULL_REPORT,KNOWN_STDERR+'ERROR: new diagnostic\n')

if __name__=='__main__':unittest.main()
