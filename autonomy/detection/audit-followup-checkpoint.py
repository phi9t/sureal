"""Separate native norm checkpoint/head and optimizer-state replay."""
import json,hashlib
from pathlib import Path
import numpy as np
import torch
from detection.pillar_detector import PillarDetector
from gpu.norm_variants import configure_norm
from gpu.architecture_followups import configure_followup
manifest=json.loads(Path('/tmp/inputs/manifest.json').read_text());variant=manifest['architecture_variant'];directory=Path('/tmp/native')/manifest['frames'][0]['relative_directory']
for name,h in manifest['frames'][0]['sha256'].items():assert hashlib.sha256((directory/name).read_bytes()).hexdigest()==h
torch.manual_seed(17);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.deterministic=True;torch.backends.cudnn.benchmark=False;torch.use_deterministic_algorithms(True)
with np.load(directory/'observations.npz',allow_pickle=False) as data:points=torch.from_numpy(data['points'].astype(np.float32)).cuda();counts=torch.from_numpy(data['counts']).cuda();coordinates=torch.from_numpy(data['coordinates']).cuda()
def model():return configure_followup(configure_norm(PillarDetector(nx=512,ny=512,classes=4,anchors_per_cell=8,cell_size=(.25,.25),origin=(-64.,-64.)),'gn_backbone'),variant).cuda().eval()
initial=model()
with torch.no_grad():
 heads=initial(points,counts,coordinates,batch_size=1)
 with np.load('/tmp/retained/checkpoint-0000/heads-00.npz',allow_pickle=False) as data:
  for key,value in heads.items():np.testing.assert_array_equal(value[0].cpu().numpy(),data[key])
checkpoint=torch.load('/tmp/retained/checkpoint.pt',weights_only=True,map_location='cpu');assert checkpoint['steps']==2000
assert checkpoint['manifest_sha256']==hashlib.sha256(Path('/tmp/inputs/manifest.json').read_bytes()).hexdigest()
final=model();final.load_state_dict(checkpoint['model'])
with torch.no_grad():
 heads=final(points,counts,coordinates,batch_size=1)
 with np.load('/tmp/retained/heads-00.npz',allow_pickle=False) as data:
  for key,value in heads.items():np.testing.assert_array_equal(value[0].cpu().numpy(),data[key])
for state in checkpoint['optimizer']['state'].values():assert state['step'].item()==2000 and all(torch.isfinite(x).all() for x in state.values())
assert len(checkpoint['optimizer']['state'])==len(list(final.parameters()))
groups=checkpoint['optimizer']['param_groups'];assert len(groups)==1
group=groups[0];assert group['lr']==1e-4 and tuple(group['betas'])==(.9,.999) and group['eps']==1e-8 and group['weight_decay']==0 and group['foreach'] is False
assert len(group['params'])==len(list(final.parameters()))
for pid,param in zip(group['params'],final.parameters()):
 state=checkpoint['optimizer']['state'][pid]
 assert state['exp_avg'].shape==state['exp_avg_sq'].shape==param.shape
 assert state['exp_avg'].dtype==state['exp_avg_sq'].dtype==param.dtype
Path('/outputs/check.json').write_text(json.dumps({'architecture_variant':variant,'initial_and_final_heads_exactly_replayed':True,'optimizer_updates':2000,'parameters':sum(p.numel() for p in final.parameters()),'scope':'live native norm checkpoint replay; native quality/curve audit separate'}));print('PASS independent native norm checkpoint replay',variant)
