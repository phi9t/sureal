"""PointPillars adaptation loss: paired batch/anchor targets, no target inputs."""
import torch
from torch.nn import functional as F


def detector_loss(logits,boxes,direction_logits,labels,box_targets,direction_targets):
    if logits.ndim!=3 or min(logits.shape)<=0:
        raise ValueError('nonempty batch/anchor/class logits required')
    batch,anchors,classes=logits.shape
    if boxes.shape!=(batch,anchors,7) or box_targets.shape!=boxes.shape or direction_logits.shape!=(batch,anchors,2) or labels.shape!=(batch,anchors) or direction_targets.shape!=labels.shape:
        raise ValueError('paired detector tensor shapes required')
    for value in (logits,boxes,direction_logits,box_targets):
        if value.device!=logits.device or value.dtype!=logits.dtype or not value.is_floating_point() or not torch.isfinite(value).all():
            raise ValueError('finite floating detector tensors on one device required')
    for value in (labels,direction_targets):
        if value.device!=logits.device or value.dtype not in (torch.int32,torch.int64):
            raise ValueError('integer targets on detector device required')
    if torch.any(labels < -1) or torch.any(labels > classes) or torch.any(direction_targets<0) or torch.any(direction_targets>1):
        raise ValueError('class or direction target out of range')
    positive=labels>0
    normalizer=positive.sum(dim=1).clamp_min(1).to(logits.dtype)
    targets=(labels[:,:,None]==torch.arange(1,classes+1,device=logits.device)[None,None,:]).to(logits.dtype)
    probability=logits.sigmoid()
    correct_probability=targets*probability+(1-targets)*(1-probability)
    alpha=targets*.25+(1-targets)*.75
    focal=alpha*(1-correct_probability).square()*F.binary_cross_entropy_with_logits(logits,targets,reduction='none')
    classification=((focal*(labels>=0)[:,:,None]).sum(dim=(1,2))/normalizer).mean()
    # Source sine-difference comparison, without inverse-sine decoding.
    difference=torch.cat((boxes[:,:,:6]-box_targets[:,:,:6],
                          torch.sin(boxes[:,:,6]-box_targets[:,:,6])[:,:,None]),dim=-1)
    absolute=difference.abs()
    smooth=torch.where(absolute<1/9,4.5*difference.square(),absolute-1/18)
    localization=((smooth*positive[:,:,None]).sum(dim=(1,2))/normalizer).mean()
    direction_ce=F.cross_entropy(direction_logits.reshape(-1,2),direction_targets.long().reshape(-1),reduction='none').reshape(batch,anchors)
    direction=((direction_ce*positive).sum(dim=1)/normalizer).mean()
    return {'classification':classification,'localization':localization,
            'direction':direction,'total':classification+2*localization+.2*direction}
