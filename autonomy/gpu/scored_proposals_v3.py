"""Versioned score-first decoder with periodic heading correction; legacy v2 preserved."""
import numpy as np
from detection.box_coding import decode_boxes
from detection.detector_geometry import enclosing_bev_nms

def canonical_direction_correct(yaw,bins):
    yaw=np.asarray(yaw,dtype=np.float64);bins=np.asarray(bins)
    if yaw.shape!=bins.shape or not np.isfinite(yaw).all() or bins.dtype.kind not in 'iu' or np.any((bins!=0)&(bins!=1)):raise ValueError('finite angles and binary paired bins required')
    canonical=(yaw+np.pi)%(2*np.pi)-np.pi
    corrected=canonical+np.where((canonical>0)!=(bins==1),np.pi,0.)
    return (corrected+np.pi)%(2*np.pi)-np.pi

def decode_scored_proposals(logits,residuals,direction_logits,anchors,*,iou_threshold,score_floor,pre_limit,post_limit):
    logits=np.asarray(logits,dtype=np.float64);residuals=np.asarray(residuals,dtype=np.float64);direction_logits=np.asarray(direction_logits,dtype=np.float64);anchors=np.asarray(anchors,dtype=np.float64)
    if logits.ndim!=2 or logits.shape[1]!=4 or residuals.shape!=(len(logits),7) or direction_logits.shape!=(len(logits),2) or anchors.shape!=residuals.shape:raise ValueError('paired native predictions required')
    if not all(np.isfinite(x).all() for x in [logits,residuals,direction_logits,anchors]) or np.any(anchors[:,3:6]<=0):raise ValueError('finite heads and positive anchors required')
    if not np.isfinite([iou_threshold,score_floor]).all() or not 0<=iou_threshold<=1 or not 0<=score_floor<=1 or type(pre_limit) is not int or type(post_limit) is not int or min(pre_limit,post_limit)<=0:raise ValueError('valid thresholds/limits required')
    probabilities=np.empty_like(logits);positive=logits>=0;probabilities[positive]=1/(1+np.exp(-logits[positive]));exponent=np.exp(logits[~positive]);probabilities[~positive]=exponent/(1+exponent)
    classes=probabilities.argmax(1)+1;scores=probabilities.max(1);candidate=np.flatnonzero(scores>=score_floor);selected=candidate[np.lexsort((candidate,-scores[candidate]))][:pre_limit]
    boxes=decode_boxes(residuals[selected],anchors[selected]);boxes[:,6]=canonical_direction_correct(residuals[selected,6]+anchors[selected,6],direction_logits[selected].argmax(1))
    kept=enclosing_bev_nms(boxes,scores[selected],iou_threshold=iou_threshold,score_floor=score_floor,pre_limit=pre_limit,post_limit=post_limit)
    return {'boxes':boxes[kept],'classes':classes[selected[kept]],'scores':scores[selected[kept]],'anchor_indices':selected[kept],'suppression':'class-agnostic enclosing rectangle; original anchor index breaks score ties'}
