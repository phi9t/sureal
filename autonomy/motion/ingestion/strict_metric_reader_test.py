import copy
import unittest
from motion.ingestion import strict_metric_reader

parse_result = strict_metric_reader.parse_result

REAL_REPORT={
    'metrics':{'metricsBundles':[
        {'objectFilter':'TYPE_VEHICLE','measurementStep':15,'minAde':0,'minFde':0,
         'missRate':0,'overlapRate':0,'meanAveragePrecision':1,
         'softMeanAveragePrecision':1,'customMetrics':{}},
        {'objectFilter':'TYPE_PEDESTRIAN','measurementStep':15,'minAde':2,'minFde':2,
         'missRate':0,'overlapRate':0,'meanAveragePrecision':1,
         'softMeanAveragePrecision':1,'customMetrics':{}},
    ]},
    'counts':[
        {'object_type':1,'measurement_step':15,'min_ade':1,'min_fde':1,
         'miss_rate':1,'overlap_rate':1},
        {'object_type':2,'measurement_step':15,'min_ade':1,'min_fde':1,
         'miss_rate':1,'overlap_rate':1},
    ],
}

class MotionStrictMetricReaderTests(unittest.TestCase):
    def test_real_retained_report_is_complete_and_zero_values_parse(self):
        parsed=parse_result(REAL_REPORT,{1:{'min_ade':1,'min_fde':1,'miss_rate':1,'overlap_rate':1},
                                         2:{'min_ade':1,'min_fde':1,'miss_rate':1,'overlap_rate':1}})
        self.assertEqual(set(parsed['classes']),{1,2})
        self.assertEqual(parsed['classes'][1]['objectFilter'],'TYPE_VEHICLE')
        self.assertEqual(parsed['classes'][1]['minAde'],0.0)
        self.assertEqual(parsed['classes'][2]['minFde'],2.0)

    def test_proto3_zero_omission_is_declared_per_metric_value(self):
        report=copy.deepcopy(REAL_REPORT)
        del report['metrics']['metricsBundles'][0]['minAde']
        del report['metrics']['metricsBundles'][0]['minFde']
        parsed=parse_result(report,{1:{'min_ade':1,'min_fde':1,'miss_rate':1,'overlap_rate':1},
                                    2:{'min_ade':1,'min_fde':1,'miss_rate':1,'overlap_rate':1}})
        self.assertEqual(parsed['classes'][1]['minAde'],0.0)
        self.assertEqual(parsed['classes'][1]['minFde'],0.0)

    def test_class_metrics_selection_rejects_duplicate_object_filter(self):
        selector=getattr(strict_metric_reader,'class_metrics',None)
        self.assertIsNotNone(selector,'strict reader exposes a class metric selector')
        self.assertEqual(selector(REAL_REPORT,1)['minFde'],0.0)
        duplicate=copy.deepcopy(REAL_REPORT)
        duplicate['metrics']['metricsBundles'].append(copy.deepcopy(duplicate['metrics']['metricsBundles'][0]))
        with self.assertRaises(ValueError):
            selector(duplicate,1)

    def test_missing_structural_field_unknown_duplicate_and_bad_step_fail(self):
        cases=[]
        missing_step=copy.deepcopy(REAL_REPORT);del missing_step['metrics']['metricsBundles'][0]['measurementStep'];cases.append(missing_step)
        unknown=copy.deepcopy(REAL_REPORT);unknown['metrics']['metricsBundles'][0]['objectFilter']='TYPE_SIGN';cases.append(unknown)
        duplicate=copy.deepcopy(REAL_REPORT);duplicate['metrics']['metricsBundles'].append(copy.deepcopy(duplicate['metrics']['metricsBundles'][0]));cases.append(duplicate)
        bad_step=copy.deepcopy(REAL_REPORT);bad_step['counts'][0]['measurement_step']=16;cases.append(bad_step)
        for report in cases:
            with self.subTest(report=report),self.assertRaises(ValueError):
                parse_result(report,{1:{'min_ade':1,'min_fde':1,'miss_rate':1,'overlap_rate':1},
                                     2:{'min_ade':1,'min_fde':1,'miss_rate':1,'overlap_rate':1}})

    def test_nonfinite_values_and_count_mismatch_fail(self):
        nonfinite=copy.deepcopy(REAL_REPORT);nonfinite['metrics']['metricsBundles'][0]['minAde']='NaN'
        mismatch=copy.deepcopy(REAL_REPORT);mismatch['counts'][0]['min_fde']=2
        for report in [nonfinite,mismatch]:
            with self.subTest(report=report),self.assertRaises(ValueError):
                parse_result(report,{1:{'min_ade':1,'min_fde':1,'miss_rate':1,'overlap_rate':1},
                                     2:{'min_ade':1,'min_fde':1,'miss_rate':1,'overlap_rate':1}})

if __name__=='__main__':unittest.main()
