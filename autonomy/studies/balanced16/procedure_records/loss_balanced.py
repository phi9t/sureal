"""Literal NumPy loss reconstruction, independent of training loss function."""
import hashlib,json,math
from pathlib import Path
import numpy as np
manifest=json.loads(Path('/tmp/inputs/manifest.json').read_text());v=json.loads(Path('/source/check.json').read_text());times=v['synchronized_step_seconds'];assert len(times)==v['updates']==2000 and all(math.isfinite(t) and t>0 for t in times);assert math.isclose(sum(times),v['cumulative_train_seconds']);assert v['clipped_steps']==sum(x['gradient_norm_before_clip']>10 for x in v['step_records'])
assert len(v['checkpoint_curve'])==3;checks=0
for index,frame in enumerate(manifest['frames']):
 directory=Path('/tmp/native')/frame['relative_directory']
 for name,h in frame['sha256'].items():assert hashlib.sha256((directory/name).read_bytes()).hexdigest()==h
 with np.load(directory/'targets.npz',allow_pickle=False) as a:labels=a['labels'];targets=a['box_targets'].astype(np.float32).astype(float);directions=a['direction_targets']
 positive=labels>0;normalizer=max(1,int(positive.sum()));y=(labels[:,None]==np.arange(1,5)[None,:]).astype(float)
 for curve in v['checkpoint_curve']:
  step=curve['step'];assert math.isclose(sum(times[:step]),curve['cumulative_train_seconds'])
  with np.load(Path('/source')/f'checkpoint-{step:04d}'/f'heads-{index:02d}.npz',allow_pickle=False) as a:logits=a['classification'].astype(float);residuals=a['box_residuals'].astype(float);direction=a['direction'].astype(float)
  probability=np.exp(-np.logaddexp(0,-logits));correct=y*probability+(1-y)*(1-probability);focal=(.25*y+.75*(1-y))*(1-correct)**2*(np.logaddexp(0,logits)-y*logits);classification=float((focal*(labels>=0)[:,None]).sum()/normalizer)
  delta=residuals-targets;delta[:,6]=np.sin(delta[:,6]);absolute=np.abs(delta);local=float((np.where(absolute<1/9,4.5*delta**2,absolute-1/18)*positive[:,None]).sum()/normalizer)
  d=float(((np.logaddexp(direction[:,0],direction[:,1])-direction[np.arange(len(direction)),directions])*positive).sum()/normalizer)
  expected={'classification':classification,'localization':local,'direction':d,'total':classification+2*local+.2*d}
  for key,value in expected.items():assert math.isclose(value,curve['evaluation_losses'][index][key],rel_tol=2e-5,abs_tol=2e-5),(index,step,key,value,curve['evaluation_losses'][index][key])
  checks+=1
 print('LOSS AUDITED',index,flush=True)
assert set(x['frame_index'] for x in v['step_records'])==set(range(16))
Path('/outputs/check.json').write_text(json.dumps({'literal_frame_checkpoint_losses':checks,'timing_and_clipping_validated':True,'all_frames_optimized':True}));print('PASS cohort literal losses',checks)
