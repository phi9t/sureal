"""Independent literal pilot updates; intentionally never calls producer advance.

Restricted to the 35-update admission pilot. Scientific continuation still uses
its separately admitted bounded controller and full native score gates.
"""
import resource
import torch
from cohort.sustained_state import capture_state,restore_state

def reference_updates(model,optimizer,frames,objective,identity,target_step,*,checkpoint=None):
 start=0 if checkpoint is None else checkpoint.get('steps')
 if type(target_step) is not int or not 0<=target_step<=35 or type(start) is not int or not 0<=start<=target_step or len(frames)!=16:raise ValueError('bounded pilot target and full16 frames required')
 seconds=0.
 if checkpoint is not None:_,_,seconds=restore_state(checkpoint,model,optimizer,identity)
 device=next(model.parameters()).device
 for update in range(start,target_step):
  observations,targets=frames[update%16]
  model.train();optimizer.zero_grad(set_to_none=True)
  observations=tuple(t.to(device,non_blocking=device.type=='cuda') for t in observations)
  targets=targets.to(device,non_blocking=device.type=='cuda') if isinstance(targets,torch.Tensor) else tuple(t.to(device,non_blocking=device.type=='cuda') for t in targets)
  output=model(*observations,batch_size=1);terms=objective(output,targets)
  if not terms or 'total' not in terms or any(not isinstance(v,torch.Tensor) or v.numel()!=1 or not torch.isfinite(v).all() for v in terms.values()):raise ValueError('finite scalar losses required')
  terms['total'].backward()
  if any(p.grad is None or not torch.isfinite(p.grad).all() for p in model.parameters()):raise ValueError('finite complete gradients required')
  torch.nn.utils.clip_grad_norm_(model.parameters(),10,error_if_nonfinite=True);optimizer.step()
  if any(not torch.isfinite(p).all() for p in model.parameters()):raise ValueError('nonfinite model update')
  if device.type=='cuda':torch.cuda.synchronize(device)
  if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>16*1024**2 or device.type=='cuda' and torch.cuda.max_memory_allocated(device)>8*1024**3:raise ValueError('reference resource cap exceeded')
 return capture_state(model,optimizer,identity,target_step,seconds)
