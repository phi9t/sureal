"""Native TOP semantic support on valid reconstructed points; no model features."""
import numpy as np


def semantic_support(records):
    counts=np.zeros(23,dtype=np.int64);seen=set();frames=set();annotated=0;unannotated=0;empty=0;per_frame={}
    for r in records:
        identity=r['identity'];key=tuple(identity[k] for k in ('context','timestamp','laser','return'))
        if key in seen:raise ValueError('duplicate original sensor return')
        seen.add(key)
        labels=r['targets'].get('segmentation')
        if labels is None:
            unannotated+=1;continue
        if identity['laser']!=1 or not r['return_present']:raise ValueError('semantic supervision must belong to present TOP return')
        labels=np.asarray(labels);xyz=np.asarray(r['observations']['xyz'])
        if labels.shape!=(len(xyz),2) or not np.issubdtype(labels.dtype,np.integer):raise ValueError('native semantic point shape/type differs')
        semantic=labels[:,1]
        if np.any(semantic<0) or np.any(semantic>22) or np.any(labels[:,0]<-1):raise ValueError('native taxonomy or instance ID invalid')
        histogram=np.bincount(semantic,minlength=23);counts+=histogram;annotated+=1;empty+=len(labels)==0
        frame=(identity['context'],identity['timestamp']);frames.add(frame)
        if frame not in per_frame:per_frame[frame]=np.zeros(23,dtype=np.int64)
        per_frame[frame]+=histogram
    return {'taxonomy':'native Waymo LiDAR semantic IDs 0..22; 0 undefined',
            'native_counts':counts.tolist(),'labeled_point_elements':int(counts.sum()),'eligible_point_elements':int(counts[1:].sum()),
            'annotated_frames':len(frames),'annotated_returns':annotated,'unannotated_returns':unannotated,'empty_annotated_returns':int(empty),
            'frame_counts':[{'context':c,'timestamp':t,'native_counts':v.tolist()} for (c,t),v in sorted(per_frame.items())],
            'scope':'native targets on retained valid-range points; instance -1 does not mask valid semantics; no category remapping or scientific generalization claim'}
