"""Exact continuation state, bound to externally supplied experiment identity.

Over-budget terminal time is retained honestly; the caller rejects resource
admission and continuation independently. The caller separately admits
source/input/runtime identities and persisted file
hashes. This module never treats a checkpoint's own identity as trusted.
"""
import copy,math,random
import numpy as np
import torch

KEYS={'identity','steps','frame_cursor','training_seconds','model','optimizer','rng'}

def _validate(saved,model,optimizer,identity):
 if not isinstance(saved,dict) or set(saved)!=KEYS or saved['identity']!=identity:raise ValueError('checkpoint identity/state differs')
 step=saved['steps'];seconds=saved['training_seconds']
 if type(step) is not int or not 0<=step<=32000 or type(saved['frame_cursor']) is not int or saved['frame_cursor']!=step%16:raise ValueError('invalid update/frame cursor')
 if isinstance(seconds,bool) or not isinstance(seconds,(int,float)) or not math.isfinite(seconds) or seconds<0:raise ValueError('invalid synchronized training time')
 current=model.state_dict();state=saved['model']
 if not isinstance(state,dict) or state.keys()!=current.keys():raise ValueError('model state incomplete')
 for key,value in state.items():
  if not isinstance(value,torch.Tensor) or value.shape!=current[key].shape or value.dtype!=current[key].dtype or not torch.isfinite(value).all():raise ValueError('model values invalid')
 old=saved['optimizer'];new=optimizer.state_dict()
 if not isinstance(old,dict) or set(old)!=set(new) or len(old['param_groups'])!=len(new['param_groups']):raise ValueError('optimizer state incomplete')
 for a,b in zip(old['param_groups'],new['param_groups']):
  if a!=b:raise ValueError('optimizer recipe/parameter mapping differs')
 params=[(pid,p) for index,group in enumerate(optimizer.param_groups) for pid,p in zip(new['param_groups'][index]['params'],group['params'])]
 if set(old['state'])!=({pid for pid,p in params} if step else set()):raise ValueError('optimizer parameter state incomplete')
 for pid,param in params:
  if not step:continue
  entry=old['state'][pid]
  if set(entry)!={'step','exp_avg','exp_avg_sq'} or not all(isinstance(x,torch.Tensor) and torch.isfinite(x).all() for x in entry.values()):raise ValueError('Adam moments invalid')
  if entry['step'].numel()!=1 or entry['step'].item()!=step or any(entry[key].shape!=param.shape or entry[key].dtype!=param.dtype for key in ['exp_avg','exp_avg_sq']):raise ValueError('Adam update/shape differs')
 rng=saved['rng']
 if not isinstance(rng,dict) or set(rng)!={'python','numpy','torch','cuda'}:raise ValueError('RNG state incomplete')
 if not isinstance(rng['torch'],torch.Tensor) or rng['torch'].dtype!=torch.uint8 or rng['torch'].shape!=torch.get_rng_state().shape:raise ValueError('Torch RNG shape differs')
 numpy_state=rng['numpy']
 if not isinstance(numpy_state,tuple) or len(numpy_state)!=5 or numpy_state[0]!='MT19937' or not isinstance(numpy_state[1],torch.Tensor) or numpy_state[1].shape!=(624,) or numpy_state[1].dtype!=torch.int64 or torch.any((numpy_state[1]<0)|(numpy_state[1]>=2**32)):raise ValueError('NumPy RNG state invalid')
 expected_devices=torch.cuda.device_count() if torch.cuda.is_available() else 0
 if not isinstance(rng['cuda'],list) or len(rng['cuda'])!=expected_devices or any(not isinstance(x,torch.Tensor) or x.dtype!=torch.uint8 or x.ndim!=1 for x in rng['cuda']):raise ValueError('CUDA RNG topology differs')
 # Validate Python/NumPy values on isolated generators before changing live RNG.
 try:
  torch.Generator(device='cpu').set_state(rng['torch'].cpu())
  for device,value in enumerate(rng['cuda']):torch.Generator(device=torch.device('cuda',device)).set_state(value.cpu())
  random.Random().setstate(rng['python']);probe=np.random.RandomState();probe.set_state((numpy_state[0],numpy_state[1].cpu().numpy().astype(np.uint32),*numpy_state[2:]))
 except (TypeError,ValueError,OverflowError,RuntimeError) as error:raise ValueError('RNG values invalid') from error

def capture_state(model,optimizer,identity,steps,training_seconds):
 numpy_state=np.random.get_state();rng={'python':random.getstate(),'numpy':(numpy_state[0],torch.from_numpy(numpy_state[1].astype(np.int64)),*numpy_state[2:]),'torch':torch.get_rng_state(),'cuda':torch.cuda.get_rng_state_all() if torch.cuda.is_available() else []}
 saved=copy.deepcopy({'identity':identity,'steps':steps,'frame_cursor':steps%16,'training_seconds':training_seconds,'model':model.state_dict(),'optimizer':optimizer.state_dict(),'rng':rng})
 _validate(saved,model,optimizer,identity);return saved

def restore_state(saved,model,optimizer,expected_identity):
 _validate(saved,model,optimizer,expected_identity);model.load_state_dict(saved['model']);optimizer.load_state_dict(copy.deepcopy(saved['optimizer']));rng=saved['rng'];state=rng['numpy'];random.setstate(rng['python']);np.random.set_state((state[0],state[1].cpu().numpy().astype(np.uint32),*state[2:]));torch.set_rng_state(rng['torch'].cpu())
 if rng['cuda']:torch.cuda.set_rng_state_all([x.cpu() for x in rng['cuda']])
 return saved['steps'],saved['frame_cursor'],saved['training_seconds']
