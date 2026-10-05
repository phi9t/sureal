"""One-frame native untrained range frontend verification."""
import hashlib,importlib.util,json,time
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F
from geometry.native_range_grid import native_range_grid
from pipeline.range_frontend import RangeFrontend
from detection.pillar_packing import pack_points
from detection.packed_point_features import packed_point_features
from detection.pillar_encoder import decorate
from detection.pillar_detector import PillarDetector
from pipeline.range_pillar_hybrid import RangePillarFeatureNet,SharedPillarHead
assert importlib.util.find_spec('tensorflow') is None
assert torch.cuda.device_count()==1
torch.manual_seed(17);torch.cuda.manual_seed_all(17)
torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
d=json.loads(Path('/mnt/trusted.json').read_text());grids=[];source_points=[];points=eligible=0
started=time.monotonic()
for r in d['rows']:
 p=Path('/source/reconstruction')/r['artifact'];assert hashlib.file_digest(p.open('rb'),'sha256').hexdigest()==r['sha256']
 with np.load(p,allow_pickle=False) as a:
  identity={k:r[k] for k in ['context','timestamp','laser','return','motion']};identity['pixels']=a['pixels']
  record={'identity':identity,'return_present':True,'observations':{'physical_features':a['physical_features'],'xyz':a['xyz']},'targets':{'segmentation':a['segmentation']},'evaluation':{'nlz':a['nlz']}}
  g=native_range_grid(record,r['native_shape']);grids.append(g);source_points.append(np.concatenate([a['xyz'],a['physical_features'][:,1:2]],axis=1));points+=r['points'];eligible+=int(g['semantic_supervised'].sum())
assert len(grids)==2 and eligible>0
raw=torch.from_numpy(np.stack([g['measurements'] for g in grids])).permute(0,3,1,2).float().cuda()
valid=torch.from_numpy(np.stack([g['valid'] for g in grids])).cuda()
labels=torch.from_numpy(np.stack([g['semantic_labels'] for g in grids])).long().cuda()
packed=pack_points(np.concatenate(source_points),roi=(-64.,-64.,-3.,64.,64.,5.),cell_size=(.25,.25),max_pillars=20000,max_points=32,seed=17)
packed_physical=torch.from_numpy(packed['points']).float().cuda();counts=torch.from_numpy(packed['counts']).cuda();coordinates=torch.from_numpy(packed['coordinates']).cuda();indices=torch.from_numpy(packed['source_indices']).cuda()
model=RangeFrontend().cuda().train();pfn=RangePillarFeatureNet(32).cuda().train();head=SharedPillarHead(PillarDetector(nx=512,ny=512,classes=3,anchors_per_cell=2,cell_size=(.25,.25),origin=(-64.,-64.))).cuda().train();load_seconds=time.monotonic()-started
torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats();started=time.monotonic()
result=model(raw,valid)
for value in result.values():assert torch.isfinite(value).all()
assert int(valid.sum())==points
supervised=valid&(labels>0);assert int(supervised.sum())==eligible
logits=result['semantic_logits'].permute(0,2,3,1)[supervised]
semantic=F.cross_entropy(logits,labels[supervised])
# No box labels: this term merely exercises the independent foreground head.
foreground=result['foreground_logits'][:,0][valid].square().mean()
point_features=[]
for i,g in enumerate(grids):
 y,x=g['point_pixels'].T
 point_features.append(result['features'][i,:,torch.from_numpy(y).cuda(),torch.from_numpy(x).cuda()].T)
point_features=torch.cat(point_features);assert len(point_features)==points
retained_features=packed_point_features(point_features,indices,counts)
assert torch.equal(retained_features[indices>=0],point_features[indices[indices>=0]])
decorated=decorate(packed_physical,counts,coordinates,cell_size=(.25,.25),origin=(-64.,-64.))
pillars=pfn(decorated,retained_features,counts);predictions=head(pillars,coordinates,batch_size=1)
assert all(torch.isfinite(v).all() for v in predictions.values())
# Synthetic detector objective checks connectivity, not label fitting.
detector_objective=sum(v.square().mean() for v in predictions.values())
(semantic+foreground+detector_objective).backward()
assert all(p.grad is not None and torch.isfinite(p.grad).all() for module in (pfn,head) for p in module.parameters())
assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
torch.cuda.synchronize();elapsed=time.monotonic()-started;peak=torch.cuda.max_memory_allocated()
started=time.monotonic();gathered=0
for i,g in enumerate(grids):
 y,x=g['point_pixels'].T
 features=result['features'][i,:,torch.from_numpy(y).cuda(),torch.from_numpy(x).cuda()].T
 assert features.shape==(len(y),32) and torch.isfinite(features).all();gathered+=len(features)
assert gathered==points
torch.cuda.synchronize();gather_seconds=time.monotonic()-started
r={'status':'native ungated range point pillar shared-head forward/backward passed','frame':d['frame'],'sensor':'TOP','returns':[1,2],'native_shapes':[g['native_shape'] for g in grids],'points':points,'eligible_point_elements':eligible,'gathered_features':gathered,'channels':32,'parameter_count':sum(p.numel() for module in (model,pfn,head) for p in module.parameters()),'packing':packed['counts_report'],'prediction_shapes':{k:list(v.shape) for k,v in predictions.items()},'foreground_selection':'disabled','semantic_support_scope':'all valid native points, independent of pillar sampling','load_and_grid_seconds':load_seconds,'forward_backward_seconds':elapsed,'gather_seconds':gather_seconds,'peak_allocated_bytes':peak,'seed':17,'optimizer_steps':0,'device':torch.cuda.get_device_name(),'scope':'engineering native ungated hybrid; native semantics and synthetic foreground/detector objectives; zero optimizer updates, no trained detection or held-out accuracy claim'}
Path('/outputs/check.json').write_text(json.dumps(r,indent=2));print('PASS native range frontend',r)
