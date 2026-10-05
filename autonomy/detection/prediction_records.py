"""Prediction evaluation metadata from measured points; no GT annotation fields."""
import math
import numpy as np
from detection.detection_export import validate_object


def _overlaps_nlz(box,sensor_returns):
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


def prediction_records(proposals,*,context,timestamp,sensor_returns):
    if not isinstance(context,str) or not context or type(timestamp) is not int or not 0<=timestamp<2**63:
        raise ValueError('native frame identity required')
    boxes=np.asarray(proposals['boxes']);classes=np.asarray(proposals['classes'])
    scores=np.asarray(proposals['scores']);indices=np.asarray(proposals['anchor_indices'])
    n=len(boxes)
    if boxes.shape!=(n,7) or classes.shape!=(n,) or scores.shape!=(n,) or indices.shape!=(n,) or classes.dtype.kind not in 'iu' or indices.dtype.kind not in 'iu' or np.any(indices<0) or len(np.unique(indices))!=n:
        raise ValueError('paired native proposals and unique anchor indices required')
    # Validate measurement completeness even for an empty prediction catalog.
    _overlaps_nlz([0.,0.,0.,1.,1.,1.,0.],sensor_returns)
    records=[]
    for box,category,score,index in zip(boxes,classes,scores,indices):
        flag=_overlaps_nlz(box,sensor_returns)
        c,s=math.cos(box[6]),math.sin(box[6]);count=0
        for points,_ in sensor_returns.values():
            delta=np.asarray(points)-box[:3]
            local_x=c*delta[:,0]+s*delta[:,1]
            local_y=-s*delta[:,0]+c*delta[:,1]
            count+=int(np.count_nonzero((np.abs(local_x)<=box[3]/2)&(np.abs(local_y)<=box[4]/2)&(np.abs(delta[:,2])<=box[5]/2)))
        record={'context_name':context,'frame_timestamp_micros':timestamp,
                'object_id':'prediction-anchor-'+str(int(index)),'type':int(category),
                'box':box.tolist(),'score':float(score),'overlap_with_nlz':flag,
                'num_lidar_points_in_box':count,'difficulty':None}
        records.append(validate_object(record))
    return records
