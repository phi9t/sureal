"""Deterministic no-subsampling PointPillars assignment from measured overlaps.

Similarity geometry is an explicit external contract, not assumed to be native
rotated 3D IoU. Thresholds must come from the frozen training configuration.
"""
import numpy as np


def assign_overlaps(overlaps,classes,*,positive,negative):
    overlaps=np.asarray(overlaps,dtype=np.float64)
    classes=np.asarray(classes)
    if overlaps.ndim!=2 or classes.shape!=(overlaps.shape[1],):
        raise ValueError('anchor by target overlaps and target classes required')
    if classes.dtype.kind not in 'iu' or np.any(classes<=0):
        raise ValueError('positive integer target classes required')
    if not np.isfinite(overlaps).all() or np.any(overlaps<0) or np.any(overlaps>1):
        raise ValueError('finite IoU values in [0,1] required')
    if not np.isfinite([positive,negative]).all() or not 0<=negative<positive<=1:
        raise ValueError('ordered scalar assignment thresholds required')
    count,targets=overlaps.shape
    labels=np.full(count,-1,dtype=np.int64)
    indices=np.full(count,-1,dtype=np.int64)
    if not count or not targets:
        labels[:]=0
        return {'labels':labels,'target_indices':indices}
    best=overlaps.argmax(axis=1)
    maximum=overlaps[np.arange(count),best]
    target_maximum=overlaps.max(axis=0)
    forced=np.any((overlaps==target_maximum[None,:]) & (target_maximum[None,:]>0),axis=1)
    labels[maximum<negative]=0
    positive_mask=(maximum>=positive)|forced
    labels[positive_mask]=classes[best[positive_mask]]
    indices[positive_mask]=best[positive_mask]
    return {'labels':labels,'target_indices':indices}
