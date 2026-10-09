"""Axis-aligned detector reference geometry; never native rotated 3D metrics."""
import numpy as np
from geometry.oriented_box import axis_aligned_bev_iou, enclosing_bev_rectangles, nearest_bev_rectangles


def _boxes(boxes):
    boxes=np.asarray(boxes,dtype=np.float64)
    if boxes.ndim!=2 or boxes.shape[1]!=7 or not np.isfinite(boxes).all() or np.any(boxes[:,3:6]<=0):
        raise ValueError('finite native center-Z Nx7 boxes with positive dimensions required')
    return boxes


def nearest_bev_iou(first,second):
    return axis_aligned_bev_iou(nearest_bev_rectangles(_boxes(first)),nearest_bev_rectangles(_boxes(second)))


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
    rectangles=enclosing_bev_rectangles(boxes)
    keep=[]
    while len(order) and len(keep)<post_limit:
        current=order[0];keep.append(current);remaining=order[1:]
        overlap=axis_aligned_bev_iou(rectangles[current:current+1],rectangles[remaining])[0]
        order=remaining[overlap<=iou_threshold]
    return np.asarray(keep,dtype=np.int64)
