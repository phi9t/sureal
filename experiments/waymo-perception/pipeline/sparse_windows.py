"""Lossless sparse BEV window bucketing for a declared attention treatment."""
import numpy as np


def partition_sparse_windows(coordinates,*,window_shape,shift):
    """Return padded token-index buckets; padding is never an observation.

    Coordinates are [batch,y,x] unique nonnegative integer voxel identities.
    The shifted origin is (-shift_y,-shift_x); boundaries use mathematical floor.
    There is no cyclic wrap, foreground selection, token cap or diffusion.
    Buckets round each window occupancy up to a power of two, using fewer than
    twice as many slots as real tokens. The caller masks padding in attention.
    This is a common-head mechanism candidate, not an official SWFormer port.
    """
    c=np.asarray(coordinates)
    if (c.ndim!=2 or c.shape[1]!=3 or c.dtype.kind not in 'iu'
            or np.any(c<0) or len(np.unique(c,axis=0))!=len(c)):
        raise ValueError('unique nonnegative native [batch,y,x] integer coordinates required')
    if (len(window_shape)!=2 or len(shift)!=2
            or any(type(v) is not int or v<=0 for v in window_shape)
            or any(type(s) is not int or abs(s)>=w for s,w in zip(shift,window_shape))):
        raise ValueError('positive window shape and explicit bounded integer origin shift required')
    groups={}
    for index,(batch,y,x) in enumerate(c):
        key=(int(batch),(int(y)+shift[0])//window_shape[0],
             (int(x)+shift[1])//window_shape[1])
        groups.setdefault(key,[]).append(index)
    by_capacity={}
    for key,indices in sorted(groups.items()):
        capacity=1<<(len(indices)-1).bit_length()
        by_capacity.setdefault(capacity,[]).append((key,indices))
    buckets={}
    for capacity,windows in by_capacity.items():
        indices=np.full((len(windows),capacity),-1,dtype=np.int64)
        valid=np.zeros_like(indices,dtype=bool)
        relative=np.zeros((*indices.shape,2),dtype=np.int64)
        for row,(key,tokens) in enumerate(windows):
            indices[row,:len(tokens)]=tokens;valid[row,:len(tokens)]=True
            for column,index in enumerate(tokens):
                relative[row,column]=[(int(c[index,1])+shift[0])%window_shape[0],
                                      (int(c[index,2])+shift[1])%window_shape[1]]
        buckets[capacity]={'window_keys':np.array([key for key,_ in windows],dtype=np.int64),
                           'token_indices':indices,'valid_mask':valid,'relative_coordinates':relative}
    return {'tokens':len(c),'windows':len(groups),'buckets':buckets,
            'window_shape':window_shape,'shift':shift}
