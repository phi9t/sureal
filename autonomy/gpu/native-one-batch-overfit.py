"""Preregistered single fixed training-batch overfit; final heads require native scoring."""
import hashlib,importlib.util,json,resource,time
from pathlib import Path
import numpy as np
import torch
from detection.pillar_detector import PillarDetector
from detection.detector_loss import detector_loss
assert importlib.util.find_spec('tensorflow') is None
assert torch.cuda.is_available() and torch.cuda.device_count()==1
manifest=json.loads(Path('/tmp/inputs/manifest.json').read_text())
assert manifest['execution']['updates']==2000 and manifest['execution']['seed']==17 and len(manifest['frames'])==1
start=time.monotonic();torch.manual_seed(17)
torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
torch.backends.cudnn.deterministic=True;torch.backends.cudnn.benchmark=False
torch.use_deterministic_algorithms(True)
frames=[]
for frame in manifest['frames']:
 directory=Path('/tmp/native')/frame['relative_directory']
 for name,digest in frame['sha256'].items():assert hashlib.sha256((directory/name).read_bytes()).hexdigest()==digest
 with np.load(directory/'observations.npz',allow_pickle=False) as data:
  assert set(data.files)=={'points','counts','coordinates'}
  observations=tuple(torch.from_numpy(data[key].astype(np.float32) if key=='points' else data[key]).pin_memory() for key in ['points','counts','coordinates'])
 with np.load(directory/'targets.npz',allow_pickle=False) as data:
  targets=tuple(torch.from_numpy(data[key].astype(np.float32) if key=='box_targets' else data[key]).pin_memory()[None] for key in ['labels','box_targets','direction_targets'])
 frames.append((observations,targets))
model=PillarDetector(nx=512,ny=512,classes=4,anchors_per_cell=8,cell_size=(.25,.25),origin=(-64.,-64.)).cuda()
optimizer=torch.optim.Adam(model.parameters(),lr=1e-4,betas=(.9,.999),eps=1e-8,weight_decay=0,foreach=False)
torch.cuda.reset_peak_memory_stats()
def evaluate(save=False):
 model.eval();result=[]
 with torch.no_grad():
  for index,(observation,target) in enumerate(frames):
   points,counts,coordinates=[x.cuda(non_blocking=True) for x in observation]
   labels,boxes,directions=[x.cuda(non_blocking=True) for x in target]
   output=model(points,counts,coordinates,batch_size=1)
   losses=detector_loss(output['classification'],output['box_residuals'],output['direction'],labels,boxes,directions)
   result.append({key:value.item() for key,value in losses.items()})
   if save:
    np.savez(Path('/outputs')/('heads-%02d.npz'%index),**{key:value[0].cpu().numpy() for key,value in output.items()})
 return result
initial=evaluate();print('BASELINE mean loss',sum(x['total'] for x in initial)/len(frames),flush=True)
rng=np.random.Generator(np.random.PCG64(17));order=[];step_records=[];train_start=time.monotonic()
for step in range(2000):
 if not order:order=rng.permutation(len(frames)).tolist()
 index=order.pop(0);observation,target=frames[index]
 points,counts,coordinates=[x.cuda(non_blocking=True) for x in observation]
 labels,boxes,directions=[x.cuda(non_blocking=True) for x in target]
 model.train();optimizer.zero_grad(set_to_none=True)
 output=model(points,counts,coordinates,batch_size=1)
 losses=detector_loss(output['classification'],output['box_residuals'],output['direction'],labels,boxes,directions)
 losses['total'].backward()
 assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
 norm=torch.nn.utils.clip_grad_norm_(model.parameters(),10,error_if_nonfinite=True);optimizer.step()
 assert all(torch.isfinite(p).all() for p in model.parameters())
 step_records.append({'step':step+1,'frame_index':index,'loss':losses['total'].item(),'gradient_norm_before_clip':norm.item()})
 assert time.monotonic()-start<7200
 assert torch.cuda.max_memory_allocated()<=8*1024**3
 assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss<=16*1024**2
 if (step+1)%100==0:print('UPDATE',step+1,'loss',step_records[-1]['loss'],'seconds',time.monotonic()-train_start,flush=True)
final=evaluate(save=True);torch.cuda.synchronize()
checkpoint=Path('/outputs/checkpoint.pt')
torch.save({'model':model.state_dict(),'optimizer':optimizer.state_dict(),'steps':2000,'manifest_sha256':hashlib.sha256(Path('/tmp/inputs/manifest.json').read_bytes()).hexdigest(),'torch_rng':torch.get_rng_state(),'cuda_rng':torch.cuda.get_rng_state(),'sampling_rng':rng.bit_generator.state,'remaining_frame_order':order},checkpoint)
a=sum(x['total'] for x in initial)/len(frames);b=sum(x['total'] for x in final)/len(frames)
report={'scope':'training-only one-batch overfit execution; APH/export acceptance still requires independent native scoring','updates':2000,'initial_eval_losses':initial,'final_eval_losses':final,'initial_mean_loss':a,'final_mean_loss':b,'loss_reduction_fraction':1-b/a,'loss_gate_passed':1-b/a>=.8,'step_records':step_records,'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_reserved_bytes':torch.cuda.max_memory_reserved(),'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'elapsed_seconds':time.monotonic()-start,'torch':torch.__version__,'device':torch.cuda.get_device_name(0),'deterministic_algorithms':True,'tf32':False,'seed':17,'checkpoint_sha256':hashlib.sha256(checkpoint.read_bytes()).hexdigest()}
Path('/outputs/check.json').write_text(json.dumps(report,indent=2)+'\n');print('TERMINAL native overfit execution; loss gate',report['loss_gate_passed'],'reduction',report['loss_reduction_fraction'],flush=True)
