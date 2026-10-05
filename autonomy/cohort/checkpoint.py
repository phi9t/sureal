"""Separate replay of every initial/final head and retained Adam state."""
import hashlib,json
from pathlib import Path
import numpy as np
import torch
from detection.pillar_detector import PillarDetector
from gpu.norm_variants import configure_norm
from gpu.architecture_variants import configure_architecture
manifest=json.loads(Path('/tmp/inputs/manifest.json').read_text());torch.manual_seed(17);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.deterministic=True;torch.backends.cudnn.benchmark=False;torch.use_deterministic_algorithms(True)
def model():
 m=configure_norm(PillarDetector(nx=512,ny=512,classes=4,anchors_per_cell=8,cell_size=(.25,.25),origin=(-64.,-64.)),'gn_backbone')
 if manifest['architecture_variant']!='baseline':m=configure_architecture(m,manifest['architecture_variant'])
 return m.cuda().eval()
initial=model();final=model();checkpoint=torch.load('/tmp/retained/checkpoint.pt',weights_only=True,map_location='cpu');assert checkpoint['steps']==2000 and checkpoint['manifest_sha256']==hashlib.sha256(Path('/tmp/inputs/manifest.json').read_bytes()).hexdigest();final.load_state_dict(checkpoint['model'])
for index,frame in enumerate(manifest['frames']):
 directory=Path('/tmp/native')/frame['relative_directory']
 for name,h in frame['sha256'].items():assert hashlib.sha256((directory/name).read_bytes()).hexdigest()==h
 with np.load(directory/'observations.npz',allow_pickle=False) as a:points=torch.from_numpy(a['points'].astype(np.float32)).cuda();counts=torch.from_numpy(a['counts']).cuda();coordinates=torch.from_numpy(a['coordinates']).cuda()
 for step,m in [(0,initial),(2000,final)]:
  with torch.no_grad():heads=m(points,counts,coordinates,batch_size=1)
  with np.load(f'/tmp/retained/checkpoint-{step:04d}/heads-{index:02d}.npz',allow_pickle=False) as data:
   for key,value in heads.items():np.testing.assert_array_equal(value[0].cpu().numpy(),data[key])
 print('REPLAYED',index,flush=True)
state=checkpoint['optimizer'];group=state['param_groups'][0];assert len(state['param_groups'])==1 and group['lr']==1e-4 and tuple(group['betas'])==(.9,.999) and group['eps']==1e-8 and group['weight_decay']==0 and group['foreach'] is False
assert len(state['state'])==len(list(final.parameters()))==len(group['params'])
for pid,p in zip(group['params'],final.parameters()):
 s=state['state'][pid];assert s['step'].item()==2000 and s['exp_avg'].shape==s['exp_avg_sq'].shape==p.shape and all(torch.isfinite(v).all() for v in s.values())
Path('/outputs/check.json').write_text(json.dumps({'frames_exactly_replayed':16,'initial_and_final_heads_exact':True,'optimizer_updates':2000,'optimizer_state_validated':True}));print('PASS full cohort replay')
