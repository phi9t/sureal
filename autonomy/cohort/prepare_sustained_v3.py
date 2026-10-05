"""Frozen16 V3 export with every native four-class GT box; training-only."""
import hashlib,importlib.util,json,math,re,subprocess,time,resource
from pathlib import Path
import numpy as np
from cohort.balanced import uncovered_count
from cohort.sustained_groundtruth import groundtruth_records
from cohort.sustained_contract import validate_contract
from detection.anchor_grid import anchor_grid
from gpu.scored_proposals_v3 import decode_scored_proposals as decode_proposals
from detection.prediction_records import prediction_records
assert importlib.util.find_spec('tensorflow') is None
start=time.monotonic();manifest=json.loads(Path('/tmp/inputs/manifest.json').read_text())
audit=json.loads(Path('/tmp/inputs/export-audit.json').read_text());manifest_path=Path('/tmp/inputs/manifest.json');anchor_path=Path('/tmp/inputs/anchor-templates.json')
if hashlib.sha256(manifest_path.read_bytes()).hexdigest()!=audit['manifest_sha256'] or hashlib.sha256(anchor_path.read_bytes()).hexdigest()!=audit['anchor_templates_sha256']:raise ValueError('external export manifest/anchors changed')
validate_contract(manifest['candidate'],[{k:f[k] for k in ['identity','split','sha256']} for f in manifest['frames']])
if set(audit['head_hashes'])!={f'heads-{i:02d}.npz' for i in range(16)}:raise ValueError('externally pinned full16 heads required')
anchor_candidate=json.loads(anchor_path.read_text())
anchors=anchor_grid(nx=512,ny=512,cell_size=(.25,.25),origin=(-64.,-64.),templates=[t['values'] for t in anchor_candidate['templates']])
truth=[];predictions=[];frame_reports=[];class_counts={i:0 for i in range(1,5)}
for index,frame in enumerate(manifest['frames']):
 scene,timestamp=frame['identity'].split(':');timestamp=int(timestamp)
 head=Path('/source')/('heads-%02d.npz'%index)
 if hashlib.sha256(head.read_bytes()).hexdigest()!=audit['head_hashes'][head.name]:raise ValueError('externally pinned export heads changed')
 with np.load(head,allow_pickle=False) as data:
  proposals=decode_proposals(data['classification'],data['box_residuals'],data['direction'],anchors,iou_threshold=.5,score_floor=.05,pre_limit=4096,post_limit=500)
 source=Path('/tmp/physical')/scene/'producer'/f'{timestamp}.npz'
 assert hashlib.sha256(source.read_bytes()).hexdigest()==frame['physical_sha256']
 with np.load(source,allow_pickle=False) as data:
  points=data['physical_points'][:,:3];identity=data['measurement_identity'];flags=data['evaluation_nlz'];states=data['return_states']
  assert states.shape==(10,4) and np.all(states[:,2]==1)
  returns={}
  for laser,ret,present,count in states:
   key=(int(laser),int(ret));assert key not in returns
   mask=(identity[:,0]==laser)&(identity[:,1]==ret);assert mask.sum()==count
   returns[key]=(points[mask],flags[mask])
 records=prediction_records(proposals,context=scene,timestamp=timestamp,sensor_returns=returns);predictions.extend(records)
 boxes_path=Path('/tmp/boxes')/scene/'producer/targets.json';assert hashlib.sha256(boxes_path.read_bytes()).hexdigest()==frame['boxes_sha256']
 frames=json.loads(boxes_path.read_text())['frames'];matching=[x for x in frames if x['timestamp_micros']==timestamp] if frames and 'timestamp_micros' in frames[0] else [x for x in frames if x['rows'] and x['rows'][0]['frame_timestamp_micros']==timestamp]
 assert len(matching)==1
 records_gt,eligible=groundtruth_records(matching[0]['rows'],scene,timestamp)
 truth.extend(records_gt)
 for record in records_gt:class_counts[record['type']]+=1
 native_directory=Path('/tmp/native')/frame['relative_directory']
 for name,digest in frame['sha256'].items():
  if hashlib.sha256((native_directory/name).read_bytes()).hexdigest()!=digest:raise ValueError('original native frame changed')
 report=json.loads((native_directory/'report.json').read_text());assert sorted(eligible)==sorted(report['eligible_object_ids'])
 frame_reports.append({'identity':frame['identity'],'native_groundtruth':len(records_gt),'training_eligible_groundtruth':len(eligible),'zero_point_groundtruth':sum(x['num_lidar_points_in_box']==0 for x in records_gt),'predictions':len(records),'uncovered_targets':uncovered_count(report['target_assignment'])})
 print('PREPARED',index+1,'predictions',len(records),'eligible',len(eligible),flush=True)
out=Path('/outputs');(out/'predictions.json').write_text(json.dumps(predictions));(out/'groundtruth.json').write_text(json.dumps(truth))
(out/'preparation.json').write_text(json.dumps({'frames':frame_reports,'native_groundtruth':len(truth),'eligible_groundtruth':len(truth),'training_eligible_groundtruth':sum(f['training_eligible_groundtruth'] for f in frame_reports),'groundtruth_policy':'all native four-class boxes; native evaluator handles eligibility','decoder_version':3,'manifest_sha256':audit['manifest_sha256'],'head_hashes':audit['head_hashes'],'anchor_templates_sha256':audit['anchor_templates_sha256'],'predictions':len(predictions),'groundtruth_by_class':class_counts,'elapsed_seconds':time.monotonic()-start,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},indent=2)+'\n');print('PASS full16 native GT V3 heads prepared for native scoring',flush=True)
