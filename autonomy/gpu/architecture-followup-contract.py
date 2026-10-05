import json
from pathlib import Path
import torch
from detection.pillar_detector import PillarDetector
from gpu.norm_variants import configure_norm
from gpu.architecture_followups import configure_followup,WindowAttention,CoarseMLP
from detection.pillar_encoder import decorate

def make():
 torch.manual_seed(17)
 return configure_norm(PillarDetector(nx=64,ny=64,classes=4,anchors_per_cell=8,cell_size=(.25,.25),origin=(-8.,-8.)),'gn_backbone')
for variant in ['masked_pfn','window_bev','coarse_mlp']:
 reference=make();model=configure_followup(make(),variant).cuda().eval()
 for k,v in reference.state_dict().items():assert torch.equal(v,model.state_dict()[k].cpu()),k
 points=torch.randn(3,5,4,device='cuda');counts=torch.tensor([3,4,5],device='cuda');coords=torch.tensor([[0,0,1,1],[0,0,2,2],[0,0,3,3]],device='cuda')
 out=model(points,counts,coords,batch_size=1);assert out['classification'].shape==(1,8192,4)
 sum(x.square().mean() for x in out.values()).backward();assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
 if variant=='masked_pfn':
  d=decorate(points,counts,coords,cell_size=(.25,.25),origin=(-8.,-8.));a=model.encoder(d,counts=counts)
  reordered=d.clone()
  for i,n in enumerate(counts.tolist()):reordered[i,:n]=d[i,:n].flip(0)
  torch.testing.assert_close(a,model.encoder(reordered,counts=counts),atol=2e-6,rtol=2e-6)
  b=model.encoder(torch.cat([d,torch.zeros(3,2,9,device='cuda')],1),counts=counts);torch.testing.assert_close(a,b,atol=2e-6,rtol=2e-6)
block=WindowAttention().cuda();x=torch.randn(2,256,16,16,device='cuda');assert torch.equal(block.unpartition(block.partition(x),2,16,16),x)
with torch.no_grad():block.output.weight.zero_()
assert torch.equal(block(x),x)
control=CoarseMLP().cuda();assert sum(p.numel() for p in control.parameters())==sum(p.numel() for p in block.parameters())
with torch.no_grad():control.output.weight.zero_()
assert torch.equal(control(x),x)
Path('/outputs/check.json').write_text(json.dumps({'variants':['masked_pfn','window_bev','coarse_mlp'],'shape_gradients_shared_weights':True,'window_partition_inverse':True,'zero_projection_identity':True,'masked_eval_padding_extension':True}));print('PASS live followup architecture contracts')
