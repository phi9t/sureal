"""Annotation-only target-coverage diagnostic; never a model prediction."""
import hashlib,json,resource,time
from pathlib import Path
import numpy as np
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
start=time.monotonic();e=json.loads(Path('/tmp/inputs/expected.json').read_text())
assert sha('/tmp/inputs/manifest.json')==e['manifest_sha256']
manifest=json.loads(Path('/tmp/inputs/manifest.json').read_text());assert len(manifest['frames'])==16
assert sha('/source/groundtruth.json')==e['groundtruth_sha256'] and sha('/source/preparation.json')==e['preparation_sha256']
truth=json.loads(Path('/source/groundtruth.json').read_text());preparation=json.loads(Path('/source/preparation.json').read_text());assert preparation['native_groundtruth']==len(truth)==1279
allowed={f['identity'] for f in manifest['frames']};assert len(allowed)==16;assert all(r['context_name']+':'+str(r['frame_timestamp_micros']) in allowed for r in truth)
sets={name:[] for name in ['positive_native','training_roi','anchor_covered']};rows=[]
for frame in manifest['frames']:
 directory=Path('/tmp/native')/frame['relative_directory']
 for name in ['report.json','targets.npz']:assert sha(directory/name)==frame['sha256'][name]
 report=json.loads((directory/'report.json').read_text());identity=report['scene']+':'+str(report['timestamp_micros']);assert identity==frame['identity']
 eligible=report['eligible_object_ids'];assert len(set(eligible))==len(eligible)
 with np.load(directory/'targets.npz',allow_pickle=False) as a:
  labels=a['labels'];indices=a['target_indices'];positive=indices[labels>0];assert np.all((positive>=0)&(positive<len(eligible)));covered={eligible[int(i)] for i in np.unique(positive)}
 assert set(eligible)-covered==set(report['target_assignment']['uncovered_object_ids'])
 records=[r for r in truth if r['context_name']+':'+str(r['frame_timestamp_micros'])==identity];lookup={r['object_id']:r for r in records};assert len(lookup)==len(records) and set(eligible)<=set(lookup)
 selected={'positive_native':[r for r in records if r['num_lidar_points_in_box']>0],'training_roi':[lookup[i] for i in eligible],'anchor_covered':[lookup[i] for i in eligible if i in covered]}
 counts={}
 for name,items in selected.items():
  sets[name]+=items;counts[name]={str(c):sum(r['type']==c for r in items) for c in range(1,5)}
 rows.append({'identity':identity,'counts':counts,'uncovered_ids':sorted(set(eligible)-covered)})
for name,records in sets.items():
 out=Path('/outputs')/name;out.mkdir();(out/'groundtruth.json').write_bytes(Path('/source/groundtruth.json').read_bytes());(out/'predictions.json').write_text(json.dumps([{**record,'score':1.0,'difficulty':None} for record in records],indent=2)+'\n')
 prep={**preparation,'predictions':len(records),'scope':'annotation-only ideal target coverage diagnostic; not model output'}
 prep['frames']=[{**f,'predictions':sum(r['context_name']+':'+str(r['frame_timestamp_micros'])==f['identity'] for r in records)} for f in preparation['frames']];(out/'preparation.json').write_text(json.dumps(prep,indent=2)+'\n')
summary={'frames':rows,'counts':{name:{str(c):sum(r['type']==c for r in records) for c in range(1,5)} for name,records in sets.items()},'elapsed_seconds':time.monotonic()-start,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'scope':'annotation-only ideal predictions for positive native GT, trainingROI GT and anchor-covered GT; diagnostic of target support, not a mathematical bound on unconstrained predictions or model evidence'}
Path('/outputs/check.json').write_text(json.dumps(summary,indent=2)+'\n');print('PASS coverage oracle construction',summary['counts'],flush=True)
