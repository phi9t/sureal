"""Preregistered single fixed training-batch overfit; final heads require native scoring."""
import hashlib,importlib.util,json,resource,time
from pathlib import Path
import numpy as np
import torch
from pipeline.pillar_detector import PillarDetector
from pipeline.detector_loss import detector_loss
from gpu.norm_variants import configure_norm
from gpu.architecture_variants import configure_architecture
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
model=configure_architecture(configure_norm(model,'gn_backbone'),manifest['architecture_variant']).cuda()
optimizer=torch.optim.Adam(model.parameters(),lr=1e-4,betas=(.9,.999),eps=1e-8,weight_decay=0,foreach=False)
torch.cuda.reset_peak_memory_stats()
curve=[];step_times=[];component_curve=[];gradient_curve=[]
checkpoints={0,25,50,100,200,300,500,750,1000,1500,2000}
def evaluate(save=False,step=None):
 model.eval();result=[]
 with torch.no_grad():
  for index,(observation,target) in enumerate(frames):
   points,counts,coordinates=[x.cuda(non_blocking=True) for x in observation]
   labels,boxes,directions=[x.cuda(non_blocking=True) for x in target]
   output=model(points,counts,coordinates,batch_size=1)
   losses=detector_loss(output['classification'],output['box_residuals'],output['direction'],labels,boxes,directions)
   result.append({key:value.item() for key,value in losses.items()})
   if save:
    directory=Path('/outputs') if step is None else Path('/outputs')/('checkpoint-%04d'%step)
    directory.mkdir(exist_ok=True)
    np.savez(directory/('heads-%02d.npz'%index),**{key:value[0].cpu().numpy() for key,value in output.items()})
   if step is not None:
    snapshots={name:value.clone() for name,value in model.named_buffers()}
    model.train()
    train_output=model(points,counts,coordinates,batch_size=1)
    train_losses=detector_loss(train_output['classification'],train_output['box_residuals'],train_output['direction'],labels,boxes,directions)
    for name,value in model.named_buffers():value.copy_(snapshots[name])
    model.eval()
    positive=labels>0;valid=labels>=0
    logits=output['classification'];y=(labels[:,:,None]==torch.arange(1,5,device='cuda')[None,None,:]).to(logits.dtype);prob=logits.sigmoid();correct=y*prob+(1-y)*(1-prob);alpha=.25*y+.75*(1-y)
    focal=alpha*(1-correct).square()*torch.nn.functional.binary_cross_entropy_with_logits(logits,y,reduction='none');normalizer=positive.sum().clamp_min(1)
    foreground=float((focal*positive[:,:,None]).sum()/normalizer);background=float((focal*(valid&~positive)[:,:,None]).sum()/normalizer)
    assert abs(foreground+background-losses['classification'].item())<=max(1e-4,1e-5*losses['classification'].item())
    component_curve.append({'step':step,'evaluation_losses':{k:v.item() for k,v in losses.items()},'batch_statistics_losses':{k:v.item() for k,v in train_losses.items()},'positive_focal':foreground,'negative_focal':background,'true_class_positive_probability_mean':float(prob[positive].gather(1,(labels[positive]-1)[:,None]).mean()),'negative_max_probability_mean':float(prob[labels==0].max(1).values.mean())})
 return result
initial=evaluate(save=True,step=0);curve.append({'step':0,'cumulative_train_seconds':0.,'evaluation_losses':initial});print('BASELINE mean loss',sum(x['total'] for x in initial)/len(frames),flush=True)
rng=np.random.Generator(np.random.PCG64(17));order=[];step_records=[];train_start=time.monotonic()
for step in range(2000):
 if not order:order=rng.permutation(len(frames)).tolist()
 index=order.pop(0);observation,target=frames[index];torch.cuda.synchronize();update_start=time.perf_counter()
 points,counts,coordinates=[x.cuda(non_blocking=True) for x in observation]
 labels,boxes,directions=[x.cuda(non_blocking=True) for x in target]
 model.train();optimizer.zero_grad(set_to_none=True)
 output=model(points,counts,coordinates,batch_size=1)
 losses=detector_loss(output['classification'],output['box_residuals'],output['direction'],labels,boxes,directions)
 losses['total'].backward()
 assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
 norm=torch.nn.utils.clip_grad_norm_(model.parameters(),10,error_if_nonfinite=True);optimizer.step()
 assert all(torch.isfinite(p).all() for p in model.parameters())
 torch.cuda.synchronize();step_times.append(time.perf_counter()-update_start)
 if step+1 in checkpoints:
  gradient_curve.append({'step':step+1,'norm_before_clip':norm.item(),'post_clip_head_gradient_norms':{name:float(torch.sqrt(sum((p.grad.double().square().sum() for p in module.parameters())))) for name,module in [('class',model.class_head),('box',model.box_head),('direction',model.direction_head),('encoder',model.encoder)]}})
  evaluation=evaluate(save=True,step=step+1);curve.append({'step':step+1,'cumulative_train_seconds':sum(step_times),'evaluation_losses':evaluation})
 step_records.append({'step':step+1,'frame_index':index,'loss':losses['total'].item(),'gradient_norm_before_clip':norm.item()})
 assert time.monotonic()-start<7200
 assert torch.cuda.max_memory_allocated()<=8*1024**3
 assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss<=16*1024**2
 if (step+1)%100==0:print('UPDATE',step+1,'loss',step_records[-1]['loss'],'seconds',time.monotonic()-train_start,flush=True)
final=evaluate(save=True);torch.cuda.synchronize()
checkpoint=Path('/outputs/checkpoint.pt')
torch.save({'model':model.state_dict(),'optimizer':optimizer.state_dict(),'steps':2000,'manifest_sha256':hashlib.sha256(Path('/tmp/inputs/manifest.json').read_bytes()).hexdigest(),'torch_rng':torch.get_rng_state(),'cuda_rng':torch.cuda.get_rng_state(),'sampling_rng':rng.bit_generator.state,'remaining_frame_order':order},checkpoint)
a=sum(x['total'] for x in initial)/len(frames);b=sum(x['total'] for x in final)/len(frames)
report={'scope':'training-only one-batch overfit execution; APH/export acceptance still requires independent native scoring','architecture_variant':manifest['architecture_variant'],'parameters':sum(p.numel() for p in model.parameters()),'updates':2000,'initial_eval_losses':initial,'final_eval_losses':final,'initial_mean_loss':a,'final_mean_loss':b,'loss_reduction_fraction':1-b/a,'loss_gate_passed':1-b/a>=.8,'step_records':step_records,'checkpoint_curve':curve,'component_curve':component_curve,'gradient_curve':gradient_curve,'synchronized_step_seconds':step_times,'cumulative_train_seconds':sum(step_times),'clipped_steps':sum(x['gradient_norm_before_clip']>10 for x in step_records),'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_reserved_bytes':torch.cuda.max_memory_reserved(),'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'elapsed_seconds':time.monotonic()-start,'torch':torch.__version__,'device':torch.cuda.get_device_name(0),'deterministic_algorithms':True,'tf32':False,'seed':17,'checkpoint_sha256':hashlib.sha256(checkpoint.read_bytes()).hexdigest(),'diagnostic_scope':'checkpoint grid and BN buffer-restored batch-statistics diagnostics; independent architecture checkpoint replay required'}
Path('/outputs/check.json').write_text(json.dumps(report,indent=2)+'\n');print('TERMINAL native overfit execution; loss gate',report['loss_gate_passed'],'reduction',report['loss_reduction_fraction'],flush=True)
