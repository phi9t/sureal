import json,math,re,subprocess
from pathlib import Path
from evidence.source_snapshot import file_sha256 as sha
e=json.loads(Path('/tmp/expected.json').read_text());r=e['receipt'];assert sha('/experiment/research/architecture-'+r['manifest']['architecture_variant']+'-score-first-verified.json')==e['receipt_sha256']
for path,digest in r['artifacts'].items():
 directory=Path('/source') if 'prepared' in Path(path).parts else Path('/tmp/scored');assert sha(directory/Path(path).name)==digest
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
run=subprocess.run(['/metrics-build/compute_detection_metrics','/tmp/scored/predictions.bin','/tmp/scored/groundtruth.bin'],capture_output=True,text=True,timeout=600);assert run.returncode==0
metrics={name:{'AP':float(ap),'APH':float(aph)} for name,ap,aph in re.findall(r'(\S+): \[mAP ([^\]]+)\] \[mAPH ([^\]]+)\]',run.stdout)};assert metrics==r['validation']['metrics']
values=r['validation']['LEVEL2_per_class'];mean=sum(x['APH'] for x in values.values())/len(values);assert math.isclose(mean,r['validation']['mean_populated_class_APH']) and r['validation']['APH_gate_passed']==(mean>=.8)
Path('/outputs/metrics.stdout').write_text(run.stdout);Path('/outputs/check.json').write_text(json.dumps({'all_export_fields_independently_reread':True,'native_metric_replay_exact':True,'mean_populated_class_APH':mean,'APH_gate_passed':mean>=.8,'scope':'independent single-training-batch native export and scoring audit; no heldout claim'}));print('PASS independent one-batch native export and metric replay',mean)
