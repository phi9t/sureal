import unittest
from detection import native_detection_adapter as adapter

VALID='20 examples found.\n\nVEHICLE: [mAP 0.25] [mAPH 0.2]\n'

class DetectionAdapterTests(unittest.TestCase):
    def test_complete_result_preserves_metrics_and_example_count(self):
        self.assertEqual(adapter.parse_result(0,VALID,'',{'VEHICLE'}),
                         {'examples':20,'metrics':{'VEHICLE':{'AP':0.25,'APH':0.2}}})

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

if __name__=='__main__':unittest.main()
