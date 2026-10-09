import copy
import unittest

from motion.cli import motion_native_cli_test

REPORT = {
    'metrics': {'metricsBundles': [
        {'objectFilter': 'TYPE_VEHICLE', 'measurementStep': 15, 'minAde': 0,
         'minFde': 0, 'missRate': 0, 'overlapRate': 0,
         'meanAveragePrecision': 1, 'softMeanAveragePrecision': 1,
         'customMetrics': {}},
    ]},
    'counts': [
        {'object_type': 1, 'measurement_step': 15, 'min_ade': 1,
         'min_fde': 1, 'miss_rate': 1, 'overlap_rate': 1},
    ],
}


class MotionCliStrictReaderSelectionTests(unittest.TestCase):
    def test_cli_vehicle_metric_selector_rejects_duplicate_object_filter(self):
        selector = getattr(motion_native_cli_test, 'vehicle_metrics', None)
        self.assertIsNotNone(selector, 'motion CLI tests use the strict reader selector')
        self.assertEqual(selector(REPORT)['minFde'], 0.0)
        duplicate = copy.deepcopy(REPORT)
        duplicate['metrics']['metricsBundles'].append(
            copy.deepcopy(duplicate['metrics']['metricsBundles'][0])
        )
        with self.assertRaises(ValueError):
            selector(duplicate)


if __name__ == '__main__':
    unittest.main()
