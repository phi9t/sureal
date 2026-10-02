"""Preregistered full-class fitting gate; no heldout success inference."""
import math

def validate_cohort(frames):
 if len(frames)!=16:raise ValueError('Exactly 16 frozen frames required')
 identities=[f['identity'] for f in frames]
 if len(set(identities))!=16:raise ValueError('Duplicate training frame')
 if any(f['split']!='training' for f in frames):raise ValueError('Training-only fixture required')
 counts={str(k):sum(f['positive_anchors'][str(k)] for f in frames) for k in range(1,5)}
 if any(v<=0 for v in counts.values()):raise ValueError('Every required class needs positive anchors')
 return {'frames':16,'positive_anchors_by_class':counts}

def quality_gate(per_class):
 return set(per_class)=={'1','2','3','4'} and all(math.isfinite(v) and v>=.8 for v in per_class.values())
