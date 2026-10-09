"""Independent checkpoint/head audit. This does not certify native APH or fit."""
import importlib.util,json,random,resource,time
from pathlib import Path
import numpy as np
import torch
from detection.sustained_contract import validate_contract
from training_execution.sustained_sources import validate_sources
from training_execution.sustained_state import restore_state,capture_state
from resources.replay_values import require_exact_state,require_exact_heads
from training_execution.sustained_reference import reference_updates
from detection.sustained_loss import class_balanced_objective
from detection.detector_recipe_catalog import catalog
from detection.detector_recipe_models import build,optimizer,deterministic,objective
from evidence.source_snapshot import file_sha256

sha=file_sha256
def safe(root,name):
 p=Path(name)
 if p.is_absolute() or '..' in p.parts:raise ValueError('safe relative path required')
 return Path(root)/p

def main():
 if importlib.util.find_spec('tensorflow') is not None or not torch.cuda.is_available() or torch.cuda.device_count()!=1:raise ValueError('one native GPU and TensorFlow absence required')
 torch.cuda.reset_peak_memory_stats();started=time.monotonic();manifest_path=Path('/tmp/inputs/manifest.json');manifest=json.loads(manifest_path.read_text());audit=json.loads(Path('/tmp/inputs/audit.json').read_text())
 frames=manifest['frames'];validate_contract(manifest['candidate'],[{k:f[k] for k in ['identity','split','sha256']} for f in frames]);validate_sources('/experiment',manifest['source_hashes'],manifest['runtime_lock'],json.loads(Path('/tmp/runtime-lock.json').read_text()))
 identity={'manifest_sha256':sha(manifest_path),'source_hashes':manifest['source_hashes'],'runtime_lock':manifest['runtime_lock'],'recipe':manifest['recipe']}
 checkpoint=Path('/tmp/retained/checkpoint.pt')
 if sha(checkpoint)!=audit['checkpoint_sha256']:raise ValueError('external checkpoint hash differs')
 state=torch.load(checkpoint,map_location='cuda',weights_only=True)
 names={'baseline':'baseline','residual_bev':'residual_bev','class_balanced':'class_balanced_focal','prior_bias':'foreground_prior'}
 deterministic();case=catalog()[names[manifest['recipe']]];model=build(case).cuda();opt=optimizer(model,case);restore_state(state,model,opt,identity)
 # Loading must preserve every model/Adam/RNG/cursor value, not just weights.
 require_exact_state(state,capture_state(model,opt,identity,state['steps'],state['training_seconds']))
 pilot_checks=[]
 if audit.get('pilot_reference'):
  if state['steps']!=35:raise ValueError('pilot reference requires terminal35')
  native_frames=[]
  for frame in frames:
   directory=safe('/tmp/native',frame['relative_directory'])
   for name,value in frame['sha256'].items():
    if sha(safe(directory,name))!=value:raise ValueError('native pilot input differs')
   with np.load(directory/'observations.npz',allow_pickle=False) as data:
    obs=tuple(torch.from_numpy(data[k].astype(np.float32) if k=='points' else data[k]).pin_memory() for k in ['points','counts','coordinates'])
   with np.load(directory/'targets.npz',allow_pickle=False) as data:
    truth=tuple(torch.from_numpy(data[k].astype(np.float32) if k=='box_targets' else data[k]).pin_memory()[None] for k in ['labels','box_targets','direction_targets'])
   native_frames.append((obs,truth))
  previous_path=Path('/tmp/previous/checkpoint.pt')
  if sha(previous_path)!=audit['previous_checkpoint_sha256']:raise ValueError('previous external checkpoint differs')
  previous=torch.load(previous_path,map_location='cuda',weights_only=True)
  if previous['steps']!=19:raise ValueError('pilot restart requires step19')
  loss=class_balanced_objective if manifest['recipe']=='class_balanced' else lambda output,truth:objective(output,truth,case)
  del model,opt
  for initial,name in [(None,'independent full0-to35'),(previous,'independent restart19-to35')]:
   deterministic();random.seed(17);np.random.seed(17);model=build(case).cuda();opt=optimizer(model,case)
   actual=reference_updates(model,opt,native_frames,loss,identity,35,checkpoint=initial)
   require_exact_state(state,actual,exclude_training_seconds=True);pilot_checks.append(name)
   del actual
   if initial is None:del model,opt
  restore_state(state,model,opt,identity)
 model.eval();checked=[]
 with torch.no_grad():
  for index,frame in enumerate(frames):
   directory=safe('/tmp/native',frame['relative_directory'])
   for name,value in frame['sha256'].items():
    if sha(safe(directory,name))!=value:raise ValueError('native payload hash differs')
   with np.load(directory/'observations.npz',allow_pickle=False) as data:
    if set(data.files)!={'points','counts','coordinates'}:raise ValueError('observation slots differ')
    obs=tuple(torch.from_numpy(data[key].astype(np.float32) if key=='points' else data[key]).cuda() for key in ['points','counts','coordinates'])
   output=model(*obs,batch_size=1);actual={key:value[0].cpu().numpy() for key,value in output.items()};name=f'heads-{index:02d}.npz';head=Path('/tmp/retained/heads')/name
   if set(audit['head_hashes'])!={f'heads-{i:02d}.npz' for i in range(16)} or sha(head)!=audit['head_hashes'][name]:raise ValueError('external full16 head hashes differ')
   with np.load(head,allow_pickle=False) as data:require_exact_heads({key:data[key] for key in data.files},actual)
   checked.append(frame['identity'])
 restore_state(state,model,opt,identity);require_exact_state(state,capture_state(model,opt,identity,state['steps'],state['training_seconds']))
 peak=torch.cuda.max_memory_allocated();rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
 if peak>8*1024**3 or rss>16*1024**2:raise ValueError('audit resource cap exceeded')
 Path('/outputs/replay.json').write_text(json.dumps({'checkpoint_sha256':sha(checkpoint),'manifest_sha256':identity['manifest_sha256'],'updates':state['steps'],'checked_frames':checked,'pilot_reference_checks':pilot_checks,'head_hashes':audit['head_hashes'],'peak_allocated_bytes':peak,'peak_rss_kib':rss,'elapsed_seconds':time.monotonic()-started,'scope':'exact restored model/Adam/RNG/cursor and all16 inference heads; independent continuation, literal losses and native metrics still required'},indent=2)+'\n')
 print('ADMITTED exact checkpoint restoration and all16 heads',flush=True)
if __name__=='__main__':main()
