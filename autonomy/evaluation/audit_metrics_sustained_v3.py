# Deliberate independent checker: oriented-box field rereads stay separate from producer export code.
from resources.sustained_scoring_budget import DEFAULT_NATIVE_SECONDS
import json,math,re,subprocess
from pathlib import Path
from detection.native_detection_adapter import parse_result
from evidence.source_snapshot import file_sha256
sha=file_sha256
e=json.loads(Path('/tmp/expected.json').read_text());r=e['receipt'];assert sha('/tmp/score-receipt.json')==e['receipt_sha256']
for key,directory in [('parent_artifacts',Path('/source')),('artifacts',Path('/tmp/scored'))]:
 for path,digest in r[key].items():assert sha(directory/Path(path).name)==digest
for name in ['predictions','groundtruth']:
 records=json.loads((Path('/source')/(name+'.json')).read_text());run=subprocess.run(['protoc','--proto_path=/upstream/src','--decode=waymo.open_dataset.Objects','waymo_open_dataset/protos/metrics.proto'],input=(Path('/tmp/scored')/(name+'.bin')).read_bytes(),capture_output=True);assert run.returncode==0
 blocks=re.split(r'^objects \{\n',run.stdout.decode(),flags=re.M)[1:];assert len(blocks)==len(records)
 for b,record in zip(blocks,records):
  assert re.search(r'context_name: "([^"\n]+)"',b)[1]==record['context_name'] and int(re.search(r'frame_timestamp_micros: (\d+)',b)[1])==record['frame_timestamp_micros']
  assert re.search(r'\bid: "([^"\n]+)"',b)[1]==record['object_id']
  assert re.search(r'\btype: (\S+)',b)[1]=={1:'TYPE_VEHICLE',2:'TYPE_PEDESTRIAN',3:'TYPE_SIGN',4:'TYPE_CYCLIST'}[record['type']]
  for field,value in zip(['center_x','center_y','center_z','length','width','height','heading'],record['box']):assert math.isclose(float(re.search(r'\b'+field+r': ([^\s]+)',b)[1]),value,rel_tol=1e-12,abs_tol=1e-12)
  assert math.isclose(float(re.search(r'\bscore: ([^\s]+)',b)[1]),record['score'],rel_tol=1e-6,abs_tol=1e-7)
  assert int(re.search(r'num_lidar_points_in_box: (\d+)',b)[1])==record['num_lidar_points_in_box']
  assert re.search(r'overlap_with_nlz: (true|false)',b)[1]==str(record['overlap_with_nlz']).lower()
  difficulty=re.search(r'detection_difficulty_level: (\S+)',b)
  if record['difficulty'] is None:assert difficulty is None
  else:assert difficulty[1]=={0:'UNKNOWN',1:'LEVEL_1',2:'LEVEL_2'}[record['difficulty']]
run=subprocess.run(['/metrics-build/compute_detection_metrics','/tmp/scored/predictions.bin','/tmp/scored/groundtruth.bin'],capture_output=True,text=True,timeout=DEFAULT_NATIVE_SECONDS)
parsed=parse_result(run.returncode,run.stdout,run.stderr);metrics=parsed['metrics'];assert metrics==r['validation']['metrics'];assert parsed['diagnostics']==r['validation']['diagnostics']
values=r['validation']['LEVEL2_per_class'];assert values=={category:metrics[f'OBJECT_TYPE_TYPE_{name}_LEVEL_2'] for category,name in {'1':'VEHICLE','2':'PEDESTRIAN','3':'SIGN','4':'CYCLIST'}.items()};assert set(values)=={'1','2','3','4'} and all(math.isfinite(v) and 0<=v<=1 for row in values.values() for v in row.values());mean=sum(x['APH'] for x in values.values())/len(values);passed=all(x['APH']>=.8 for x in values.values());assert math.isclose(mean,r['validation']['mean_populated_class_APH']) and r['validation']['APH_gate_passed']==passed and r['validation']['all_class_APH_gate_passed']==passed
assert r['validation']['decoder_version']==3 and r['validation']['groundtruth_policy']=='all native four-class boxes; native evaluator handles eligibility'
Path('/outputs/metrics.stdout').write_text(run.stdout);Path('/outputs/metrics.stderr').write_text(run.stderr);Path('/outputs/check.json').write_text(json.dumps({'all_export_fields_independently_reread':True,'native_metric_replay_exact':True,'mean_populated_class_APH':mean,'all_class_APH_gate_passed':passed,'diagnostics':parsed['diagnostics'],'scope':'independent full16 V3 native protobuf/export/metric audit; original four-class native GT retained; no heldout claim'}));print('PASS independent one-batch native export and metric replay',mean)
