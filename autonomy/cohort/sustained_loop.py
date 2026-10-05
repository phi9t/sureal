"""Bounded deterministic one-frame-per-update loop for the fixed16 cohort."""
import math,resource,time
import torch
from cohort.sustained_state import capture_state,restore_state


def advance(model,optimizer,frames,objective,identity,target_step,*,checkpoint=None,clock=time.perf_counter):
 if type(target_step) is not int or not 0<=target_step<=32000 or len(frames)!=16:raise ValueError('bounded target and exact16 frames required')
 if checkpoint is None:start=0;seconds=0.
 else:
  if not isinstance(checkpoint,dict) or type(checkpoint.get('steps')) is not int or target_step<checkpoint['steps']:raise ValueError('cannot rewind or restore malformed state')
  start,_,seconds=restore_state(checkpoint,model,optimizer,identity)
 if target_step<start:raise ValueError('cannot rewind a continued trajectory')
 records=[];completed=start;reason='sample';maximum_step_seconds=0.
 for step in range(start,target_step):
  if seconds>7200:reason='resource_overrun';break
  if 7200-seconds<max(1.,2*maximum_step_seconds):reason='time_cap';break
  index=step%16;observations,targets=frames[index];device=next(model.parameters()).device
  if device.type=='cuda':torch.cuda.synchronize(device)
  began=clock();model.train();optimizer.zero_grad(set_to_none=True)
  observation=[x.to(device,non_blocking=device.type=='cuda') for x in observations]
  target=targets.to(device,non_blocking=device.type=='cuda') if isinstance(targets,torch.Tensor) else tuple(x.to(device,non_blocking=device.type=='cuda') for x in targets)
  output=model(*observation,batch_size=1);losses=objective(output,target)
  if not losses or any(not isinstance(x,torch.Tensor) or x.numel()!=1 or not torch.isfinite(x).all() for x in losses.values()) or 'total' not in losses:raise ValueError('finite scalar losses required')
  losses['total'].backward()
  if any(p.grad is None or not torch.isfinite(p.grad).all() for p in model.parameters()):raise ValueError('finite complete gradients required')
  norm=torch.nn.utils.clip_grad_norm_(model.parameters(),10,error_if_nonfinite=True);optimizer.step()
  if any(not torch.isfinite(p).all() for p in model.parameters()):raise ValueError('nonfinite model update')
  if device.type=='cuda':torch.cuda.synchronize(device)
  elapsed=clock()-began
  if not math.isfinite(elapsed) or elapsed<0:raise ValueError('invalid synchronized interval')
  seconds+=elapsed;completed=step+1;maximum_step_seconds=max(maximum_step_seconds,elapsed)
  records.append({'step':step+1,'frame_index':index,'losses':{key:float(value.detach()) for key,value in losses.items()},'gradient_norm_before_clip':float(norm),'clipped':bool(norm>10),'synchronized_seconds':elapsed})
  if seconds>7200:reason='resource_overrun';break
  if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>16*1024**2 or device.type=='cuda' and torch.cuda.max_memory_allocated(device)>8*1024**3:reason='resource_overrun';break
  if (step+1)%100==0:print('UPDATE',step+1,'frame',index,'train seconds',seconds,flush=True)
 return capture_state(model,optimizer,identity,completed,seconds),records,reason
