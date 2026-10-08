"""Structural support diagnostic, not an attribution of trained model errors."""
import json
from pathlib import Path
import numpy as np
import torch
from detection.pillar_detector import PillarDetector
from detection.architecture_adaptations.spatial_modules import SparseBackbone
model=PillarDetector(nx=512,ny=512,classes=4,anchors_per_cell=8,cell_size=(.25,.25),origin=(-64.,-64.))
assert [layer[0].stride for layer in model.upsample]==[(1,1),(2,2),(4,4)]
assert [layer[0].kernel_size for layer in model.upsample]==[(1,1),(2,2),(4,4)]
assert len(SparseBackbone().blocks)==3
with np.load('/source/observations.npz',allow_pickle=False) as f:coords=f['coordinates']
with np.load('/source/targets.npz',allow_pickle=False) as f:labels=f['labels'];objects=f['target_indices']
assert coords.shape[1]==4 and np.all(coords[:,:2]==0) and np.all((coords[:,2:]>=0)&(coords[:,2:]<512))
assert labels.shape==(256*256*8,) and objects.shape==labels.shape
assert np.all(objects[labels>0]>=0)
support=np.zeros((256,256),dtype=bool)
for divisor,repeat in [(2,1),(4,2),(8,4)]:
 coarse=coords[:,2:]//divisor;mask=np.zeros((512//divisor,512//divisor),dtype=bool);mask[coarse[:,0],coarse[:,1]]=True
 support|=np.repeat(np.repeat(mask,repeat,axis=0),repeat,axis=1)
# Separate direct membership calculation, without dense-mask expansion.
occupied={tuple(x) for x in coords[:,2:]//8}
reference=np.array([(y//4,x//4) in occupied for y in range(256) for x in range(256)],dtype=bool).reshape(256,256)
assert np.array_equal(reference,support)
anchor_support=np.repeat(support.ravel(),8);report={}
for cls in range(1,5):
 positive=labels==cls;ids=np.unique(objects[positive]);per_object=[]
 for obj in ids:
  slots=positive&(objects==obj);per_object.append({'target_index':int(obj),'positive_anchors':int(slots.sum()),'supported_positive_anchors':int((slots&anchor_support).sum())})
 report[str(cls)]={'positive_anchors':int(positive.sum()),'unsupported_positive_anchors':int((positive&~anchor_support).sum()),'objects':len(ids),'objects_without_supported_positive_anchor':sum(x['supported_positive_anchors']==0 for x in per_object),'object_support':per_object}
result={'classes':report,'unsupported_head_cells':int((~support).sum()),'total_head_cells':support.size,'background_anchors_without_local_support':int(((labels==0)&~anchor_support).sum()),'scope':'Structural local occupied-token support only. Global normalization statistics can couple cells. Missing local support is not a measured attribution of AP errors; supported cells can also fail. No architecture treatment or scientific promotion.'}
Path('/outputs/check.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:{x:v for x,v in val.items() if x!='object_support'} for k,val in report.items()}))
