"""Bounded NumPy delta components matching pinned Waymo channel-major semantics.

Protobuf/zlib/source identity and geometric reconstruction are separate gates.
"""
import math
import numpy as np

def _integers(values):
    array=np.asarray(values)
    if array.ndim!=1 or (array.size and array.dtype.kind not in 'iu'):
        raise ValueError('integer vector required')
    if array.size and (np.any(array>np.iinfo(np.int64).max) or np.any(array<np.iinfo(np.int64).min)):
        raise ValueError('int64 component bound')
    return array.astype(np.int64)

def decode_components(shape,precision,mask,residual,*,max_values=32*1024*1024):
    shape=_integers(shape)
    if len(shape)!=3 or np.any(shape<=0) or np.any(shape>65535):
        raise ValueError('positive native HWC dimensions required')
    if type(max_values) is not int or max_values<=0:
        raise ValueError('positive decoded-value cap required')
    total=math.prod(map(int,shape))
    if total>max_values:raise ValueError('decoded tensor exceeds cap')
    precision=np.asarray(precision,dtype=np.float64)
    if precision.shape!=(int(shape[2]),) or not np.isfinite(precision).all() or np.any(precision<=0):
        raise ValueError('finite positive channel precisions required')
    mask=_integers(mask);residual=_integers(residual)
    if not len(mask) or np.any(mask<0) or sum(map(int,mask))!=total:
        raise ValueError('run lengths must cover exactly HWC values')
    if sum(map(int,mask[::2]))!=len(residual):
        raise ValueError('one residual per nonzero encoded entry required')
    cumulative=np.cumsum(residual,dtype=np.int64)
    previous=np.r_[np.int64(0),cumulative[:-1]] if len(cumulative) else cumulative
    if np.any(((residual>=0)&(cumulative<previous))|((residual<0)&(cumulative>=previous))):
        raise ValueError('cumulative integer overflow')
    selected=np.repeat(np.arange(len(mask))%2==0,mask)
    flat=np.zeros(total,dtype=np.float64);flat[selected]=cumulative
    decoded=flat.reshape((int(shape[2]),int(shape[0]),int(shape[1]))).transpose(1,2,0)*precision
    if not np.isfinite(decoded).all():raise ValueError('nonfinite decoded tensor')
    return decoded
