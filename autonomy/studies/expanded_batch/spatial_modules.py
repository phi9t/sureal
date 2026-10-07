"""Fixed-head grid strides and a multiscale sparse occupied-token backbone."""
import math
import torch
from torch import nn
from detection.pillar_encoder import scatter
from studies.expanded_batch.sparse_sets import window_sets,pool_tokens

class SparseBlock(nn.Module):
 def __init__(self,width,*,spacing,axis,shift):
  super().__init__()
  if width<=0 or width%4 or spacing<=0:raise ValueError('four-head metric sparse block required')
  self.width,self.spacing,self.axis,self.shift=width,spacing,axis,shift;self.norm=nn.LayerNorm(width,eps=1e-3);self.position=nn.Linear(2,width,bias=False);self.qkv=nn.Linear(width,3*width,bias=False);self.output=nn.Linear(width,width,bias=False);self.after=nn.LayerNorm(width,eps=1e-3);self.ffn=nn.Sequential(nn.Linear(width,2*width),nn.GELU(),nn.Linear(2*width,width))
 def forward(self,features,coordinates):
  indices,valid=window_sets(coordinates,shift=self.shift,axis=self.axis);position=((coordinates[:,[3,2]].to(features.dtype)+.5)*self.spacing-64)/64;tokens=self.norm(features)+self.position(position);grouped=tokens[indices.clamp_min(0)].masked_fill(~valid[:,:,None],0);sets,slots,_=grouped.shape;head=self.width//4;q,k,v=self.qkv(grouped).reshape(sets,slots,3,4,head).permute(2,0,3,1,4).unbind(0);weights=((q@k.transpose(-1,-2))/math.sqrt(head)).masked_fill(~valid[:,None,None,:],-torch.inf).softmax(-1);attended=(weights@v).transpose(1,2).reshape(sets,slots,self.width);values=self.output(attended);update=torch.zeros_like(features);update[indices[valid]]=values[valid];result=features+update;return result+self.ffn(self.after(result))

class SparseBackbone(nn.Module):
 def __init__(self):
  super().__init__();self.projections=nn.ModuleList([nn.Identity(),nn.Linear(64,128,bias=False),nn.Linear(128,256,bias=False)]);self.blocks=nn.ModuleList([nn.ModuleList([SparseBlock(width,spacing=.5*2**level,axis='x',shift=0),SparseBlock(width,spacing=.5*2**level,axis='y',shift=4)]) for level,width in enumerate([64,128,256])])
 def forward(self,features,coordinates,*,batch_size):
  images=[]
  for level,(projection,blocks) in enumerate(zip(self.projections,self.blocks)):
   features,coordinates=pool_tokens(features,coordinates);features=projection(features)
   for block in blocks:features=block(features,coordinates)
   extent=256//2**level;images.append(scatter(features,coordinates,batch_size=batch_size,nx=extent,ny=extent))
  return images

def configure_grid(model,name):
 if name not in ('grid_fine','grid_coarse'):raise ValueError('grid treatment required')
 fine=name=='grid_fine';model.nx=model.ny=1024 if fine else 256;model.cell_size=(.125,.125) if fine else (.5,.5);model.blocks[0][1].stride=(4,4) if fine else (1,1);return model
