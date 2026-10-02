"""Exact mathematical tensor state equality independent of serialized placement."""
import torch

def same_tensor_values(left,right):
 return isinstance(right,torch.Tensor) and left.dtype==right.dtype and left.shape==right.shape and torch.equal(left.detach().cpu(),right.detach().cpu())
