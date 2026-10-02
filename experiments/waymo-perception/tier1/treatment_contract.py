"""Explicit norm/module/initial-weight/optimizer contracts and cap equivalence."""
import json
from pathlib import Path
import numpy as np
import torch
from torch import nn
from tier1.models import build,optimizer
from tier1.catalog import catalog
from gpu.norm_variants import PointChannelLayerNorm
from gpu.architecture_variants import DeepPillar,ContextPillar,ResidualUnit
from gpu.architecture_followups import MaskedPillar,WindowAttention,CoarseMLP
cases=catalog();torch.manual_seed(17);reference=build(cases['baseline']);results=[]
base_conv=[m.weight.detach().clone() for m in reference.modules() if isinstance(m,nn.Conv2d) and m.kernel_size==(3,3)]
for name,case in cases.items():
 torch.manual_seed(17);m=build(case);opt=optimizer(m,case);assert not opt.state and opt.defaults['lr']==case['learning_rate'] and opt.defaults['betas']==(.9,.999) and opt.defaults['eps']==1e-8 and opt.defaults['weight_decay']==0 and opt.defaults['foreach'] is False
 conv=[n.weight for n in m.modules() if isinstance(n,nn.Conv2d) and n.kernel_size==(3,3)];assert len(conv)==len(base_conv) and all(torch.equal(a,b) for a,b in zip(base_conv,conv));assert torch.equal(reference.encoder.linear.weight,m.encoder.linear.weight)
 for head in ['class_head','box_head','direction_head']:
  assert torch.equal(getattr(reference,head).weight,getattr(m,head).weight)
  if not (head=='class_head' and case['foreground_prior'] is not None):assert torch.equal(getattr(reference,head).bias,getattr(m,head).bias)
 if case['norm']=='bn':assert any(isinstance(n,nn.BatchNorm2d) for n in m.modules())
 else:
  assert not any(isinstance(n,nn.BatchNorm2d) for n in m.modules())
  if case['norm']=='no_norm':assert not any(isinstance(n,(nn.BatchNorm1d,nn.GroupNorm,nn.LayerNorm)) for n in m.modules())
  else:
   assert all(n.num_groups==8 and n.eps==1e-3 for n in m.modules() if isinstance(n,nn.GroupNorm))
   if case['norm']=='gn_backbone_ln_pillar':assert isinstance(m.encoder.norm,PointChannelLayerNorm)
   else:assert isinstance(m.encoder.norm,nn.BatchNorm1d)
 expected={'deep_pfn':DeepPillar,'context_pfn':ContextPillar,'masked_pfn':MaskedPillar}
 if name in expected:assert isinstance(m.encoder,expected[name])
 if name=='residual_bev':assert sum(isinstance(n,ResidualUnit) for n in m.modules())==13
 if name=='window_bev':assert sum(isinstance(n,WindowAttention) for n in m.modules())==1
 if name=='coarse_mlp':assert sum(isinstance(n,CoarseMLP) for n in m.modules())==1
 results.append({'case':name,'parameters':sum(p.numel() for p in m.parameters()),'compatible_weights_exact':True,'optimizer_initialization_exact':True,'module_and_norm_inventory':True});del m,opt
x=torch.randn(3,64,7);norm=PointChannelLayerNorm(64);expected=(x-x.mean(1,keepdim=True))/torch.sqrt(x.var(1,unbiased=False,keepdim=True)+1e-3);torch.testing.assert_close(norm(x),expected,atol=2e-6,rtol=2e-6)
# Exact packed-array and initial-model inference equivalence for nonbinding pillar cap.
with np.load('/tmp/fixture/observations.npz') as a:obs=[torch.from_numpy(a[k]) for k in ['points','counts','coordinates']]
with np.load('/tmp/allpillars/observations.npz') as a:other=[torch.from_numpy(a[k]) for k in ['points','counts','coordinates']]
assert all(torch.equal(a,b) for a,b in zip(obs,other));obs[0]=obs[0].float();other[0]=other[0].float();reference.eval()
with torch.no_grad():
 a=reference(*obs,batch_size=1);b=reference(*other,batch_size=1);assert all(torch.equal(a[k],b[k]) for k in a)
Path('/outputs/check.json').write_text(json.dumps({'treatments':results,'point_ln_literal_channel_axis':True,'all_pillars_initial_inference_exact':True},indent=2));print('PASS treatment contracts and initial cap-equivalent inference',len(results))
