"""Admitted positive-focal weighting, with explicit absent-class extension.

Each present class c receives N_positive/(4*N_c). An absent class has no
positive term and weight zero. This preserves the admitted all-present equation
without renormalizing by the number of present classes. Negative focal, box and
direction equations are unchanged. No observation or target is removed.
"""
import torch
from detection.detector_loss import detector_loss

def class_balanced_objective(output,targets):
 logits=output['classification']
 if logits.ndim!=3 or logits.shape[-1]!=4:raise ValueError('four native class logits required')
 result=detector_loss(logits,output['box_residuals'],output['direction'],*targets)
 labels,_,_=targets;normalizer=(labels>0).sum(1).clamp_min(1).to(logits.dtype)
 y=(labels[:,:,None]==torch.arange(1,5,device=logits.device)[None,None,:]).to(logits.dtype);counts=y.sum(1)
 weights=torch.where(counts>0,normalizer[:,None]/(4*counts.clamp_min(1)),torch.zeros_like(counts))
 probability=logits.sigmoid();positive_terms=.25*y*(1-probability).square()*torch.nn.functional.binary_cross_entropy_with_logits(logits,y,reduction='none')
 correction=((positive_terms*(weights[:,None,:]-1)).sum((1,2))/normalizer).mean()
 result['classification']=result['classification']+correction
 result['total']=result['classification']+2*result['localization']+.2*result['direction']
 return result
