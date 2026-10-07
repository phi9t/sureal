"""Independent literal GPU transition audit, executed outside the frozen package.

Mount this worker and sustained_chunk_reference.py at /tmp/verifier; the original
source-frozen producer package stays at /experiment. External host admission
must pin both verifier files, all inputs, checkpoint bytes and live outputs.
"""
import hashlib,importlib.util,json,math,random,resource,sys,time
from pathlib import Path
import numpy as np
import torch

def sha(path):
 with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def safe(root,name):
 relative=Path(name)
 if relative.is_absolute() or '..' in relative.parts:raise ValueError('safe native path required')
 return Path(root)/relative

def main():
 if importlib.util.find_spec('tensorflow') is not None or not torch.cuda.is_available() or torch.cuda.device_count()!=1:raise ValueError('one native GPU and TensorFlow absence required')
 sys.path.insert(0,'/experiment')
 from cohort.sustained_sources import validate_sources
 from cohort.sustained_contract import validate_contract
 from resources.replay_values import require_exact_state
 from cohort.sustained_loss import class_balanced_objective
 from tier1.catalog import catalog
 from tier1.models import build,optimizer,deterministic,objective
 from sustained_chunk_reference import reference_chunk
 from cohort.replay_sustained import main as replay_heads
 torch.cuda.reset_peak_memory_stats();started=time.monotonic()
 manifestpath=Path('/source/manifest.json');manifest=json.loads(manifestpath.read_text());expected=json.loads(Path('/source/transition.json').read_text())
 if set(expected)!={'manifest_sha256','checkpoint_sha256','previous_checkpoint_sha256','report_sha256','start_step','terminal_step'} or sha(manifestpath)!=expected['manifest_sha256']:raise ValueError('complete external transition identity required')
 framesmeta=manifest['frames'];validate_contract(manifest['candidate'],[{k:f[k] for k in ['identity','split','sha256']} for f in framesmeta]);validate_sources('/experiment',manifest['source_hashes'],manifest['runtime_lock'],json.loads(Path('/tmp/runtime-lock.json').read_text()))
 identity={'manifest_sha256':sha(manifestpath),'source_hashes':manifest['source_hashes'],'runtime_lock':manifest['runtime_lock'],'recipe':manifest['recipe']}
 current=Path('/tmp/retained/checkpoint.pt');reportpath=Path('/tmp/retained/check.json')
 if sha(current)!=expected['checkpoint_sha256'] or sha(reportpath)!=expected['report_sha256']:raise ValueError('external checkpoint/report hash differs')
 state=torch.load(current,map_location='cuda',weights_only=True);report=json.loads(reportpath.read_text());start=expected['start_step'];terminal=expected['terminal_step']
 if type(start) is not int or type(terminal) is not int or not 0<=start<=terminal<=32000 or terminal-start>8000 or state['steps']!=terminal or report['updates']!=terminal or report['checkpoint_sha256']!=sha(current) or report['manifest_sha256']!=sha(manifestpath):raise ValueError('bounded original completed transition required')
 previous=None
 if expected['previous_checkpoint_sha256'] is not None:
  prior=Path('/tmp/previous/checkpoint.pt')
  if sha(prior)!=expected['previous_checkpoint_sha256']:raise ValueError('external previous checkpoint differs')
  previous=torch.load(prior,map_location='cuda',weights_only=True)
  if previous['steps']!=start:raise ValueError('previous checkpoint update differs')
 elif start!=0:raise ValueError('noninitial transition requires previous checkpoint')
 before_seconds=0. if previous is None else previous['training_seconds'];records=report['step_records']
 if [r['step'] for r in records]!=list(range(start+1,terminal+1)) or any(r['frame_index']!=(r['step']-1)%16 for r in records):raise ValueError('complete round-robin producer steps required')
 seconds=[r['synchronized_seconds'] for r in records]
 if any(type(x) not in (int,float) or not math.isfinite(x) or x<0 for x in seconds) or not math.isclose(before_seconds+sum(seconds),state['training_seconds'],rel_tol=1e-12,abs_tol=1e-9) or report['cumulative_train_seconds']!=state['training_seconds']:raise ValueError('synchronized cumulative time differs')
 frames=[]
 for frame in framesmeta:
  directory=safe('/tmp/native',frame['relative_directory'])
  for name,digest in frame['sha256'].items():
   if sha(safe(directory,name))!=digest:raise ValueError('original native payload differs')
  with np.load(directory/'observations.npz',allow_pickle=False) as data:
   if set(data.files)!={'points','counts','coordinates'}:raise ValueError('observation slots differ')
   obs=tuple(torch.from_numpy(data[k].astype(np.float32) if k=='points' else data[k]).pin_memory() for k in ['points','counts','coordinates'])
  with np.load(directory/'targets.npz',allow_pickle=False) as data:
   truth=tuple(torch.from_numpy(data[k].astype(np.float32) if k=='box_targets' else data[k]).pin_memory()[None] for k in ['labels','box_targets','direction_targets'])
  frames.append((obs,truth))
 names={'baseline':'baseline','residual_bev':'residual_bev','class_balanced':'class_balanced_focal','prior_bias':'foreground_prior'}
 deterministic();random.seed(17);np.random.seed(17);case=catalog()[names[manifest['recipe']]];model=build(case).cuda();opt=optimizer(model,case)
 loss=class_balanced_objective if manifest['recipe']=='class_balanced' else lambda output,truth:objective(output,truth,case)
 actual=reference_chunk(model,opt,frames,loss,identity,terminal,checkpoint=previous);require_exact_state(state,actual,exclude_training_seconds=True)
 peak=torch.cuda.max_memory_allocated();rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
 if peak>8*1024**3 or rss>16*1024**2:raise ValueError('transition verifier resource cap exceeded')
 audit=json.loads(Path('/source/audit.json').read_text())
 if audit.get('pilot_reference') or audit['checkpoint_sha256']!=expected['checkpoint_sha256'] or audit['head_hashes']!=report['head_hashes']:raise ValueError('exact checkpoint/head audit inputs required')
 del actual,model,opt,previous,state,frames
 replay_heads()
 Path('/outputs/transition.json').write_text(json.dumps({'manifest_sha256':expected['manifest_sha256'],'checkpoint_sha256':expected['checkpoint_sha256'],'previous_checkpoint_sha256':expected['previous_checkpoint_sha256'],'start_step':start,'terminal_step':terminal,'literal_updates':terminal-start,'state_exact_excluding_training_seconds':True,'producer_synchronized_seconds_reconciled':True,'peak_allocated_bytes':peak,'peak_rss_kib':rss,'elapsed_seconds':time.monotonic()-started,'scope':'independent literal complete model/Adam/RNG/cursor transition and exact restored all16 heads; native loss/export/metrics and retention still required'},indent=2)+'\n')
 print('ADMITTED independent literal GPU transition and all16 heads',start,terminal,flush=True)
if __name__=='__main__':main()
