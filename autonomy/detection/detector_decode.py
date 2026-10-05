"""Native box proposals; evaluation metadata must be resolved separately."""
import numpy as np
from detection.box_coding import decode_boxes,direction_correct
from detection.detector_geometry import enclosing_bev_nms


def decode_proposals(logits,residuals,direction_logits,anchors,*,iou_threshold,score_floor,pre_limit,post_limit):
    logits=np.asarray(logits,dtype=np.float64);residuals=np.asarray(residuals,dtype=np.float64)
    direction_logits=np.asarray(direction_logits,dtype=np.float64);anchors=np.asarray(anchors,dtype=np.float64)
    if logits.ndim!=2 or logits.shape[1]!=4 or residuals.shape!=(len(logits),7) or direction_logits.shape!=(len(logits),2) or anchors.shape!=residuals.shape:
        raise ValueError('paired native four-class anchor predictions required')
    if not np.isfinite(logits).all() or not np.isfinite(direction_logits).all():
        raise ValueError('finite class and direction logits required')
    boxes=decode_boxes(residuals,anchors)
    # Keep the unwrapped additive angle for the source direction-sign test.
    boxes[:,6]=direction_correct(residuals[:,6]+anchors[:,6],direction_logits.argmax(axis=1))
    probabilities=np.empty_like(logits)
    positive=logits>=0
    probabilities[positive]=1/(1+np.exp(-logits[positive]))
    exponent=np.exp(logits[~positive]);probabilities[~positive]=exponent/(1+exponent)
    classes=probabilities.argmax(axis=1)+1
    scores=probabilities[np.arange(len(classes)),classes-1]
    kept=enclosing_bev_nms(boxes,scores,iou_threshold=iou_threshold,score_floor=score_floor,
                           pre_limit=pre_limit,post_limit=post_limit)
    return {'boxes':boxes[kept],'classes':classes[kept],'scores':scores[kept],
            'anchor_indices':kept,'suppression':'class-agnostic enclosing rectangle; original anchor index breaks score ties'}
