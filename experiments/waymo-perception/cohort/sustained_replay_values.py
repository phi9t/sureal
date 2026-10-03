"""Literal recursive replay equality; never trusts producer equality claims.

Wall time may differ between independent executions. Its exclusion must be
explicit and applies only to the top-level training_seconds field.
"""
import math
import numpy as np
import torch

def require_exact_state(expected,actual,*,exclude_training_seconds=False):
 def compare(left,right,path):
  if isinstance(left,torch.Tensor):
   if not isinstance(right,torch.Tensor) or left.dtype!=right.dtype or left.shape!=right.shape or not torch.isfinite(left).all() or not torch.isfinite(right).all() or not torch.equal(left.detach().cpu(),right.detach().cpu()):raise ValueError(f'replay tensor differs: {path}')
  elif type(left) is not type(right):raise ValueError(f'replay type differs: {path}')
  elif isinstance(left,dict):
   if left.keys()!=right.keys():raise ValueError(f'replay keys differ: {path}')
   for key in left:
    if exclude_training_seconds and path=='state' and key=='training_seconds':continue
    compare(left[key],right[key],f'{path}.{key}')
  elif isinstance(left,(tuple,list)):
   if len(left)!=len(right):raise ValueError(f'replay length differs: {path}')
   for index,(a,b) in enumerate(zip(left,right)):compare(a,b,f'{path}[{index}]')
  elif isinstance(left,float) and (not math.isfinite(left) or not math.isfinite(right)):raise ValueError(f'nonfinite replay scalar: {path}')
  elif left!=right:raise ValueError(f'replay scalar differs: {path}')
 compare(expected,actual,'state')

def require_exact_heads(expected,actual):
 if expected.keys()!=actual.keys():raise ValueError('replay head keys differ')
 for key,left in expected.items():
  right=actual[key]
  if not isinstance(left,np.ndarray) or not isinstance(right,np.ndarray) or left.dtype!=right.dtype or left.shape!=right.shape or not np.isfinite(left).all() or not np.isfinite(right).all() or not np.array_equal(left,right):raise ValueError(f'replay head differs: {key}')
