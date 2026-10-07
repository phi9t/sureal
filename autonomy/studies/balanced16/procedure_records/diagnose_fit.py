"""Literal class-specific fitting diagnostics, without model or loss imports."""
import json,hashlib
from pathlib import Path
import numpy as np
manifest=json.loads(Path('/tmp/inputs/manifest.json').read_text());records=[]
for step in manifest['execution']['checkpoint_grid']:
 stats={str(c):{'positive_anchors':0,'probability_sum':0.,'correct_class_anchors':0,'supervised_objects':set(),'objects_above_05':set(),'sin_heading_error_sum':0.,'encoded_xyz_error_sum':0.} for c in range(1,5)}
 for index,frame in enumerate(manifest['frames']):
  folder=Path('/tmp/native')/frame['relative_directory']
  for name,h in frame['sha256'].items():assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==h
  with np.load(folder/'targets.npz',allow_pickle=False) as a:labels=a['labels'];target=a['box_targets'];matched=a['target_indices']
  with np.load(Path('/source')/f'checkpoint-{step:04d}'/f'heads-{index:02d}.npz',allow_pickle=False) as a:logits=a['classification'].astype(float);residuals=a['box_residuals'].astype(float)
  probability=np.exp(-np.logaddexp(0,-logits));winner=logits.argmax(1)+1
  for c in range(1,5):
   mask=labels==c;s=stats[str(c)];s['positive_anchors']+=int(mask.sum());s['probability_sum']+=float(probability[mask,c-1].sum());s['correct_class_anchors']+=int((winner[mask]==c).sum());s['sin_heading_error_sum']+=float(np.abs(np.sin(residuals[mask,6]-target[mask,6])).sum());s['encoded_xyz_error_sum']+=float(np.linalg.norm(residuals[mask,:3]-target[mask,:3],axis=1).sum())
   for object_index in np.unique(matched[mask]):
    key=(frame['identity'],int(object_index));s['supervised_objects'].add(key)
    if np.any(probability[(matched==object_index)&mask,c-1]>=.5):s['objects_above_05'].add(key)
 for s in stats.values():
  n=max(1,s['positive_anchors']);s['mean_true_class_probability']=s.pop('probability_sum')/n;s['argmax_class_accuracy']=s.pop('correct_class_anchors')/n;s['mean_absolute_sin_heading_error']=s.pop('sin_heading_error_sum')/n;s['mean_encoded_xyz_error']=s.pop('encoded_xyz_error_sum')/n;s['anchor_covered_object_observations']=len(s.pop('supervised_objects'));s['covered_object_observations_with_true_class_score_ge_05']=len(s.pop('objects_above_05'))
 records.append({'step':step,'classes':stats})
Path('/outputs/check.json').write_text(json.dumps({'curve':records,'scope':'class-specific positive-anchor diagnostics; object observations are scene/frame matched-index identities; no native AP/APH or detection recall claim'},indent=2));print('PASS literal positive-anchor class diagnostics')
