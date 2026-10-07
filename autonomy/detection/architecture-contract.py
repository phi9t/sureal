import json
from pathlib import Path
import torch
from detection.pillar_detector import PillarDetector
from detection.norm_variants import configure_norm
from detection.architecture_variants import configure_architecture,ResidualUnit

def make():
 torch.manual_seed(17)
 return configure_norm(PillarDetector(nx=8,ny=8,classes=4,anchors_per_cell=8,cell_size=(.25,.25),origin=(-1.,-1.)),'gn_backbone')
reference=make(); shared={k:v.clone() for k,v in reference.state_dict().items()}
results=[]
for variant in ['deep_pfn','context_pfn','residual_bev']:
 model=configure_architecture(make(),variant).cuda().eval()
 for name,value in model.state_dict().items():
  normalized=name.replace('.unit.','.')
  if normalized in shared:assert torch.equal(value.cpu(),shared[normalized]),name
 points=torch.randn(3,5,4,device='cuda');counts=torch.tensor([3,4,5],device='cuda');coords=torch.tensor([[0,0,1,1],[0,0,2,2],[0,0,3,3]],device='cuda')
 # Full forward preserves native head interface and all parameters receive gradients.
 out=model(points,counts,coords,batch_size=1)
 assert out['classification'].shape==(1,128,4)
 sum(x.square().mean() for x in out.values()).backward()
 assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
 if variant!='residual_bev':
  from detection.pillar_encoder import decorate
  d=decorate(points,counts,coords,cell_size=(.25,.25),origin=(-1.,-1.))
  a=model.encoder(d,counts=counts)
  reordered=d.clone()
  for i,n in enumerate(counts.tolist()):reordered[i,:n]=d[i,:n].flip(0)
  b=model.encoder(reordered,counts=counts)
  torch.testing.assert_close(a,b,atol=2e-6,rtol=2e-6)
  if variant=='context_pfn':
   c=model.encoder(torch.cat([d,torch.zeros(3,2,9,device='cuda')],dim=1),counts=counts)
   torch.testing.assert_close(a,c,atol=2e-6,rtol=2e-6)
 results.append(variant)
unit=ResidualUnit(torch.nn.Sequential(torch.nn.Conv2d(8,8,3,padding=1,bias=False),torch.nn.GroupNorm(8,8),torch.nn.ReLU())).cuda()
with torch.no_grad():unit.unit[0].weight.zero_()
x=torch.rand(2,8,4,4,device='cuda');assert torch.equal(unit(x),x)
try:configure_architecture(make(),'bad')
except ValueError:pass
else:raise AssertionError('unknown variant accepted')
Path('/outputs/check.json').write_text(json.dumps({'variants':results,'shape_gradient_permutation_shared_weights':True,'context_eval_padding_extension':True,'residual_zero_branch_identity':True,'scope':'live candidate contract; no native quality admission'}))
print('PASS architecture live contracts',results)
