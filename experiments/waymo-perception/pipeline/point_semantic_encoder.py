"""Independent all-point semantic candidate; not a paper reproduction.

Input columns: vehicle XYZ, intensity, elongation. Range can be derived from
XYZ. Annotation coverage, NLZ and box metadata have no observation slots.
No foreground selection or point sampling occurs in this candidate.
"""
import torch
from torch import nn
from torch.nn import functional as F


class PointSemanticEncoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.local=nn.Sequential(nn.Linear(5,64),nn.ReLU(),nn.Linear(64,128),nn.ReLU())
        self.head=nn.Sequential(nn.Linear(256,128),nn.ReLU(),nn.Linear(128,23))

    def forward(self,points):
        if points.ndim!=2 or points.shape[1]!=5 or not points.is_floating_point() or not torch.isfinite(points).all():
            raise ValueError('finite physical XYZ/intensity/elongation rows required')
        local=self.local(points)
        context=local.amax(dim=0,keepdim=True) if len(points) else local.new_zeros((1,128))
        return self.head(torch.cat((local,context.expand(len(points),-1)),dim=1))


def semantic_loss(logits,labels):
    if logits.ndim!=2 or logits.shape[1]!=23 or not logits.is_floating_point() or not torch.isfinite(logits).all():
        raise ValueError('finite native23 semantic logits required')
    if labels is None:
        return {'loss':logits.sum()*0,'eligible_points':0,'labels_present':False}
    if labels.shape!=(len(logits),) or labels.dtype!=torch.int64 or labels.device!=logits.device or torch.any((labels<0)|(labels>22)):
        raise ValueError('aligned native semantic integer labels required')
    mask=labels!=0;count=int(mask.sum())
    loss=F.cross_entropy(logits[mask],labels[mask],reduction='sum')/count if count else logits.sum()*0
    return {'loss':loss,'eligible_points':count,'labels_present':True}
