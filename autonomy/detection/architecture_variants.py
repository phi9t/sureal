"""Isolated architecture candidates; the reference modules remain unmodified."""
import torch
from torch import nn
from detection.pillar_encoder import decorate,scatter
from detection.norm_variants import PointChannelLayerNorm

class DeepPillar(nn.Module):
 def __init__(self,encoder):
  super().__init__();self.linear,self.norm=encoder.linear,encoder.norm
  self.second=nn.Linear(64,64,bias=False);self.second_norm=PointChannelLayerNorm(64)
 def forward(self,decorated,counts=None):
  first=torch.relu(self.norm(self.linear(decorated).transpose(1,2)))
  return torch.relu(self.second_norm(self.second(first.transpose(1,2)).transpose(1,2))).amax(2)

class ContextPillar(nn.Module):
 def __init__(self,encoder):
  super().__init__();self.linear,self.norm=encoder.linear,encoder.norm
  self.context=nn.Linear(192,64,bias=False);self.context_norm=PointChannelLayerNorm(64)
 def forward(self,decorated,counts=None):
  if counts is None or counts.shape!=(len(decorated),) or torch.any(counts<=0) or torch.any(counts>decorated.shape[1]):raise ValueError('valid retained counts required')
  first=torch.relu(self.norm(self.linear(decorated).transpose(1,2))).transpose(1,2)
  valid=torch.arange(decorated.shape[1],device=decorated.device)[None,:]<counts[:,None]
  maximum=first.masked_fill(~valid[:,:,None],-torch.inf).amax(1)
  mean=first.masked_fill(~valid[:,:,None],0).sum(1)/counts[:,None]
  context=torch.cat([maximum,mean],1)[:,None,:].expand(-1,decorated.shape[1],-1)
  transformed=torch.relu(self.context_norm(self.context(torch.cat([first,context],2)).transpose(1,2))).transpose(1,2)
  return transformed.masked_fill(~valid[:,:,None],-torch.inf).amax(1)

class ResidualUnit(nn.Module):
 def __init__(self,unit):super().__init__();self.unit=unit
 def forward(self,x):return torch.relu(x+self.unit(x))

class EncodedDetector(nn.Module):
 def __init__(self,detector,encoder):
  super().__init__()
  for attr in ['nx','ny','classes','anchors_per_cell','cell_size','origin']:setattr(self,attr,getattr(detector,attr))
  self.encoder=encoder
  for attr in ['blocks','upsample','class_head','box_head','direction_head']:setattr(self,attr,getattr(detector,attr))
 def forward(self,points,counts,coordinates,*,batch_size):
  d=decorate(points,counts,coordinates,cell_size=self.cell_size,origin=self.origin)
  image=scatter(self.encoder(d,counts=counts),coordinates,batch_size=batch_size,nx=self.nx,ny=self.ny)
  parts=[]
  for block,up in zip(self.blocks,self.upsample):image=block(image);parts.append(up(image))
  features=torch.cat(parts,1)
  def head(module,width):return module(features).permute(0,2,3,1).contiguous().reshape(batch_size,-1,width)
  return {'classification':head(self.class_head,self.classes),'box_residuals':head(self.box_head,7),'direction':head(self.direction_head,2)}

def configure_architecture(model,variant):
 if variant=='deep_pfn':return EncodedDetector(model,DeepPillar(model.encoder))
 if variant=='context_pfn':return EncodedDetector(model,ContextPillar(model.encoder))
 if variant=='residual_bev':
  for i,block in enumerate(model.blocks):
   children=list(block.children());model.blocks[i]=nn.Sequential(*children[:4],*[ResidualUnit(nn.Sequential(*children[j:j+3])) for j in range(4,len(children),3)])
  return model
 raise ValueError('unknown architecture variant')
