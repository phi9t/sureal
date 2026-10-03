"""Native camera semantic IoU diagnostic; not official panoptic/STQ scoring.

IDs 0..28 follow pinned camera_segmentation.proto; zero is undefined ground
truth and is excluded from eligible support. Undefined predictions on labeled
pixels count as false negatives. Classes with zero union are omitted from the
reported diagnostic mean and remain null in per-class results.
"""
import numpy as np


def score(truth,prediction,support):
    if truth is None:
        if prediction is not None or support is not None:raise ValueError('partial missing annotation')
        return {'coverage':'missing_annotation','eligible_pixels':0,'mean_iou':None}
    truth=np.asarray(truth);prediction=np.asarray(prediction);support=np.asarray(support)
    if truth.shape!=prediction.shape or truth.shape!=support.shape or support.dtype!=np.bool_:
        raise ValueError('shape or support-mask contract')
    for a in [truth,prediction]:
        if a.dtype.kind not in 'iu' or np.any(a<0) or np.any(a>28):
            raise ValueError('native camera semantic IDs must be integer 0..28')
    mask=support & (truth!=0)
    confusion=np.bincount((truth[mask].astype(np.int64)*29+prediction[mask]).ravel(),minlength=29*29).reshape(29,29)
    intersection=confusion.diagonal()
    union=confusion.sum(0)+confusion.sum(1)-intersection
    classes=[i for i in range(1,29) if union[i]>0]
    per_class=[None if union[i]==0 or i==0 else float(intersection[i]/union[i]) for i in range(29)]
    return {'coverage':'annotated' if mask.any() else 'annotated_no_eligible_pixels',
            'eligible_pixels':int(mask.sum()),'confusion':confusion.tolist(),
            'per_class_iou':per_class,'classes_in_mean':classes,
            'mean_iou':float(np.mean([per_class[i] for i in classes])) if classes else None}
