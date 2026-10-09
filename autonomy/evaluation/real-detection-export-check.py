"""Native real-box export and independent decoded-field reconciliation."""
import json,re,subprocess,math
from pathlib import Path
from detection.detection_export import export_objects
from detection.native_detection_adapter import parse_result

out=Path('/outputs');records=json.loads(Path('/source/real-boxes.json').read_text())
# Replay only evaluable ground truth as predictions: zero-support targets stay
# in the GT export and are omitted from the evaluation-only prediction fixture.
predictions=[r for r in records if r['num_lidar_points_in_box']>0]
(out/'groundtruth.bin').write_bytes(export_objects(records));(out/'predictions.bin').write_bytes(export_objects(predictions))
classes={'TYPE_VEHICLE':1,'TYPE_PEDESTRIAN':2,'TYPE_SIGN':3,'TYPE_CYCLIST':4}
for name,expected in [('groundtruth',records),('predictions',predictions)]:
    decoded=subprocess.run(['protoc','--proto_path=/upstream/src','--decode=waymo.open_dataset.Objects','waymo_open_dataset/protos/metrics.proto'],input=(out/(name+'.bin')).read_bytes(),capture_output=True)
    assert decoded.returncode==0,decoded.stderr
    blocks=re.split(r'^objects \{\n',decoded.stdout.decode(),flags=re.M)[1:]
    assert len(blocks)==len(expected)
    for block,record in zip(blocks,expected):
        def number(field):return float(re.search(r'\b'+field+r': ([^\s]+)',block)[1])
        assert re.search(r'context_name: "([^"\n]+)"',block)[1]==record['context_name']
        assert int(number('frame_timestamp_micros'))==record['frame_timestamp_micros']
        assert re.search(r'\bid: "([^"\n]+)"',block)[1]==record['object_id']
        assert classes[re.search(r'\btype: (TYPE_\w+)',block)[1]]==record['type']
        for field,value in zip(['center_x','center_y','center_z','length','width','height','heading'],record['box']):
            assert abs(number(field)-value)<1e-12
        assert int(number('num_lidar_points_in_box'))==record['num_lidar_points_in_box']
        assert number('score')==1 and 'overlap_with_nlz: false' in block
run=subprocess.run(['/metrics-build/compute_detection_metrics','/outputs/predictions.bin','/outputs/groundtruth.bin'],capture_output=True,text=True)
(out/'metrics.stdout').write_text(run.stdout);(out/'metrics.stderr').write_text(run.stderr)
parsed=parse_result(run.returncode,run.stdout,run.stderr);metrics=parsed['metrics']
for name,index in classes.items():
    if any(r['type']==index for r in predictions):
        values=metrics['OBJECT_TYPE_'+name+'_LEVEL_2']
        assert abs(values['AP']-1)<1e-6 and abs(values['APH']-1)<1e-6,(name,values)
(out/'real-detection-validation.json').write_text(json.dumps({'source_objects':len(records),'evaluable_predictions':len(predictions),'decoded_fields':'frame/object identities, dimensions, class, point count, score, NLZ fixture flag','result':'native self-replay AP/APH 1 for populated LEVEL_2 object classes','diagnostics':parsed['diagnostics'],'scope':'evaluation-only ground-truth replay; production NLZ derivation remains open'},indent=2)+'\n')
print('PASS real native detection export',len(records),'objects')
