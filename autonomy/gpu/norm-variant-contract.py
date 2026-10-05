import torch
from pipeline.pillar_detector import PillarDetector
from gpu.norm_variants import configure_norm

def model():
 torch.manual_seed(17);return PillarDetector(nx=512,ny=512,classes=4,anchors_per_cell=8,cell_size=(.25,.25),origin=(-64.,-64.))
reference=model();weights={n:p.clone() for n,p in reference.named_parameters() if 'norm' not in n}
for variant in ['gn_backbone','gn_backbone_ln_pillar','no_norm']:
 candidate=configure_norm(model(),variant)
 # Replacement must preserve original convolution/head initialization.
 for name,module in reference.named_modules():
  if isinstance(module,(torch.nn.Linear,torch.nn.Conv2d,torch.nn.ConvTranspose2d)):
   other=dict(candidate.named_modules())[name];torch.testing.assert_close(module.weight,other.weight,rtol=0,atol=0)
 gn=[m for m in candidate.modules() if isinstance(m,torch.nn.GroupNorm)]
 assert bool(gn)==(variant!='no_norm')
 if variant=='no_norm':assert not any(isinstance(m,(torch.nn.BatchNorm1d,torch.nn.BatchNorm2d,torch.nn.GroupNorm,torch.nn.LayerNorm)) for m in candidate.modules())
 if variant!='gn_backbone':assert not any(isinstance(m,(torch.nn.BatchNorm1d,torch.nn.BatchNorm2d)) for m in candidate.modules())
 if variant=='gn_backbone_ln_pillar':
  norm=candidate.encoder.norm;x=torch.randn(2,64,5);before=norm(x);changed=x.clone();changed[:,:,1:]*=10;after=norm(changed);torch.testing.assert_close(before[:,:,0],after[:,:,0],rtol=0,atol=0)
  norm.train();a=norm(x);norm.eval();torch.testing.assert_close(a,norm(x),rtol=0,atol=0)
 for norm in gn:
  x=torch.randn(2,norm.num_channels,4,4);before=norm(x);changed=x.clone();changed[1]*=10;torch.testing.assert_close(before[0],norm(changed)[0],rtol=0,atol=0)
  norm.train();a=norm(x);norm.eval();torch.testing.assert_close(a,norm(x),rtol=0,atol=0)
try:configure_norm(model(),'typo')
except ValueError:pass
else:raise AssertionError('unknown normalization silently accepted')
print('PASS norm contracts: same convolution weights, LN point independence, GN sample independence, no running-stat mode gap')
