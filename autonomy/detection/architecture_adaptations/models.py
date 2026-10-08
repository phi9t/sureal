"""Single pure factory used by native training, contracts and exact replay."""
import torch
from torch import nn
from detection.pillar_encoder import decorate,scatter
from detection.detector_recipe_models import build as build_reference,objective,optimizer,deterministic
from detection.architecture_adaptations.point_modules import RaggedPillar,PointAttention,PointMLP,decorate_ragged
from detection.architecture_adaptations.spatial_modules import configure_grid,SparseBackbone
from range_view.range_fusion import RangePillar

class AdvancedDetector(nn.Module):
 def __init__(self,base,encoder,*,ragged=False,sparse=False):
  super().__init__();self.nx,self.ny=base.nx,base.ny;self.cell_size,self.origin=base.cell_size,base.origin;self.classes,self.anchors_per_cell=base.classes,base.anchors_per_cell;self.encoder=encoder;self.ragged=ragged;self.upsample=base.upsample;self.class_head,self.box_head,self.direction_head=base.class_head,base.box_head,base.direction_head
  if sparse:self.spatial=SparseBackbone()
  else:self.blocks=base.blocks;self.spatial=None
 def decorate_points(self,points,counts,coordinates):return (decorate_ragged if self.ragged else decorate)(points,counts,coordinates,cell_size=self.cell_size,origin=self.origin)
 def forward(self,points,counts,coordinates,*,batch_size):
  decorated=self.decorate_points(points,counts,coordinates);features=self.encoder(decorated,counts) if not self.spatial else self.encoder(decorated)
  if self.spatial:images=self.spatial(features,coordinates,batch_size=batch_size);parts=[up(image) for up,image in zip(self.upsample,images)]
  else:
   image=scatter(features,coordinates,batch_size=batch_size,nx=self.nx,ny=self.ny);parts=[]
   for block,up in zip(self.blocks,self.upsample):image=block(image);parts.append(up(image))
  joined=torch.cat(parts,1)
  def flatten(head,width):return head(joined).permute(0,2,3,1).contiguous().reshape(batch_size,-1,width)
  return {'classification':flatten(self.class_head,self.classes),'box_residuals':flatten(self.box_head,7),'direction':flatten(self.direction_head,2)}

def build(case):
 name=case['architecture'];base=build_reference({**case,'architecture':'baseline'})
 if name in ['grid_fine','grid_coarse']:return configure_grid(base,name)
 if name=='ragged_pillars':return AdvancedDetector(base,RaggedPillar(base.encoder),ragged=True)
 if name=='point_attention':return AdvancedDetector(base,PointAttention(base.encoder))
 if name=='point_mlp_control':return AdvancedDetector(base,PointMLP(base.encoder))
 if name in ['range_fusion','zero_range_control']:return AdvancedDetector(base,RangePillar(base.encoder,zero_range=name=='zero_range_control'))
 if name=='sparse_bev_transformer':return AdvancedDetector(base,base.encoder,sparse=True)
 raise ValueError('unknown advanced architecture')

def bind_observations(model,auxiliary):
 if isinstance(model.encoder,RangePillar):model.encoder.set_observations(auxiliary)
