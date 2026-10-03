"""Independent literal objective at every new checkpoint."""
import json,math
from pathlib import Path
import numpy as np
job=json.loads(Path('/tmp/inputs/job.json').read_text());v=json.loads(Path('/source/check.json').read_text());case=job['case'];times=v['synchronized_step_seconds'];assert len(times)==v['updates'] and all(math.isfinite(t) and t>0 for t in times)
with np.load('/tmp/targets/targets.npz') as a:labels=a['labels'];targets=a['box_targets'].astype(np.float32).astype(float);directions=a['direction_targets']
positive=labels>0;normalizer=max(1,int(positive.sum()));y=(labels[:,None]==np.arange(1,5)[None,:]).astype(float);checks=0
for curve in v['checkpoint_curve']:
 step=curve['step'];directory=Path('/source')/f'checkpoint-{step:04d}'
 if not (directory/'heads-00.npz').exists():continue
 assert math.isclose(sum(times[:step]),curve['cumulative_train_seconds'])
 with np.load(directory/'heads-00.npz') as a:logits=a['classification'].astype(float);residuals=a['box_residuals'].astype(float);direction=a['direction'].astype(float)
 probability=np.exp(-np.logaddexp(0,-logits));correct=y*probability+(1-y)*(1-probability);focal=(.25*y+.75*(1-y))*(1-correct)**2*(np.logaddexp(0,logits)-y*logits)
 if case['loss']=='class_balanced_positive':focal*=1+y*(normalizer/(4*y.sum(0))-1)
 classification=float((focal*(labels>=0)[:,None]).sum()/normalizer);delta=residuals-targets;delta[:,6]=np.sin(delta[:,6]);absolute=np.abs(delta);local=float((np.where(absolute<1/9,4.5*delta**2,absolute-1/18)*positive[:,None]).sum()/normalizer);d=float(((np.logaddexp(direction[:,0],direction[:,1])-direction[np.arange(len(direction)),directions])*positive).sum()/normalizer)
 expected={'classification':classification,'localization':local,'direction':d,'total':classification+2*local+.2*d}
 for key,value in expected.items():assert math.isclose(value,curve['evaluation_losses'][0][key],rel_tol=2e-5,abs_tol=2e-5),(step,key,value,curve['evaluation_losses'][0][key])
 checks+=1
assert checks>0
Path('/outputs/check.json').write_text(json.dumps({'literal_checkpoint_losses':checks,'timing_validated':True,'loss':case['loss']}));print('PASS literal single-frame losses',checks)
