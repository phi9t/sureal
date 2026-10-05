"""Selected training targets and explicit covered-object coverage; no sensors."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,'/tmp/workers')
from overfit_detection_targets_v2 import build_targets
from detection.anchor_grid import anchor_grid
job=json.loads(Path('/tmp/input/job.json').read_text());boxes=Path('/source/targets.json');assert hashlib.sha256(boxes.read_bytes()).hexdigest()==job['boxes_sha256'];native=json.loads(boxes.read_text());assert native['scene']==job['scene'];anchors=anchor_grid(nx=512,ny=512,cell_size=[.25,.25],origin=[-64,-64],templates=job['templates']);frames=[]
for frame in native['frames']:
 timestamp=frame['timestamp_micros'];selected=next(f for f in job['selection'] if f['identity']==f"{job['scene']}:{timestamp}");result=build_targets(anchors,frame['rows'],scene=job['scene'],timestamp=timestamp,roi=[-64,-64,-4,64,64,6],positive=.5,negative=.35);directory=Path('/outputs')/str(timestamp);directory.mkdir();np.savez(directory/'targets.npz',**{k:result[k] for k in ['labels','box_targets','direction_targets','target_indices']});(directory/'report.json').write_text(json.dumps(result['report'],indent=2));lookup={r['object_id']:r for r in frame['rows']};covered=set(result['eligible_object_ids'])-set(result['report']['uncovered_object_ids']);objects={str(c):sorted(x for x in result['eligible_object_ids'] if lookup[x]['type']==c) for c in range(1,5)};assert objects==selected['objects'];row={'identity':selected['identity'],'objects':objects,'covered_objects':{str(c):sorted(x for x in covered if lookup[x]['type']==c) for c in range(1,5)},'positive_anchors':result['report']['positive_anchor_counts_by_class'],'uncovered_objects':result['report']['uncovered_object_ids']};frames.append(row);print('TARGETS',selected['identity'],row['positive_anchors'],flush=True)
Path('/outputs/check.json').write_text(json.dumps({'frames':frames,'scope':'native box/anchor coverage only; physical measurement support still required'},indent=2))
