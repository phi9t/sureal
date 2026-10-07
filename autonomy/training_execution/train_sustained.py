"""GPU-only frozen balanced16 chunk worker; no scientific admission by itself."""
import importlib.util,json,random,resource,time
from pathlib import Path
import numpy as np
import torch
from sustained.sustained_contract import validate_contract
from training_execution.sustained_loop import advance
from detection.sustained_loss import class_balanced_objective
from training_execution.sustained_state import restore_state
from training_execution.sustained_sources import validate_sources
from detection.fixed_batch_catalog import catalog
from detection.fixed_batch_models import build,objective,optimizer,deterministic
from resources.scientific_budget import reserve_write
from evidence.source_snapshot import file_sha256

sha=file_sha256

def relative(root,name):
 p=Path(name)
 if p.is_absolute() or '..' in p.parts:raise ValueError('safe relative input/code path required')
 return Path(root)/p

def main():
 if importlib.util.find_spec('tensorflow') is not None or not torch.cuda.is_available() or torch.cuda.device_count()!=1:raise ValueError('one native GPU and TensorFlow absence required')
 started=time.monotonic();manifest_path=Path('/source/manifest.json');manifest=json.loads(manifest_path.read_text());job=json.loads(Path('/source/job.json').read_text())
 frames_meta=manifest['frames'];admitted=[{k:f[k] for k in ['identity','split','sha256']} for f in frames_meta];validate_contract(manifest['candidate'],admitted)
 names={'baseline':'baseline','residual_bev':'residual_bev','class_balanced':'class_balanced_focal','prior_bias':'foreground_prior'}
 recipe=manifest['recipe']
 if recipe not in names:raise ValueError('unsupported frozen recipe')
 validate_sources('/experiment',manifest['source_hashes'],manifest['runtime_lock'],json.loads(Path('/tmp/runtime-lock.json').read_text()))
 identity={'manifest_sha256':sha(manifest_path),'source_hashes':manifest['source_hashes'],'runtime_lock':manifest['runtime_lock'],'recipe':recipe}
 deterministic();random.seed(17);np.random.seed(17);torch.cuda.reset_peak_memory_stats();frames=[]
 for frame in frames_meta:
  directory=relative('/tmp/native',frame['relative_directory'])
  for name,h in frame['sha256'].items():
   if sha(relative(directory,name))!=h:raise ValueError('native frame payload differs')
  with np.load(directory/'observations.npz',allow_pickle=False) as data:
   if set(data.files)!={'points','counts','coordinates'}:raise ValueError('observation slots differ')
   observations=tuple(torch.from_numpy(data[key].astype(np.float32) if key=='points' else data[key]).pin_memory() for key in ['points','counts','coordinates'])
  with np.load(directory/'targets.npz',allow_pickle=False) as data:
   targets=tuple(torch.from_numpy(data[key].astype(np.float32) if key=='box_targets' else data[key]).pin_memory()[None] for key in ['labels','box_targets','direction_targets'])
  frames.append((observations,targets))
 case=catalog()[names[recipe]];model=build(case).cuda();opt=optimizer(model,case)
 checkpoint=None;retained=Path('/tmp/retained/checkpoint.pt')
 if retained.exists():
  if sha(retained)!=job['retained_sha256']:raise ValueError('externally pinned checkpoint differs')
  checkpoint=torch.load(retained,map_location='cuda',weights_only=True)
 elif job.get('retained_sha256') is not None:raise ValueError('declared checkpoint missing')
 loss=class_balanced_objective if recipe=='class_balanced' else lambda out,targets:objective(out,targets,case)
 try:state,records,stop_reason=advance(model,opt,frames,loss,identity,job['target_step'],checkpoint=checkpoint)
 except ValueError as error:
  Path('/outputs/failure.json').write_text(json.dumps({'error':str(error),'manifest_sha256':identity['manifest_sha256'],'scope':'failed chunk; no checkpoint or fit admission'},indent=2));raise
 # Write admission reserves include uncompressed head tensors and full Adam/model.
 reserve_write('/tmp/scientific',sum(p.numel()*p.element_size() for p in model.parameters())*3+16*1024**2)
 saved=Path('/outputs/checkpoint.pt');torch.save(state,saved)
 head_dir=Path('/outputs/heads');head_dir.mkdir();evaluations=[];model.eval()
 with torch.no_grad():
  for index,(obs,targets) in enumerate(frames):
   observation=[x.cuda(non_blocking=True) for x in obs];truth=tuple(x.cuda(non_blocking=True) for x in targets);output=model(*observation,batch_size=1);terms=loss(output,truth);arrays={key:value[0].cpu().numpy() for key,value in output.items()}
   reserve_write('/tmp/scientific',sum(x.nbytes for x in arrays.values())+1024**2)
   np.savez_compressed(head_dir/f'heads-{index:02d}.npz',**arrays)
   labels=truth[0];prob=output['classification'].sigmoid();statistics={str(cls):{'positive_anchors':int((labels==cls).sum()),'positive_probability_mean':float(prob[:,:,cls-1][labels==cls].mean()) if (labels==cls).any() else None} for cls in range(1,5)}
   evaluations.append({'identity':frames_meta[index]['identity'],'losses':{k:float(v) for k,v in terms.items()},'class_statistics':statistics})
 restore_state(state,model,opt,identity)
 report={'recipe':recipe,'case':case,'updates':state['steps'],'requested_updates':job['target_step'],'stop_reason':stop_reason,'frame_cursor':state['frame_cursor'],'cumulative_train_seconds':state['training_seconds'],'step_records':records,'evaluation_losses':evaluations,'checkpoint_sha256':sha(saved),'head_hashes':{p.name:sha(p) for p in head_dir.iterdir()},'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'elapsed_seconds':time.monotonic()-started,'device':torch.cuda.get_device_name(0),'manifest_sha256':identity['manifest_sha256'],'scope':'training-only chunk; independent full16 GPU replay/literal losses/native scoring and retention required'}
 report['resource_gate_passed']=stop_reason!='resource_overrun' and state['training_seconds']<=7200 and report['peak_allocated_bytes']<=8*1024**3 and report['peak_rss_kib']<=16*1024**2
 Path('/outputs/check.json').write_text(json.dumps(report,indent=2));print('READY for independent chunk audits' if report['resource_gate_passed'] else 'RESOURCE-CENSORED; promotion forbidden',state['steps'],flush=True)

if __name__=='__main__':main()
