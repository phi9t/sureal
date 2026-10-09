"""Independent homogeneous-transform containment reconciliation.

This copy deliberately stays independent of geometry.oriented_box so it can reconcile producer output.
"""
import json,math
from pathlib import Path
import numpy as np

root=Path('/source');manifest=json.loads((root/'report.json').read_text());boxes=json.loads(Path('/opt/real-boxes.json').read_text());flags=json.loads(Path('/srv/nlz-flags.json').read_text())
expected={(r['context_name'],r['frame_timestamp_micros'],r['object_id']):r['overlap_with_nlz'] for r in flags}
assert len(expected)==len(flags)==len(boxes)==38363
frames={};measurements={}
for box in boxes:frames.setdefault((box['context_name'],box['frame_timestamp_micros']),[]).append(box)
for row in manifest['rows']:measurements.setdefault((row['context'],row['timestamp']),[]).append(row)
checked=0;positive=0
for frame,records in frames.items():
    xyz=[];keys=set()
    for row in measurements[frame]:
        keys.add((row['laser'],row['return']))
        with np.load(root/row['artifact']) as data:
            assert np.all(np.isin(data['nlz'],[-1,1]))
            xyz.append(data['xyz'][data['nlz']==1])
    assert keys=={(laser,ret) for laser in range(1,6) for ret in [1,2]}
    points=np.concatenate(xyz);homogeneous=np.concatenate([points,np.ones((len(points),1))],axis=1)
    for record in records:
        x,y,z,length,width,height,heading=record['box'];c=math.cos(heading);s=math.sin(heading)
        transform=np.array([[c,-s,0,x],[s,c,0,y],[0,0,1,z],[0,0,0,1]])
        local=homogeneous@np.linalg.inv(transform).T
        inside=np.all(np.abs(local[:,:3])<=np.array([length,width,height])/2,axis=1)
        result=bool(inside.any());key=(*frame,record['object_id'])
        assert expected[key]==result,key
        checked+=1;positive+=result
assert checked==38363
Path('/outputs/nlz-validation.json').write_text(json.dumps({'checked_boxes':checked,'positive_overlap_boxes':positive,'method':'independent inverse homogeneous transform of NLZ points from all ten sensor returns','status':'all overlap flags reconciled'},indent=2)+'\n')
print('PASS independent full NLZ flags',checked)
