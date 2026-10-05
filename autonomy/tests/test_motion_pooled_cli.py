import json
import subprocess
import tempfile
import unittest
from pathlib import Path
import test_motion_native_cli as single_cli

BINARY='/outputs/pooled-build/compute_motion_metrics_pooled'

class MotionPooledCliTests(unittest.TestCase):
    def test_pooled_error_counts_and_ranked_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pairs=[]
            for name,error,confidence in [('correct',0,.1),('wrong',20,.9)]:
                folder=root/name;folder.mkdir()
                single_cli.MotionNativeCliTests().fixture(folder,offset=error)
                for file in ['scenario','predictions']:
                    p=folder/(file+'.textproto');p.write_text(p.read_text().replace('"analytic"',json.dumps(name)))
                p=folder/'predictions.textproto';p.write_text(p.read_text().replace('confidence: 1','confidence: '+str(confidence)))
                pairs.append(str(folder/'scenario.textproto')+' '+str(folder/'predictions.textproto'))
            catalog=root/'pairs.txt';catalog.write_text('\n'.join(pairs)+'\n')
            result=root/'result.json'
            cmd=[BINARY,str(catalog),str(root/'correct/config.textproto'),str(result)]
            run=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)
            report=json.loads(result.read_text())
            self.assertEqual(report['scenarios'],2)
            vehicle=next(b for b in report['metrics']['metricsBundles'] if b.get('objectFilter')=='TYPE_VEHICLE')
            self.assertAlmostEqual(float(vehicle['minFde']),10,places=5)
            self.assertAlmostEqual(float(vehicle['meanAveragePrecision']),.25,places=5)
            count=next(c for c in report['counts'] if c['object_type']==1)
            self.assertEqual(count['min_fde'],2)

    def test_duplicate_missing_and_malformed_pairs_refuse_output(self):
        for fault in ['duplicate','missing','extra_column','empty']:
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);single_cli.MotionNativeCliTests().fixture(root)
                pair=str(root/'scenario.textproto')+' '+str(root/'predictions.textproto')
                text={'duplicate':pair+'\n'+pair,'missing':pair+'-missing','extra_column':pair+' extra','empty':''}[fault]
                catalog=root/'pairs.txt';catalog.write_text(text)
                result=root/'pooled.json'
                run=subprocess.run([BINARY,str(catalog),str(root/'config.textproto'),str(result)],capture_output=True,text=True)
                self.assertNotEqual(run.returncode,0)
                self.assertFalse(result.exists())

    def test_unlabeled_scenario_does_not_dilute_measured_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pairs=[]
            for name,labeled in [('measured',True),('unlabeled',False)]:
                folder=root/name;folder.mkdir();single_cli.MotionNativeCliTests().fixture(folder,offset=2)
                for file in ['scenario','predictions']:
                    p=folder/(file+'.textproto');p.write_text(p.read_text().replace('"analytic"',json.dumps(name)))
                if not labeled:
                    p=folder/'scenario.textproto';prefix,tail=p.read_text().split('center_x: 1.1 ',1)
                    p.write_text(prefix+'center_x: 1.1 '+tail.replace('valid: true','valid: false'))
                pairs.append(str(folder/'scenario.textproto')+' '+str(folder/'predictions.textproto'))
            catalog=root/'pairs.txt';catalog.write_text('\n'.join(pairs))
            result=root/'result.json'
            run=subprocess.run([BINARY,str(catalog),str(root/'measured/config.textproto'),str(result)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)
            report=json.loads(result.read_text())
            vehicle=next(b for b in report['metrics']['metricsBundles'] if b.get('objectFilter')=='TYPE_VEHICLE')
            self.assertAlmostEqual(float(vehicle['minFde']),2,places=5)
            self.assertEqual(next(c for c in report['counts'] if c['object_type']==1)['min_fde'],1)

    def test_unequal_agent_support_weights_measurements_not_scenarios(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pairs=[]
            for name,error,agents in [('two_correct',0,2),('one_offset',3,1)]:
                folder=root/name;folder.mkdir();single_cli.MotionNativeCliTests().fixture(folder,offset=error)
                scene=folder/'scenario.textproto';text=scene.read_text().replace('"analytic"',json.dumps(name))
                pred=folder/'predictions.textproto';prediction=pred.read_text().replace('"analytic"',json.dumps(name))
                if agents==2:
                    track=text[text.index('tracks {'):text.index(' tracks_to_predict')]
                    text+=' '+track.replace('id: 1','id: 2')+' tracks_to_predict { track_index: 1 difficulty: LEVEL_1 }'
                    group=prediction[prediction.index('multi_modal_predictions'):]
                    prediction+=' '+group.replace('object_id: 1','object_id: 2')
                scene.write_text(text);pred.write_text(prediction)
                pairs.append(str(scene)+' '+str(pred))
            catalog=root/'pairs.txt';catalog.write_text('\n'.join(pairs));result=root/'result.json'
            run=subprocess.run([BINARY,str(catalog),str(root/'two_correct/config.textproto'),str(result)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)
            report=json.loads(result.read_text())
            vehicle=next(b for b in report['metrics']['metricsBundles'] if b.get('objectFilter')=='TYPE_VEHICLE')
            self.assertAlmostEqual(float(vehicle['minFde']),1,places=5)
            self.assertAlmostEqual(float(vehicle['minAde']),1,places=5)
            self.assertEqual(next(c for c in report['counts'] if c['object_type']==1)['min_fde'],3)

    def test_pooled_overlap_of_predicted_boxes_with_other_agent_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pairs=[]
            for name,other_y in [('collision',10),('clear',100)]:
                folder=root/name;folder.mkdir();single_cli.MotionNativeCliTests().fixture(folder)
                scene=folder/'scenario.textproto';text=scene.read_text().replace('"analytic"',json.dumps(name))
                other=' tracks { id: 2 object_type: TYPE_VEHICLE '
                other+=' '.join('states { center_x: 1.5 center_y: '+str(other_y)+' center_z: 0 length: 4 width: 2 height: 1.5 heading: 0 velocity_x: 0 velocity_y: 0 valid: true }' for _ in range(91))
                text+=other+' }';scene.write_text(text)
                pred=folder/'predictions.textproto';pred.write_text(pred.read_text().replace('"analytic"',json.dumps(name)).replace('center_y: 0','center_y: 10'))
                pairs.append(str(scene)+' '+str(pred))
            catalog=root/'pairs.txt';catalog.write_text('\n'.join(pairs));result=root/'result.json'
            run=subprocess.run([BINARY,str(catalog),str(root/'collision/config.textproto'),str(result)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)
            report=json.loads(result.read_text())
            vehicle=next(b for b in report['metrics']['metricsBundles'] if b.get('objectFilter')=='TYPE_VEHICLE')
            self.assertAlmostEqual(float(vehicle['overlapRate']),.5,places=5)
            self.assertEqual(next(c for c in report['counts'] if c['object_type']==1)['overlap_rate'],2)

    def test_overlap_uses_most_confident_mode_while_error_uses_best_mode(self):
        for collision_confidence in [.9,.1]:
            with self.subTest(collision_confidence=collision_confidence),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);single_cli.MotionNativeCliTests().fixture(root)
                scene=root/'scenario.textproto';text=scene.read_text()
                other=' tracks { id: 2 object_type: TYPE_VEHICLE '
                other+=' '.join('states { center_x: 1.5 center_y: 10 center_z: 0 length: 4 width: 2 height: 1.5 heading: 0 velocity_x: 0 velocity_y: 0 valid: true }' for _ in range(91))
                scene.write_text(text+other+' }')
                pred=root/'predictions.textproto';original=pred.read_text()
                start=original.index('joint_predictions {');mode=original[start:original.rfind(' }')]
                collision=mode.replace('confidence: 1','confidence: '+str(collision_confidence)).replace('center_y: 0','center_y: 10')
                clear=mode.replace('confidence: 1','confidence: '+str(1-collision_confidence))
                pred.write_text('scenario_id: "analytic" multi_modal_predictions { '+collision+' '+clear+' }')
                config=root/'config.textproto';config.write_text(config.read_text().replace('max_predictions: 1','max_predictions: 2'))
                pairs=root/'pairs.txt';pairs.write_text(str(scene)+' '+str(pred));result=root/'result.json'
                run=subprocess.run([BINARY,str(pairs),str(config),str(result)],capture_output=True,text=True)
                self.assertEqual(run.returncode,0,run.stderr)
                report=json.loads(result.read_text())
                vehicle=next(b for b in report['metrics']['metricsBundles'] if b.get('objectFilter')=='TYPE_VEHICLE')
                self.assertAlmostEqual(float(vehicle['minFde']),0,places=5)
                self.assertAlmostEqual(float(vehicle['overlapRate']),1 if collision_confidence>.5 else 0,places=5)
