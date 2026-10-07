"""Actual-frame CUDA admission: typed inputs, finite gradients and exact repetition."""
import hashlib, importlib.util, json, resource, time
from pathlib import Path
import numpy as np
import torch
from advanced.models import build,bind_observations,deterministic,objective,optimizer
from advanced.observations import load_observations
from tier1.models import build as reference_build
assert torch.cuda.is_available() and importlib.util.find_spec('tensorflow') is None
job=json.loads(Path('/tmp/inputs/job.json').read_text());case=job['case']
obs,aux=load_observations('/tmp/fixture/observations.npz','cuda')
with np.load('/tmp/targets/targets.npz',allow_pickle=False) as a:
 truth=[torch.from_numpy(a[k]).cuda()[None] for k in ('labels','box_targets','direction_targets')]
truth[1]=truth[1].float()
def value_hash(value):
 h=hashlib.sha256()
 def visit(v):
  if isinstance(v,torch.Tensor):
   a=v.detach().cpu().numpy();h.update(str(a.dtype).encode());h.update(str(a.shape).encode());h.update(np.ascontiguousarray(a).tobytes())
  elif isinstance(v,dict):
   for key in sorted(v,key=str):h.update(str(key).encode());visit(v[key])
  elif isinstance(v,(list,tuple)):
   for item in v:visit(item)
  else:h.update(repr(v).encode())
 visit(value);return h.hexdigest()
proof=[];start=time.monotonic();torch.cuda.reset_peak_memory_stats()
for repetition in range(2):
 deterministic();model=build(case).cuda();bind_observations(model,aux);opt=optimizer(model,case);model.eval()
 with torch.no_grad():
  output=model(*obs,batch_size=1)
  assert {k:tuple(v.shape) for k,v in output.items()}=={'classification':(1,524288,4),'box_residuals':(1,524288,7),'direction':(1,524288,2)}
  assert all(torch.isfinite(v).all() for v in output.values())
  initial=value_hash(output)
 if case['architecture'] in ('range_fusion','zero_range_control'):
  deterministic();reference=reference_build({**case,'architecture':'baseline'}).cuda().eval()
  with torch.no_grad():expected=reference(*obs,batch_size=1)
  assert all(torch.equal(output[k],expected[k]) for k in output),'zero-initialized range heads differ from baseline'
  del reference,expected
 for step in range(3):
  model.train();opt.zero_grad(set_to_none=True);output=model(*obs,batch_size=1);loss=objective(output,truth,case);loss['total'].backward()
  assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
  torch.nn.utils.clip_grad_norm_(model.parameters(),case['clip'],error_if_nonfinite=True);opt.step()
  assert all(torch.isfinite(p).all() for p in model.parameters())
  assert torch.cuda.max_memory_allocated()<=8*1024**3
  assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss<=16*1024**2
 parameters=sum(p.numel() for p in model.parameters())
 proof.append({'initial_heads':initial,'model':value_hash(model.state_dict()),'adam':value_hash(opt.state_dict()),'torch_rng':value_hash(torch.get_rng_state()),'cuda_rng':value_hash(torch.cuda.get_rng_state())})
 del model,opt,output,loss;torch.cuda.empty_cache()
assert proof[0]==proof[1],('nondeterministic native-frame trajectory',case['architecture'])
Path('/outputs/check.json').write_text(json.dumps({'case':case,'parameters':parameters,'exact_repeated_three_update_model_adam_rng':True,'finite_all_parameter_gradients':True,'fixed_head_shape':True,'proof':proof,'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'elapsed_seconds':time.monotonic()-start},indent=2))
print('PASS actual-frame CUDA admission',case['architecture'],flush=True)
