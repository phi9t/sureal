"""Deterministic segmented pillars and masked local point interactions."""
import math
import torch
from torch import nn
from torch.nn import functional as F


def decorate_ragged(points,counts,coordinates,*,cell_size,origin):
 if points.ndim!=2 or points.shape[1]!=4 or not points.is_floating_point() or counts.ndim!=1 or coordinates.shape!=(len(counts),4) or counts.dtype not in (torch.int32,torch.int64) or coordinates.dtype not in (torch.int32,torch.int64):raise ValueError('flat physical points, integer lengths and coordinates required')
 if len(counts)==0 or torch.any(counts<=0) or int(counts.sum())!=len(points) or not torch.isfinite(points).all() or any(t.device!=points.device for t in (counts,coordinates)):raise ValueError('nonempty exact finite segments required')
 if len(cell_size)!=2 or len(origin)!=2 or min(cell_size)<=0 or any(not math.isfinite(x) for x in (*cell_size,*origin)) or torch.any(coordinates<0) or torch.any(coordinates[:,1]!=0):raise ValueError('valid metric pillar coordinates required')
 mean=torch.segment_reduce(points[:,:3],reduce='mean',lengths=counts);center=torch.stack(((coordinates[:,3]+.5)*cell_size[0]+origin[0],(coordinates[:,2]+.5)*cell_size[1]+origin[1]),1).to(points.dtype)
 return torch.cat((points,points[:,:3]-torch.repeat_interleave(mean,counts,dim=0),points[:,:2]-torch.repeat_interleave(center,counts,dim=0)),1)

class RaggedPillar(nn.Module):
 def __init__(self,encoder):super().__init__();self.linear,self.norm=encoder.linear,encoder.norm
 def forward(self,decorated,counts):
  if decorated.ndim!=2 or decorated.shape[1]!=9 or counts.ndim!=1 or torch.any(counts<=0) or int(counts.sum())!=len(decorated):raise ValueError('nine-channel exact segments required')
  return torch.segment_reduce(torch.relu(self.norm(self.linear(decorated))),reduce='max',lengths=counts)

class PointBase(nn.Module):
 def __init__(self,encoder):
  super().__init__();self.linear,self.norm=encoder.linear,encoder.norm;self.before=nn.LayerNorm(64,eps=1e-3);self.position=nn.Linear(3,64,bias=False);self.after=nn.LayerNorm(64,eps=1e-3);self.ffn=nn.Sequential(nn.Linear(64,128),nn.GELU(),nn.Linear(128,64))
 def forward(self,decorated,counts):
  if decorated.ndim!=3 or decorated.shape[2]!=9 or counts.shape!=(len(decorated),) or torch.any(counts<=0) or torch.any(counts>decorated.shape[1]):raise ValueError('valid padded point tokens required')
  tokens=torch.relu(self.norm(self.linear(decorated).transpose(1,2))).transpose(1,2);results=[]
  for start in range(0,len(tokens),512):
   x=tokens[start:start+512];count=counts[start:start+512];valid=torch.arange(x.shape[1],device=x.device)[None]<count[:,None];position=self.position(decorated[start:start+512,:,4:7]);x=x+self.interact(self.before(x),position,valid);x=x+self.ffn(self.after(x));results.append(x.masked_fill(~valid[:,:,None],-torch.inf).amax(1))
  return torch.cat(results)

class PointAttention(PointBase):
 def __init__(self,encoder):super().__init__(encoder);self.qkv=nn.Linear(64,192,bias=False);self.output=nn.Linear(64,64,bias=False)
 def interact(self,x,position,valid):
  p,s,_=x.shape;all_values=self.qkv(x);pos=F.linear(position,self.qkv.weight[:128]);q,k,v=all_values.chunk(3,dim=-1);pq,pk=pos.chunk(2,dim=-1);q=(q+pq).reshape(p,s,4,16).transpose(1,2);k=(k+pk).reshape(p,s,4,16).transpose(1,2);v=v.reshape(p,s,4,16).transpose(1,2);logits=(q@k.transpose(-1,-2))/4;weights=logits.masked_fill(~valid[:,None,None,:],-torch.inf).softmax(-1);value=(weights@v).transpose(1,2).reshape(p,s,64);return self.output(value)

class PointMLP(PointBase):
 def __init__(self,encoder):super().__init__(encoder);self.input=nn.Linear(64,128,bias=False);self.output=nn.Linear(128,64,bias=False)
 def interact(self,x,position,valid):return self.output(F.gelu(self.input(x+position)))
