import json
import tempfile
import unittest
from pathlib import Path
from evaluation.strict_metric_replay import replay_roots, score_record_replay_roots

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

    def test_score_record_replay_uses_consumer_class_policies(self):
        with tempfile.TemporaryDirectory() as temp:
            repo=Path(temp)/'repo';research=repo/'autonomy/research';cache=Path(temp)/'cache'
            research.mkdir(parents=True);(cache/'score').mkdir(parents=True);(cache/'fixture').mkdir();(cache/'case').mkdir()
            result={'cases':{'baseline':{'status':'training in progress','curve':[{
                'step':1,
                'groundtruth_by_class':{'1':2,'2':3,'3':1,'4':0},
                'LEVEL2_per_class':{'1':{'AP':.9,'APH':.8},'2':{'AP':.9,'APH':.7},'3':{'AP':.9,'APH':.6}},
            }]}}}
            (research/'experiment-registry.json').write_text(json.dumps({'runs':[{'id':'run','results':'research/result.json','closure':'research/missing.json','recipes':{'baseline':{}}}]}))
            (research/'result.json').write_text(json.dumps(result))
            (cache/'score/check.json').write_text(json.dumps({
                'decoder_version':3,
                'groundtruth_policy':'all native four-class boxes; native evaluator handles eligibility',
                'manifest_sha256':'1'*64,
                'head_hashes':{f'heads-{i:02d}.npz':'2'*64 for i in range(16)},
                'frames':[{'identity':str(i)} for i in range(16)],
                'native_groundtruth':10,
                'predictions':20,
                'all_class_APH_gate_passed':True,
                'APH_gate_passed':True,
                'LEVEL2_per_class':{str(i):{'AP':.9,'APH':.9} for i in range(1,5)},
            }))
            (cache/'case/score-verified.json').write_text(json.dumps({'output_directory':str(cache/'score')}))
            (cache/'case/checkpoint-admitted.json').write_text(json.dumps({'stage_receipts':{'score':{'path':str(cache/'case/score-verified.json')}}}))
            (cache/'case/state.json').write_text(json.dumps({'records':[{
                'sample':{'step':1,'APH':{str(i):.9 for i in range(1,5)}},
                'final_path':str(cache/'case/checkpoint-admitted.json'),
            }]}))
            (research/'balanced16-sustained-fixture-live.json').write_text(json.dumps({'cases':{'baseline':{'case_directory':str(cache/'case')}}}))
            (cache/'fixture/results.json').write_text(json.dumps({'cases':{'baseline':{'curve':[{
                'step':1,
                'LEVEL2_per_class':{str(i):{'APH':.9} for i in range(1,5)},
            }]}}}))

            report=score_record_replay_roots([cache,research],root_labels=['<cache>','autonomy/research'],repo=repo)

            self.assertEqual(report['inventory']['records'],3)
            self.assertEqual(report['consumers']['evidence_projection']['accepted'],1)
            self.assertEqual(report['consumers']['sustained_admission']['accepted'],1)
            self.assertEqual(report['unconsumed_malformed_records'],1)
            self.assertEqual(report['rejections'],[])

    def test_score_record_replay_reports_consumed_rejections(self):
        with tempfile.TemporaryDirectory() as temp:
            repo=Path(temp)/'repo';research=repo/'autonomy/research'
            research.mkdir(parents=True)
            result={'cases':{'baseline':{'status':'training in progress','curve':[{
                'step':1,
                'LEVEL2_per_class':{'1':{'APH':.9},'2':{'APH':.9},'3':{'APH':.9},'4':{'APH':.9}},
            }]}}}
            (research/'experiment-registry.json').write_text(json.dumps({'runs':[{'id':'run','results':'research/result.json','closure':'research/missing.json','recipes':{'baseline':{}}}]}))
            (research/'result.json').write_text(json.dumps(result))

            report=score_record_replay_roots([research],root_labels=['autonomy/research'],repo=repo)

            self.assertEqual(report['consumers']['evidence_projection']['rejected'],1)
            self.assertEqual(report['rejections'][0]['consumer'],'evidence_projection')
            self.assertEqual(report['rejections'][0]['path'],'autonomy/research/result.json')

if __name__=='__main__':unittest.main()
