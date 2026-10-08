"""Shared construction seam for matched, explicit one-factor treatments."""
import math
import torch
from detection.pillar_detector import PillarDetector
from detection.detector_loss import detector_loss
from detection.norm_variants import configure_norm
from detection.architecture_variants import configure_architecture
from detection.architecture_followups import configure_followup

def build(case):
 m=configure_norm(PillarDetector(nx=512,ny=512,classes=4,anchors_per_cell=8,cell_size=(.25,.25),origin=(-64.,-64.)),case['norm'])
 variant=case['architecture']
 if variant in ('deep_pfn','context_pfn','residual_bev'):m=configure_architecture(m,variant)
 elif variant in ('masked_pfn','window_bev','coarse_mlp'):m=configure_followup(m,variant)
 elif variant!='baseline':raise ValueError('Unsupported architecture')
 if case['foreground_prior'] is not None:
  prior=case['foreground_prior'];assert 0<prior<1
  torch.nn.init.constant_(m.class_head.bias,math.log(prior/(1-prior)))
 return m

def objective(output,targets,case):
 logits=output['classification'];result=detector_loss(logits,output['box_residuals'],output['direction'],*targets)
 if case['loss']=='reference':return result
 if case['loss']!='class_balanced_positive':raise ValueError('Unsupported loss')
 labels,box,direction=targets;positive=labels>0;normalizer=positive.sum(1).clamp_min(1).to(logits.dtype)
 y=(labels[:,:,None]==torch.arange(1,5,device=logits.device)[None,None,:]).to(logits.dtype);counts=y.sum(1);assert torch.all(counts>0)
 weights=normalizer[:,None]/(4*counts);prob=logits.sigmoid();positive_terms=.25*y*(1-prob).square()*torch.nn.functional.binary_cross_entropy_with_logits(logits,y,reduction='none')
 correction=((positive_terms*(weights[:,None,:]-1)).sum((1,2))/normalizer).mean();result['classification']=result['classification']+correction;result['total']=result['classification']+2*result['localization']+.2*result['direction'];return result

def optimizer(model,case):return torch.optim.Adam(model.parameters(),lr=case['learning_rate'],betas=(.9,.999),eps=1e-8,weight_decay=0,foreach=False)
def deterministic():
 torch.manual_seed(17);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.deterministic=True;torch.backends.cudnn.benchmark=False;torch.use_deterministic_algorithms(True)
