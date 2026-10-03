"""Evaluation-only point-based NLZ overlap; never an encoder measurement.

Use all five LiDARs and both returns in one vehicle reference frame. The test
uses a closed upright box boundary and the documented +1/-1 NLZ convention.
Missing measurements or unknown flags fail rather than become no-overlap.
"""
import math
import numpy as np


def overlaps_nlz(box,sensor_returns):
    box=np.asarray(box,dtype=np.float64)
    if box.shape!=(7,) or not np.isfinite(box).all() or np.any(box[3:6]<=0):raise ValueError('upright box contract')
    required={(laser,ret) for laser in range(1,6) for ret in [1,2]}
    if set(sensor_returns)!=required:raise ValueError('all sensor returns required for NLZ evaluation')
    c,s=math.cos(box[6]),math.sin(box[6]);hit=False
    for points,flags in sensor_returns.values():
        points=np.asarray(points);flags=np.asarray(flags)
        if points.ndim!=2 or points.shape[1]!=3 or flags.shape!=(len(points),):raise ValueError('aligned point/flag contract')
        if not np.isfinite(points).all() or not np.all(np.isin(flags,[-1,1])):raise ValueError('unknown measurement or NLZ flag')
        selected=points[flags==1]-box[:3]
        x=c*selected[:,0]+s*selected[:,1];y=-s*selected[:,0]+c*selected[:,1]
        hit |= bool(np.any((np.abs(x)<=box[3]/2)&(np.abs(y)<=box[4]/2)&(np.abs(selected[:,2])<=box[5]/2)))
    return hit
