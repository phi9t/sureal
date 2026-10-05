"""Native one-batch final-checkpoint training-only diagnostic scoring; never heldout."""
import hashlib,importlib.util,json,math,re,subprocess,time,resource
from pathlib import Path
import numpy as np
import sys
sys.path.insert(0,'/tmp/workers')
from balanced import uncovered_count
from pipeline.anchor_grid import anchor_grid
from gpu.scored_proposals_v2 import decode_scored_proposals as decode_proposals
from pipeline.prediction_records import prediction_records
from pipeline.detection_export import export_objects
assert importlib.util.find_spec('tensorflow') is None
start=time.monotonic();manifest=json.loads(Path('/tmp/inputs/manifest.json').read_text())
anchor_candidate=json.loads(Path('/experiment/research/training-anchor-templates.candidate.json').read_text())
anchors=anchor_grid(nx=512,ny=512,cell_size=(.25,.25),origin=(-64.,-64.),templates=[t['values'] for t in anchor_candidate['templates']])
truth=[];predictions=[];frame_reports=[];class_counts={i:0 for i in range(1,5)}
for index,frame in enumerate(manifest['frames']):
 scene,timestamp=frame['identity'].split(':');timestamp=int(timestamp)
 with np.load(Path('/source')/('heads-%02d.npz'%index),allow_pickle=False) as data:
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
 eligible=[]
 for row in matching[0]['rows']:
  b=row['box'];category=row['type']
  if category not in class_counts or row['num_lidar_points_in_box']<=0 or not (-64<=b[0]<64 and -64<=b[1]<64 and -4<=b[2]<6):continue
  b=list(b);b[6]=(b[6]+math.pi)%(2*math.pi)-math.pi
  record={'context_name':scene,'frame_timestamp_micros':timestamp,'object_id':row['object_id'],'type':category,'box':b,'score':1.,'overlap_with_nlz':False,'num_lidar_points_in_box':row['num_lidar_points_in_box'],'difficulty':row['detection_difficulty']}
  truth.append(record);eligible.append(row['object_id']);class_counts[category]+=1
 report=json.loads((Path('/tmp/native')/frame['relative_directory']/'report.json').read_text());assert sorted(eligible)==sorted(report['eligible_object_ids'])
 frame_reports.append({'identity':frame['identity'],'eligible_groundtruth':len(eligible),'predictions':len(records),'uncovered_targets':uncovered_count(report['target_assignment'])})
 print('PREPARED',index+1,'predictions',len(records),'eligible',len(eligible),flush=True)
out=Path('/outputs');(out/'predictions.json').write_text(json.dumps(predictions));(out/'groundtruth.json').write_text(json.dumps(truth))
(out/'preparation.json').write_text(json.dumps({'frames':frame_reports,'eligible_groundtruth':len(truth),'predictions':len(predictions),'groundtruth_by_class':class_counts,'elapsed_seconds':time.monotonic()-start,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},indent=2)+'\n');print('PASS 16-frame final heads prepared for native scoring',flush=True)
