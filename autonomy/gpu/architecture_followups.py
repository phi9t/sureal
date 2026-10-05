"""Concrete masked-pooling control and coarse window attention candidates."""
import math
import torch
from torch import nn
from gpu.architecture_variants import EncodedDetector

class MaskedPillar(nn.Module):
 def __init__(self,encoder):super().__init__();self.linear,self.norm=encoder.linear,encoder.norm
 def forward(self,decorated,counts=None):
  if counts is None or counts.shape!=(len(decorated),) or torch.any(counts<=0) or torch.any(counts>decorated.shape[1]):raise ValueError('valid retained counts required')
  value=torch.relu(self.norm(self.linear(decorated).transpose(1,2)))
  valid=torch.arange(decorated.shape[1],device=decorated.device)[None,:]<counts[:,None]
  return value.masked_fill(~valid[:,None,:],-torch.inf).amax(2)

class WindowAttention(nn.Module):
 def __init__(self):
  super().__init__();self.norm=nn.GroupNorm(8,256,eps=1e-3);self.qkv=nn.Conv2d(256,768,1,bias=False);self.output=nn.Conv2d(256,256,1,bias=False)
 def partition(self,x):
  b,c,h,w=x.shape
  if c%4 or h%8 or w%8:raise ValueError('window-compatible dimensions required')
  return x.reshape(b,c,h//8,8,w//8,8).permute(0,2,4,3,5,1).reshape(-1,64,c)
 def unpartition(self,x,b,h,w):
  return x.reshape(b,h//8,w//8,8,8,-1).permute(0,5,1,3,2,4).reshape(b,-1,h,w)
 def forward(self,x):
  b,c,h,w=x.shape
  if c!=256:raise ValueError('256-channel coarse grid required')
  freq=10000**(-torch.arange(64,device=x.device,dtype=x.dtype)/64)
  px=freq[:,None,None]*((torch.arange(w,device=x.device,dtype=x.dtype)+.5)/w)[None,None,:]
  py=freq[:,None,None]*((torch.arange(h,device=x.device,dtype=x.dtype)+.5)/h)[None,:,None]
  pos=torch.cat([px.sin().expand(-1,h,-1),px.cos().expand(-1,h,-1),py.sin().expand(-1,-1,w),py.cos().expand(-1,-1,w)],0)
  q,k,v=self.partition(self.qkv(self.norm(x)+pos[None])).reshape(-1,64,3,4,64).permute(2,0,3,1,4).unbind(0)
  attended=((q@k.transpose(-1,-2))/math.sqrt(64)).softmax(-1)@v
  values=attended.transpose(1,2).reshape(-1,64,256)
  return x+self.output(self.unpartition(values,b,h,w))

class CoarseMLP(nn.Module):
 def __init__(self):
  super().__init__();self.norm=nn.GroupNorm(8,256,eps=1e-3);self.input=nn.Conv2d(256,512,1,bias=False);self.output=nn.Conv2d(512,256,1,bias=False)
 def forward(self,x):return x+self.output(torch.relu(self.input(self.norm(x))))

def configure_followup(model,variant):
 if variant=='masked_pfn':return EncodedDetector(model,MaskedPillar(model.encoder))
 if variant=='window_bev':model.blocks[2].append(WindowAttention());return model
 if variant=='coarse_mlp':model.blocks[2].append(CoarseMLP());return model
 raise ValueError('unknown followup variant')
