"""Native target assignment preparation; uncovered GT is reported, never hidden."""
import math
import numpy as np
from detection.anchor_assignment import assign_overlaps
from detection.detector_geometry import nearest_bev_iou
from detection.box_coding import encode_boxes
from geometry.oriented_box import wrap_heading

def build_targets(anchors,rows,*,scene,timestamp,roi,positive,negative):
 anchors=np.asarray(anchors,dtype=np.float64);roi=np.asarray(roi,dtype=np.float64)
 if anchors.ndim!=2 or anchors.shape[1]!=7 or not np.isfinite(anchors).all() or np.any(anchors[:,3:6]<=0) or roi.shape!=(6,) or not np.isfinite(roi).all() or np.any(roi[:3]>=roi[3:]):raise ValueError('finite anchors and half-open ROI required')
 seen=set();eligible=[];reasons={k:0 for k in ('unknown_class','zero_native_points','center_outside_roi','eligible')}
 for row in rows:
  identity=row['object_id'];box=row['box'];typ=row['type'];points=row['num_lidar_points_in_box']
  if row['context_name']!=scene or row['frame_timestamp_micros']!=timestamp or not isinstance(identity,str) or not identity or identity in seen or type(typ) is not int or not 0<=typ<2**31 or type(points) is not int or points<0 or len(box)!=7 or any(type(v) not in (float,int) or not math.isfinite(v) for v in box) or min(box[3:6])<=0:raise ValueError('invalid or duplicate native target')
  seen.add(identity)
  if typ not in (1,2,3,4):reason='unknown_class'
  elif points==0:reason='zero_native_points'
  elif not all(roi[i]<=box[i]<roi[i+3] for i in range(3)):reason='center_outside_roi'
  else:reason='eligible';eligible.append(row)
  reasons[reason]+=1
 eligible.sort(key=lambda row:row['object_id']);gt=np.asarray([r['box'] for r in eligible],dtype=np.float64).reshape(-1,7);classes=np.asarray([r['type'] for r in eligible],dtype=np.int64)
 # Keep residual encoding and binary direction labels in the same heading branch.
 gt[:,6]=wrap_heading(gt[:,6])
 overlaps=nearest_bev_iou(anchors,gt);assigned=assign_overlaps(overlaps,classes,positive=positive,negative=negative);labels=assigned['labels'];indices=assigned['target_indices'];mask=labels>0
 residuals=np.zeros((len(anchors),7),dtype=np.float64);directions=np.zeros(len(anchors),dtype=np.int64)
 if mask.any():
  matched=gt[indices[mask]];residuals[mask]=encode_boxes(matched,anchors[mask]);canonical=wrap_heading(matched[:,6]);directions[mask]=(canonical>0).astype(np.int64)
 covered=set(indices[mask].tolist());uncovered=[row['object_id'] for i,row in enumerate(eligible) if i not in covered]
 report={'native_box_rows':len(rows),'target_reasons':reasons,'eligible_targets':len(eligible),'positive_anchors':int(mask.sum()),'negative_anchors':int((labels==0).sum()),'ignored_anchors':int((labels<0).sum()),'positive_anchor_counts_by_class':{str(c):int((labels==c).sum()) for c in range(1,5)},'eligible_targets_without_positive_anchor':len(uncovered),'uncovered_object_ids':uncovered,'direction_rule':'canonical native heading in[-pi,pi); bin1 iff strictly positive','scope':'native target tensors only; source admission and model-input isolation external; no optimizer/quality claim'}
 assert sum(reasons.values())==len(rows) and report['positive_anchors']+report['negative_anchors']+report['ignored_anchors']==len(anchors)
 return {'labels':labels,'box_targets':residuals,'direction_targets':directions,'target_indices':indices,'eligible_object_ids':[r['object_id'] for r in eligible],'report':report}
