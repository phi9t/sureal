"""Versioned score-first diagnostic decoder; baseline decoder preserved."""
import numpy as np
from pipeline.box_coding import decode_boxes,direction_correct
from pipeline.detector_geometry import enclosing_bev_nms

def decode_scored_proposals(logits,residuals,direction_logits,anchors,*,iou_threshold,score_floor,pre_limit,post_limit):
    logits=np.asarray(logits,dtype=np.float64);residuals=np.asarray(residuals,dtype=np.float64);direction_logits=np.asarray(direction_logits,dtype=np.float64);anchors=np.asarray(anchors,dtype=np.float64)
    if logits.ndim!=2 or logits.shape[1]!=4 or residuals.shape!=(len(logits),7) or direction_logits.shape!=(len(logits),2) or anchors.shape!=residuals.shape:raise ValueError('paired native predictions required')
    if not all(np.isfinite(x).all() for x in [logits,residuals,direction_logits,anchors]) or np.any(anchors[:,3:6]<=0):raise ValueError('finite heads and positive anchors required')
    if not np.isfinite([iou_threshold,score_floor]).all() or not 0<=iou_threshold<=1 or not 0<=score_floor<=1 or type(pre_limit) is not int or type(post_limit) is not int or min(pre_limit,post_limit)<=0:raise ValueError('valid thresholds/limits required')
    probabilities=np.empty_like(logits);positive=logits>=0;probabilities[positive]=1/(1+np.exp(-logits[positive]));exponent=np.exp(logits[~positive]);probabilities[~positive]=exponent/(1+exponent)
    classes=probabilities.argmax(1)+1;scores=probabilities.max(1);candidate=np.flatnonzero(scores>=score_floor);selected=candidate[np.lexsort((candidate,-scores[candidate]))][:pre_limit]
    boxes=decode_boxes(residuals[selected],anchors[selected]);boxes[:,6]=direction_correct(residuals[selected,6]+anchors[selected,6],direction_logits[selected].argmax(1))
    kept=enclosing_bev_nms(boxes,scores[selected],iou_threshold=iou_threshold,score_floor=score_floor,pre_limit=pre_limit,post_limit=post_limit)
    return {'boxes':boxes[kept],'classes':classes[selected[kept]],'scores':scores[selected[kept]],'anchor_indices':selected[kept],'suppression':'class-agnostic enclosing rectangle; original anchor index breaks score ties'}
