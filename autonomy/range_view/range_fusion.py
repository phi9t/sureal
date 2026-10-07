"""Physical-only native range features and baseline-preserving additive fusion."""
import torch
from torch import nn
from torch.nn import functional as F
from pipeline.range_frontend import Block


def bilinear_resize(values,size):
 result=values
 for axis,length in [(2,size[0]),(3,size[1])]:
  current=result.shape[axis];position=((torch.arange(length,device=result.device,dtype=result.dtype)+.5)*current/length-.5).clamp(0,current-1);lower=position.floor().long();upper=(lower+1).clamp_max(current-1);shape=[1]*result.ndim;shape[axis]=length;weight=(position-lower).reshape(shape);result=result.index_select(axis,lower)*(1-weight)+result.index_select(axis,upper)*weight
 return result

class RangeFeatures(nn.Module):
 def __init__(self):
  super().__init__();self.register_buffer('channel_maxima',torch.tensor([79.5,2.,2.]).reshape(1,3,1,1));self.first=Block(3,32);self.second=Block(32,64);self.third=Block(64,128);self.up_second=Block(192,64);self.up_first=Block(96,32)
 def forward(self,raw,valid):
  if raw.ndim!=4 or raw.shape[1]!=3 or min(raw.shape[2:])<2 or valid.shape!=(raw.shape[0],*raw.shape[2:]) or valid.dtype!=torch.bool or valid.device!=raw.device or not torch.isfinite(raw).all():raise ValueError('physical range/intensity/elongation and valid-pixel mask required')
  normalized=(raw/self.channel_maxima.to(raw.dtype)).clamp(0,1)*valid[:,None];first=self.first(normalized);second=self.second(F.max_pool2d(first,2,ceil_mode=True));third=self.third(F.max_pool2d(second,2,ceil_mode=True));up=self.up_second(torch.cat((bilinear_resize(third,second.shape[2:]),second),1));return self.up_first(torch.cat((bilinear_resize(up,first.shape[2:]),first),1))*valid[:,None]

class RangePillar(nn.Module):
 def __init__(self,encoder,*,zero_range=False):
  super().__init__();self.linear,self.norm=encoder.linear,encoder.norm;self.frontend=RangeFeatures();self.projection=nn.Linear(32,64,bias=False);nn.init.zeros_(self.projection.weight);self.zero_range=zero_range;self.grid_keys=[]
 def set_observations(self,auxiliary):
  pixels=auxiliary['range_pixels']
  if pixels.ndim!=3 or pixels.shape[-1]!=3 or pixels.dtype not in (torch.int32,torch.int64) or torch.any(pixels[:,:,0]<-1) or torch.any(pixels[:,:,0]>9) or torch.any(pixels[pixels[:,:,0]<0]!=-1):raise ValueError('packed native sensor/return/pixel identity required')
  self.register_buffer('range_pixels',pixels,persistent=False);self.grid_keys=[]
  for number,(laser,ret) in enumerate((l,r) for l in range(1,6) for r in (1,2)):
   raw_key=f'range_raw_{laser}_{ret}';valid_key=f'range_valid_{laser}_{ret}';mask=pixels[:,:,0]==number
   if raw_key not in auxiliary:
    if torch.any(mask):raise ValueError('measured point refers to absent range grid')
    continue
   raw,valid=auxiliary[raw_key],auxiliary[valid_key]
   if raw.ndim!=4 or raw.shape[:2]!=(1,3) or valid.shape!=(1,*raw.shape[2:]) or valid.dtype!=torch.bool or raw.device!=pixels.device or valid.device!=pixels.device or not torch.isfinite(raw).all():raise ValueError('native physical-only auxiliary observations required')
   rows,cols=pixels[mask][:,1:].unbind(1)
   if torch.any(rows<0) or torch.any(cols<0) or torch.any(rows>=raw.shape[2]) or torch.any(cols>=raw.shape[3]) or not torch.all(valid[0,rows,cols]):raise ValueError('packed range pixels outside valid native measurements')
   self.register_buffer(raw_key,raw,persistent=False);self.register_buffer(valid_key,valid,persistent=False);self.grid_keys.append((number,raw_key,valid_key))
  if not self.grid_keys:raise ValueError('range observations absent')
 def forward(self,decorated,counts):
  if not self.grid_keys or decorated.shape[:2]!=self.range_pixels.shape[:2]:raise ValueError('range observations differ from packed pillars')
  valid=torch.arange(decorated.shape[1],device=decorated.device)[None]<counts[:,None]
  if not torch.equal(valid,self.range_pixels[:,:,0]>=0):raise ValueError('range pixel padding differs from physical point counts')
  gathered=decorated.new_zeros((*decorated.shape[:2],32))
  for number,raw_key,valid_key in self.grid_keys:
   features=self.frontend(getattr(self,raw_key),getattr(self,valid_key));mask=self.range_pixels[:,:,0]==number;rows,cols=self.range_pixels[mask][:,1:].unbind(1);gathered[mask]=features[0,:,rows,cols].T
  if self.zero_range:gathered=gathered*0
  values=self.linear(decorated)+self.projection(gathered);return torch.relu(self.norm(values.transpose(1,2))).amax(2)
