"""Independent NumPy detector equations and class contributions (one frame).

No imports from Torch or the producer loss. Absent classes retain the fixed
four-class denominator; ignored anchors contribute no classification term.
"""
import math
import numpy as np

def literal_losses(heads,truth,*,class_balanced=False):
 if set(heads)!={'classification','box_residuals','direction'} or not {'labels','box_targets','direction_targets'}<=truth.keys():raise ValueError('complete detector heads/targets required')
 labels=np.asarray(truth['labels']);directions=np.asarray(truth['direction_targets']);n=labels.size
 if labels.shape!=(n,) or n==0 or labels.dtype.kind not in 'iu' or directions.shape!=(n,) or directions.dtype.kind not in 'iu' or np.any((labels < -1)|(labels>4)) or np.any((directions<0)|(directions>1)):raise ValueError('bounded integer detector targets required')
 arrays={k:np.asarray(v) for k,v in heads.items()};targets=np.asarray(truth['box_targets'])
 shapes={'classification':(n,4),'box_residuals':(n,7),'direction':(n,2)}
 if targets.shape!=(n,7) or targets.dtype.kind!='f' or not np.isfinite(targets).all() or any(v.shape!=shapes[k] or v.dtype.kind!='f' or not np.isfinite(v).all() for k,v in arrays.items()):raise ValueError('finite paired floating detector arrays required')
 logits=arrays['classification'].astype(np.float64);boxes=arrays['box_residuals'].astype(np.float64);heading=arrays['direction'].astype(np.float64);targets=targets.astype(np.float32).astype(np.float64)
 positive=labels>0;normalizer=max(1,int(positive.sum()));y=(labels[:,None]==np.arange(1,5)[None,:]).astype(np.float64);prob=np.exp(-np.logaddexp(0,-logits));correct=y*prob+(1-y)*(1-prob);ce=np.logaddexp(0,logits)-y*logits;focal=(.25*y+.75*(1-y))*(1-correct)**2*ce
 counts=y.sum(0);weights=np.divide(normalizer,4*counts,out=np.zeros(4),where=counts>0) if class_balanced else np.ones(4);focal*=1+y*(weights[None,:]-1);focal*=(labels>=0)[:,None]
 parts={str(c+1):{'positive_anchors':int(counts[c]),'positive_weight':float(weights[c]),'positive_focal':float((focal[:,c]*y[:,c]).sum()/normalizer),'negative_focal':float((focal[:,c]*(1-y[:,c])).sum()/normalizer)} for c in range(4)}
 classification=float(focal.sum()/normalizer);delta=boxes-targets;delta[:,6]=np.sin(delta[:,6]);absolute=np.abs(delta);local=float((np.where(absolute<1/9,4.5*delta**2,absolute-1/18)*positive[:,None]).sum()/normalizer);direction=float(((np.logaddexp(heading[:,0],heading[:,1])-heading[np.arange(n),directions])*positive).sum()/normalizer)
 losses={'classification':classification,'localization':local,'direction':direction,'total':classification+2*local+.2*direction}
 if any(not math.isfinite(x) for x in losses.values()):raise ValueError('literal losses nonfinite')
 return losses,parts

def compare_losses(expected,reported):
 if expected.keys()!=reported.keys():raise ValueError('complete literal loss report required')
 for key,value in expected.items():
  found=reported[key]
  if isinstance(found,bool) or not isinstance(found,(int,float)) or not math.isfinite(found) or not math.isfinite(value) or not math.isclose(value,found,rel_tol=2e-5,abs_tol=2e-5):raise ValueError('literal reported loss differs: '+key)
