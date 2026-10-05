"""Prepare evaluation-only label replay preserving native point/return order."""
import hashlib,json
from pathlib import Path
import numpy as np

root=Path('/source');out=Path('/outputs')
manifest=json.loads((root/'report.json').read_text())
frames={};identities=[]
for row in manifest['rows']:
    if row['laser']!=1 or not row['segmentation_present']:continue
    path=root/row['artifact'];assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
    with np.load(path) as data:
        keys=list(data.files)
        assert data['segmentation'].shape==(row['points'],2)
        semantic=data['segmentation'][:,1].astype(np.int64)
        assert len(semantic)==len(data['pixels'])==row['points']
        assert np.all((semantic>=0)&(semantic<=22))
        frame=frames.setdefault((row['context'],row['timestamp']),{'context_name':row['context'],'frame_timestamp_micros':row['timestamp'],'returns':[None,None]})
        assert frame['returns'][row['return']-1] is None
        frame['returns'][row['return']-1]=semantic.tolist()
        identities.append({'context':row['context'],'timestamp':row['timestamp'],'return':row['return'],'points':row['points'],'source_artifact':row['artifact'],'source_sha256':row['sha256'],'pixels_sha256':hashlib.sha256(data['pixels'].tobytes()).hexdigest(),'semantic_sha256':hashlib.sha256(semantic.tobytes()).hexdigest()})
assert len(frames)==60 and len(identities)==120
assert all(all(v is not None for v in frame['returns']) for frame in frames.values())
(out/'real-semantics.json').write_text(json.dumps(list(frames.values()))+'\n')
(out/'real-semantic-identities.json').write_text(json.dumps({'frames':len(frames),'returns':len(identities),'identity_records':identities,'scope':'ground truth label replay for evaluator verification only'},indent=2)+'\n')
print('Prepared',len(frames),'real labeled frames')
