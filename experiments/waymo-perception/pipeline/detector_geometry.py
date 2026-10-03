"""Axis-aligned detector reference geometry; never native rotated 3D metrics."""
import numpy as np


def _boxes(boxes):
    boxes=np.asarray(boxes,dtype=np.float64)
    if boxes.ndim!=2 or boxes.shape[1]!=7 or not np.isfinite(boxes).all() or np.any(boxes[:,3:6]<=0):
        raise ValueError('finite native center-Z Nx7 boxes with positive dimensions required')
    return boxes


def _rectangles(boxes,*,nearest):
    boxes=_boxes(boxes)
    if nearest:
        yaw=np.abs((boxes[:,6]+np.pi/2)%np.pi-np.pi/2)
        extent=np.where((yaw>np.pi/4)[:,None],boxes[:,[4,3]],boxes[:,3:5])
    else:
        c=np.abs(np.cos(boxes[:,6]));s=np.abs(np.sin(boxes[:,6]))
        extent=np.stack((c*boxes[:,3]+s*boxes[:,4],s*boxes[:,3]+c*boxes[:,4]),axis=1)
    return np.concatenate((boxes[:,:2]-extent/2,boxes[:,:2]+extent/2),axis=1)


def _iou(first,second):
    lower=np.maximum(first[:,None,:2],second[None,:,:2])
    upper=np.minimum(first[:,None,2:],second[None,:,2:])
    intersection=np.maximum(upper-lower,0).prod(axis=-1)
    area_first=(first[:,2:]-first[:,:2]).prod(axis=-1)
    area_second=(second[:,2:]-second[:,:2]).prod(axis=-1)
    union=area_first[:,None]+area_second[None,:]-intersection
    return np.divide(intersection,union,out=np.zeros_like(intersection),where=union>0)


def nearest_bev_iou(first,second):
    return _iou(_rectangles(first,nearest=True),_rectangles(second,nearest=True))


def enclosing_bev_nms(boxes,scores,*,iou_threshold,score_floor,pre_limit,post_limit):
    boxes=_boxes(boxes);scores=np.asarray(scores,dtype=np.float64)
    if scores.shape!=(len(boxes),) or not np.isfinite(scores).all() or np.any(scores<0) or np.any(scores>1):
        raise ValueError('paired finite probability scores required')
    if not np.isfinite([iou_threshold,score_floor]).all() or not 0<=iou_threshold<=1 or not 0<=score_floor<=1:
        raise ValueError('valid suppression/score thresholds required')
    if type(pre_limit) is not int or type(post_limit) is not int or min(pre_limit,post_limit)<=0:
        raise ValueError('positive integer suppression limits required')
    indices=np.flatnonzero(scores>=score_floor)
    order=indices[np.lexsort((indices,-scores[indices]))][:pre_limit]
    rectangles=_rectangles(boxes,nearest=False)
    keep=[]
    while len(order) and len(keep)<post_limit:
        current=order[0];keep.append(current);remaining=order[1:]
        overlap=_iou(rectangles[current:current+1],rectangles[remaining])[0]
        order=remaining[overlap<=iou_threshold]
    return np.asarray(keep,dtype=np.int64)
