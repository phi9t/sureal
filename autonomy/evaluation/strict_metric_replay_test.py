import json
import tempfile
import unittest
from pathlib import Path
from evaluation.strict_metric_replay import replay_roots

DETECTION='''1 examples found.

OBJECT_TYPE_TYPE_VEHICLE_LEVEL_1: [mAP 0] [mAPH 0]
OBJECT_TYPE_TYPE_VEHICLE_LEVEL_2: [mAP 0] [mAPH 0]
OBJECT_TYPE_TYPE_PEDESTRIAN_LEVEL_1: [mAP 0] [mAPH 0]
OBJECT_TYPE_TYPE_PEDESTRIAN_LEVEL_2: [mAP 0] [mAPH 0]
OBJECT_TYPE_TYPE_SIGN_LEVEL_1: [mAP 0] [mAPH 0]
OBJECT_TYPE_TYPE_SIGN_LEVEL_2: [mAP 0] [mAPH 0]
OBJECT_TYPE_TYPE_CYCLIST_LEVEL_1: [mAP 0] [mAPH 0]
OBJECT_TYPE_TYPE_CYCLIST_LEVEL_2: [mAP 0] [mAPH 0]
RANGE_TYPE_VEHICLE_[0, 30)_LEVEL_1: [mAP 0] [mAPH 0]
RANGE_TYPE_VEHICLE_[0, 30)_LEVEL_2: [mAP 0] [mAPH 0]
RANGE_TYPE_VEHICLE_[30, 50)_LEVEL_1: [mAP 0] [mAPH 0]
RANGE_TYPE_VEHICLE_[30, 50)_LEVEL_2: [mAP 0] [mAPH 0]
RANGE_TYPE_VEHICLE_[50, +inf)_LEVEL_1: [mAP 0] [mAPH 0]
RANGE_TYPE_VEHICLE_[50, +inf)_LEVEL_2: [mAP 0] [mAPH 0]
RANGE_TYPE_PEDESTRIAN_[0, 30)_LEVEL_1: [mAP 0] [mAPH 0]
RANGE_TYPE_PEDESTRIAN_[0, 30)_LEVEL_2: [mAP 0] [mAPH 0]
RANGE_TYPE_PEDESTRIAN_[30, 50)_LEVEL_1: [mAP 0] [mAPH 0]
RANGE_TYPE_PEDESTRIAN_[30, 50)_LEVEL_2: [mAP 0] [mAPH 0]
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

class StrictMetricReplayTests(unittest.TestCase):
    def test_replay_counts_reports_rejections_and_miskeyed_check_json(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            det=root/'det';det.mkdir()
            (det/'metrics.stdout').write_text(DETECTION)
            (det/'metrics.stderr').write_text('')
            bad=root/'bad';bad.mkdir()
            (bad/'metrics.stdout').write_text(DETECTION.replace('OBJECT_TYPE_TYPE_SIGN_LEVEL_2: [mAP 0] [mAPH 0]\n',''))
            (bad/'metrics.stderr').write_text('')
            motion=root/'motion.json'
            motion.write_text(json.dumps({'metrics':{'metricsBundles':[{'objectFilter':'TYPE_VEHICLE','measurementStep':15}]},
                                          'counts':[{'object_type':1,'measurement_step':15,'min_ade':0,'min_fde':0,'miss_rate':0,'overlap_rate':0}]}))
            (root/'check.json').write_text(json.dumps({'metrics':{'30)_LEVEL_1':{'AP':0,'APH':0}}}))
            report=replay_roots([root])
            self.assertEqual(report['counts']['detection'],2)
            self.assertEqual(report['counts']['motion'],1)
            self.assertEqual(report['miskeyed_check_json_files'],1)
            self.assertEqual(len(report['rejections']),1)
            self.assertEqual(report['rejections'][0]['kind'],'detection')

    def test_paths_are_reported_relative_to_named_roots(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            bad=root/'bad';bad.mkdir()
            (bad/'metrics.stdout').write_text(DETECTION.replace('OBJECT_TYPE_TYPE_SIGN_LEVEL_2: [mAP 0] [mAPH 0]\n',''))
            (bad/'metrics.stderr').write_text('')
            nested=root/'nested';nested.mkdir()
            (nested/'check.json').write_text(json.dumps({'metrics':{'30)_LEVEL_1':{'AP':0,'APH':0}}}))
            report=replay_roots([root],root_labels=['<cache>'])
            self.assertEqual(report['roots'],['<cache>'])
            self.assertEqual(report['rejections'][0]['path'],'<cache>/bad/metrics.stdout')
            self.assertEqual(report['miskeyed_check_json_paths'],['<cache>/nested/check.json'])

if __name__=='__main__':unittest.main()
