"""Live GPU shape/backprop and independently computed balanced objective."""
import json,math
from pathlib import Path
import numpy as np
import torch
from tier1.catalog import catalog
from tier1.models import build,objective,deterministic
cases=catalog();base=cases['baseline'];balanced=cases['class_balanced_focal'];labels=torch.tensor([[1,1,1,1,2,3,4]],device='cuda');box=torch.zeros(1,7,7,device='cuda');direction=torch.zeros(1,7,dtype=torch.long,device='cuda')
x=torch.zeros(1,7,4,device='cuda',requires_grad=True);output={'classification':x,'box_residuals':box,'direction':torch.zeros(1,7,2,device='cuda')};v=objective(output,[labels,box,direction],balanced)
# At zero logits, weighting positive classes preserves sum but changes positive gradient.
v['classification'].backward();focal_derivative=.25*(-.5**2*.5-2*.5*.25*math.log(2));weights={1:7/16,2:7/4,3:7/4,4:7/4}
for i,c in enumerate(labels[0].tolist()):assert math.isclose(x.grad[0,i,c-1].item(),focal_derivative*weights[c]/7,rel_tol=2e-6)
for i,c in enumerate(labels[0].tolist()):
 for j in range(4):
  if j!=c-1:assert math.isclose(x.grad[0,i,j].item(),-.75*focal_derivative/.25/7,rel_tol=2e-6)
with np.load('/tmp/fixture/observations.npz') as a:obs=[torch.from_numpy(a[k]).cuda() for k in ['points','counts','coordinates']]
obs[0]=obs[0].float()
with np.load('/tmp/targets/targets.npz') as a:truth=[torch.from_numpy(a[k]).cuda()[None] for k in ['labels','box_targets','direction_targets']]
truth[1]=truth[1].float();results=[]
for name,case in cases.items():
 if name in ['retain64','all_pillars']:continue
 deterministic();m=build(case).cuda();m.train();o=m(*obs,batch_size=1);assert o['classification'].shape==(1,512*512//4*8,4);loss=objective(o,truth,case);loss['total'].backward();assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in m.parameters())
 if name=='foreground_prior':assert torch.allclose(m.class_head.bias,torch.full_like(m.class_head.bias,math.log(.01/.99)))
 results.append(name);print('PASS forward/backward',name,flush=True);del m,o,loss;torch.cuda.empty_cache()
Path('/outputs/check.json').write_text(json.dumps({'forward_backward_variants':results,'independent_balanced_positive_gradient':True,'negative_gradient_unchanged':True}));print('PASS live model contracts')
