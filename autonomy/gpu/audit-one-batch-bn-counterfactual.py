"""Independent literal BN moment checks and frozen output replay."""
import json
from pathlib import Path
import numpy as np
import torch
from detection.pillar_detector import PillarDetector
manifest=json.loads(Path('/tmp/inputs/manifest.json').read_text());frame=manifest['frames'][0];directory=Path('/tmp/native')/frame['relative_directory']
torch.manual_seed(17);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.deterministic=True;torch.backends.cudnn.benchmark=False;torch.use_deterministic_algorithms(True)
with np.load(directory/'observations.npz',allow_pickle=False) as data:points=torch.from_numpy(data['points'].astype(np.float32)).cuda();counts=torch.from_numpy(data['counts']).cuda();coordinates=torch.from_numpy(data['coordinates']).cuda()
checkpoint=torch.load('/tmp/baseline/checkpoint.pt',weights_only=True,map_location='cpu');model=PillarDetector(nx=512,ny=512,classes=4,anchors_per_cell=8,cell_size=(.25,.25),origin=(-64.,-64.)).cuda();model.load_state_dict(checkpoint['model']);parameter_copies={name:p.detach().clone() for name,p in model.named_parameters()};moments={};handles=[]
def capture(module,args):
 value=args[0];dims=(0,*range(2,value.ndim));moments[id(module)]=(value.mean(dims),value.var(dims,unbiased=True))
for module in model.modules():
 if isinstance(module,(torch.nn.BatchNorm1d,torch.nn.BatchNorm2d)):
  module.momentum=1.;handles.append(module.register_forward_pre_hook(capture))
with torch.no_grad():
 model.train();model(points,counts,coordinates,batch_size=1)
 for module in model.modules():
  if id(module) in moments:
   mean,var=moments[id(module)];torch.testing.assert_close(module.running_mean,mean,rtol=2e-4,atol=2e-5);torch.testing.assert_close(module.running_var,var,rtol=2e-4,atol=2e-5)
 for h in handles:h.remove()
 model.eval();heads=model(points,counts,coordinates,batch_size=1)
 with np.load('/tmp/treatment/heads-00.npz',allow_pickle=False) as data:
  for key,value in heads.items():np.testing.assert_array_equal(value[0].cpu().numpy(),data[key])
 for name,p in model.named_parameters():assert torch.equal(p,parameter_copies[name])
Path('/outputs/check.json').write_text(json.dumps({'literal_BN_mean_and_unbiased_variance_checks':len(moments),'treatment_heads_replayed_exactly':True,'model_weights_bitwise_unchanged':True,'optimizer_updates':0,'scope':'separate live BN equation/output/parameter audit on the frozen one-batch checkpoint; no heldout claim'}));print('PASS independent BN moments, exact treatment heads, unchanged weights')
