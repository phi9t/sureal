"""Frozen-weight, one-frame BN-statistics diagnostic; no optimizer updates."""
import hashlib,importlib.util,json
from pathlib import Path
import numpy as np
import torch
from detection.pillar_detector import PillarDetector
from detection.detector_loss import detector_loss
assert importlib.util.find_spec('tensorflow') is None
manifest=json.loads(Path('/tmp/inputs/manifest.json').read_text());assert len(manifest['frames'])==1
frame=manifest['frames'][0];directory=Path('/tmp/native')/frame['relative_directory']
for name,h in frame['sha256'].items():assert hashlib.sha256((directory/name).read_bytes()).hexdigest()==h
torch.manual_seed(17);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.deterministic=True;torch.backends.cudnn.benchmark=False;torch.use_deterministic_algorithms(True)
with np.load(directory/'observations.npz',allow_pickle=False) as data:points=torch.from_numpy(data['points'].astype(np.float32)).cuda();counts=torch.from_numpy(data['counts']).cuda();coordinates=torch.from_numpy(data['coordinates']).cuda()
with np.load(directory/'targets.npz',allow_pickle=False) as data:labels=torch.from_numpy(data['labels']).cuda()[None];targets=torch.from_numpy(data['box_targets'].astype(np.float32)).cuda()[None];directions=torch.from_numpy(data['direction_targets']).cuda()[None]
checkpoint=torch.load('/tmp/baseline/checkpoint.pt',weights_only=True,map_location='cpu');assert checkpoint['steps']==2000
model=PillarDetector(nx=512,ny=512,classes=4,anchors_per_cell=8,cell_size=(.25,.25),origin=(-64.,-64.)).cuda();model.load_state_dict(checkpoint['model']);parameters={name:p.detach().clone() for name,p in model.named_parameters()}
with torch.no_grad():
 model.eval();before=model(points,counts,coordinates,batch_size=1)
 with np.load('/tmp/baseline/heads-00.npz',allow_pickle=False) as data:
  for key,value in before.items():np.testing.assert_array_equal(value[0].cpu().numpy(),data[key])
 before_loss=detector_loss(before['classification'],before['box_residuals'],before['direction'],labels,targets,directions)
 model.train();bn=[m for m in model.modules() if isinstance(m,(torch.nn.BatchNorm1d,torch.nn.BatchNorm2d))]
 for m in bn:m.momentum=1.
 model(points,counts,coordinates,batch_size=1) # Physical observations only; no labels in recalibration.
 model.eval();after=model(points,counts,coordinates,batch_size=1);after_loss=detector_loss(after['classification'],after['box_residuals'],after['direction'],labels,targets,directions)
 for name,p in model.named_parameters():assert torch.equal(p,parameters[name])
 np.savez('/outputs/heads-00.npz',**{key:value[0].cpu().numpy() for key,value in after.items()})
report={'scope':'frozen2000-update weights; one physical-frame momentum1 BN recalibration; zero optimizer updates; native quality acceptance separate','optimizer_updates':0,'weights_bitwise_unchanged':True,'control_heads_exactly_match_baseline':True,'BN_layers':len(bn),'before_losses':{k:v.item() for k,v in before_loss.items()},'after_losses':{k:v.item() for k,v in after_loss.items()},'checkpoint_sha256':hashlib.sha256(Path('/tmp/baseline/checkpoint.pt').read_bytes()).hexdigest(),'manifest_sha256':hashlib.sha256(Path('/tmp/inputs/manifest.json').read_bytes()).hexdigest()}
Path('/outputs/check.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS frozen-weight BN-statistics counterfactual',report['before_losses']['total'],report['after_losses']['total'])
