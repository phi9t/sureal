"""Evaluation-only point-based NLZ overlap; never an encoder measurement.

Use all five LiDARs and both returns in one vehicle reference frame. The test
uses a closed upright box boundary and the documented +1/-1 NLZ convention.
Missing measurements or unknown flags fail rather than become no-overlap.
"""
import numpy as np

from geometry.oriented_box import point_membership


def overlaps_nlz(box,sensor_returns):
    box=np.asarray(box,dtype=np.float64)
    if box.shape!=(7,) or not np.isfinite(box).all() or np.any(box[3:6]<=0):raise ValueError('upright box contract')
    required={(laser,ret) for laser in range(1,6) for ret in [1,2]}
    if set(sensor_returns)!=required:raise ValueError('all sensor returns required for NLZ evaluation')
    hit=False
    for points,flags in sensor_returns.values():
        points=np.asarray(points);flags=np.asarray(flags)
        if points.ndim!=2 or points.shape[1]!=3 or flags.shape!=(len(points),):raise ValueError('aligned point/flag contract')
        if not np.isfinite(points).all() or not np.all(np.isin(flags,[-1,1])):raise ValueError('unknown measurement or NLZ flag')
        hit |= bool(np.any(point_membership(points[flags==1],box)))
    return hit
