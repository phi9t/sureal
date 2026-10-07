"""Complete baseline tensor coverage despite wrapped residual module names."""
import re
import torch

def verify_shared_weights(reference,candidate):
 mapped={}
 for name,value in candidate.state_dict().items():
  m=re.fullmatch(r'blocks\.(\d+)\.(\d+)\.unit\.(\d+)\.(.+)',name)
  if m:
   stage,wrapped,local,tail=m.groups();original=4+3*(int(wrapped)-4)+int(local);name=f'blocks.{stage}.{original}.{tail}'
  assert name not in mapped,name
  mapped[name]=value
 for name,value in reference.state_dict().items():
  assert name in mapped,('missing shared tensor',name)
  assert torch.equal(value.cpu(),mapped[name].cpu()),('changed shared tensor',name)
 return len(reference.state_dict())
