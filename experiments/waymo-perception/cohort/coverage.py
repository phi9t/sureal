import hashlib,json,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,'/experiment/cohort')
from protocol import validate_cohort
from balanced import uncovered_count
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
manifest=json.loads(Path('/tmp/inputs/manifest.json').read_text());frames=[];gt={str(i):0 for i in range(1,5)};uncovered=0
for frame in manifest['frames']:
 directory=Path('/tmp/native')/frame['relative_directory']
 for name,h in frame['sha256'].items():assert sha(directory/name)==h
 scene,timestamp=frame['identity'].split(':');boxfile=Path('/tmp/boxes')/scene/'producer/targets.json';assert sha(boxfile)==frame['boxes_sha256']
 physical=Path('/tmp/physical')/scene/'producer'/f'{timestamp}.npz';assert sha(physical)==frame['physical_sha256']
 rows=[f for f in json.loads(boxfile.read_text())['frames'] if f['timestamp_micros']==int(timestamp)];assert len(rows)==1
 eligible=[r for r in rows[0]['rows'] if r['type'] in range(1,5) and r['num_lidar_points_in_box']>0 and -64<=r['box'][0]<64 and -64<=r['box'][1]<64 and -4<=r['box'][2]<6]
 report=json.loads((directory/'report.json').read_text());assert sorted(x['object_id'] for x in eligible)==sorted(report['eligible_object_ids'])
 for r in eligible:gt[str(r['type'])]+=1
 with np.load(directory/'targets.npz',allow_pickle=False) as data:counts={str(i):int((data['labels']==i).sum()) for i in range(1,5)}
 assert counts==frame['positive_anchors'];uncovered+=uncovered_count(report['target_assignment'])
 frames.append(dict(frame,split='training'))
summary=validate_cohort(frames);assert all(v>0 for v in gt.values())
Path('/outputs/check.json').write_text(json.dumps({**summary,'eligible_GT_by_class':gt,'uncovered_GT':uncovered,'scope':'full-class training-only input coverage; no quality acceptance'},indent=2));print('PASS full-class native fixture',gt,summary)
