"""Resumable deterministic one-frame trajectory, or independent full replay."""
import hashlib,importlib.util,json,resource,sys,time
from pathlib import Path
import numpy as np
import torch
from tier1.admission import reserve_write
from detection.checkpoint_values import same_tensor_values
from tier1.models import build,objective,optimizer,deterministic
assert importlib.util.find_spec('tensorflow') is None and torch.cuda.is_available()
job=json.loads(Path('/tmp/inputs/job.json').read_text());case=job['case'];target=job['target'];replay=job.get('replay',False)
def digest(a):
 h=hashlib.sha256()
 for k in sorted(a):
  v=np.ascontiguousarray(a[k]);h.update(k.encode());h.update(str(v.dtype).encode());h.update(str(v.shape).encode());h.update(v.tobytes())
 return h.hexdigest()
with np.load('/tmp/fixture/observations.npz') as a:obs=[torch.from_numpy(a[k]).cuda() for k in ['points','counts','coordinates']]
obs[0]=obs[0].float()
with np.load('/tmp/targets/targets.npz') as a:truth=[torch.from_numpy(a[k]).cuda()[None] for k in ['labels','box_targets','direction_targets']]
truth[1]=truth[1].float();deterministic();model=build(case).cuda();opt=optimizer(model,case);start=0;curve=[];records=[];times=[];wall=time.monotonic()
retained=Path('/tmp/retained/checkpoint.pt')
expected=None
if retained.exists():
 with retained.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==job['retained_sha256']
if replay:expected=torch.load(retained,map_location='cuda',weights_only=False)
elif retained.exists():
 saved=torch.load(retained,map_location='cuda',weights_only=False);model.load_state_dict(saved['model']);opt.load_state_dict(saved['optimizer']);start=saved['steps'];curve=saved['curve'];records=saved['records'];times=saved['times'];torch.set_rng_state(saved['torch_rng'].cpu());torch.cuda.set_rng_state(saved['cuda_rng'].cpu())
def evaluate(step):
 model.eval()
 with torch.no_grad():
  output=model(*obs,batch_size=1);losses=objective(output,truth,case);arrays={k:v[0].cpu().numpy() for k,v in output.items()};head_hash=digest(arrays)
  if replay:
   found=next(x for x in expected['curve'] if x['step']==step);assert head_hash==found['head_sha256'],('replay heads',step)
   for k,v in losses.items():assert v.item()==found['evaluation_losses'][0][k]
  else:
   directory=Path('/outputs')/f'checkpoint-{step:04d}';directory.mkdir(exist_ok=True);reserve_write('/tmp/scientific',sum(a.nbytes for a in arrays.values())+1024*1024);np.savez_compressed(directory/'heads-00.npz',**arrays)
  snapshots={k:v.clone() for k,v in model.named_buffers()};model.train();train_output=model(*obs,batch_size=1);batch_losses=objective(train_output,truth,case)
  for k,v in model.named_buffers():v.copy_(snapshots[k])
  model.eval();labels=truth[0];prob=output['classification'].sigmoid();statistics={str(c):{'positive_anchors':int((labels==c).sum()),'true_class_probability_mean':float(prob[:,:,c-1][labels==c].mean())} for c in range(1,5)}
 positive=labels>0;valid=labels>=0;y=(labels[:,:,None]==torch.arange(1,5,device=labels.device)[None,None,:]).to(prob.dtype);correct=y*prob+(1-y)*(1-prob);terms=(.25*y+.75*(1-y))*(1-correct).square()*torch.nn.functional.binary_cross_entropy_with_logits(output['classification'],y,reduction='none');normalizer=positive.sum().clamp_min(1)
 if case['loss']=='class_balanced_positive':terms=terms*(1+y*(normalizer/(4*y.sum((0,1)))-1))
 positive_focal=float((terms*positive[:,:,None]).sum()/normalizer);negative_focal=float((terms*(valid&~positive)[:,:,None]).sum()/normalizer);assert abs(positive_focal+negative_focal-losses['classification'].item())<=max(2e-5,losses['classification'].item()*2e-5)
 return {'positive_focal':positive_focal,'negative_focal':negative_focal,'step':step,'cumulative_train_seconds':sum(times),'evaluation_losses':[{k:v.item() for k,v in losses.items()}],'batch_statistics_losses':{k:v.item() for k,v in batch_losses.items()},'head_sha256':head_hash,'class_statistics':statistics}
grid=[0,25,50,100,200,300,500,750,1000,1500,2000,3000,4000,6000,8000,10000]
if start==0:curve.append(evaluate(0))
torch.cuda.reset_peak_memory_stats()
for step in range(start+1,target+1):
 torch.cuda.synchronize();t=time.perf_counter();model.train();opt.zero_grad(set_to_none=True);output=model(*obs,batch_size=1);loss=objective(output,truth,case);loss['total'].backward()
 assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
 norm=torch.sqrt(sum(p.grad.detach().double().square().sum() for p in model.parameters()))
 if case['clip'] is not None:torch.nn.utils.clip_grad_norm_(model.parameters(),case['clip'],error_if_nonfinite=True)
 opt.step();assert all(torch.isfinite(p).all() for p in model.parameters());torch.cuda.synchronize();times.append(time.perf_counter()-t);records.append({'step':step,'loss':float(loss['total'].detach()),'gradient_norm_before_clip':float(norm)})
 if step in grid:
  entry=evaluate(step);entry['post_clip_gradient_norms']={name:float(torch.sqrt(sum(p.grad.detach().double().square().sum() for p in module.parameters()))) for name,module in [('class',model.class_head),('box',model.box_head),('direction',model.direction_head),('encoder',model.encoder)]};curve.append(entry)
 if step%500==0:print('UPDATE',step,'loss',float(loss['total'].detach()),'train seconds',sum(times),flush=True)
 assert torch.cuda.max_memory_allocated()<=8*1024**3 and resource.getrusage(resource.RUSAGE_SELF).ru_maxrss<=16*1024**2 and time.monotonic()-wall<7200
if replay:
 def same(a,b):
  if isinstance(a,torch.Tensor):assert same_tensor_values(a,b)
  elif isinstance(a,dict):
   assert a.keys()==b.keys()
   for k in a:same(a[k],b[k])
  elif isinstance(a,(list,tuple)):
   assert len(a)==len(b)
   for x,y in zip(a,b):same(x,y)
  else:assert a==b
 same(model.state_dict(),expected['model']);same(opt.state_dict(),expected['optimizer']);same(torch.get_rng_state(),expected['torch_rng'].cpu());same(torch.cuda.get_rng_state(),expected['cuda_rng'].cpu())
 report={'steps':target,'exact_all_checkpoint_heads':True,'exact_terminal_model_and_adam':True,'exact_rng':True,'recovered_checkpoint_diagnostics':curve}
else:
 checkpoint=Path('/outputs/checkpoint.pt');reserve_write('/tmp/scientific',sum(p.numel()*p.element_size() for p in model.parameters())*3+8*1024**2);torch.save({'model':model.state_dict(),'optimizer':opt.state_dict(),'steps':target,'curve':curve,'records':records,'times':times,'torch_rng':torch.get_rng_state(),'cuda_rng':torch.cuda.get_rng_state()},checkpoint)
 report={'updates':target,'case':case,'parameters':sum(p.numel() for p in model.parameters()),'checkpoint_curve':curve,'step_records':records,'synchronized_step_seconds':times,'cumulative_train_seconds':sum(times),'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'device':torch.cuda.get_device_name(),'torch':torch.__version__,'seed':17,'clipped_steps':sum(case['clip'] is not None and x['gradient_norm_before_clip']>case['clip'] for x in records),'checkpoint_sha256':hashlib.file_digest(checkpoint.open('rb'),'sha256').hexdigest(),'scope':'one fixed all-class training frame; independent replay/loss/native scoring required'}
Path('/outputs/check.json').write_text(json.dumps(report,indent=2));print('PASS', 'full trajectory replay' if replay else 'trajectory execution',target,flush=True)
