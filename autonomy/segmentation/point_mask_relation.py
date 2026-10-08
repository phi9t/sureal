"""Untyped teacher mask relations; projection incidence is not visibility."""
import numpy as np

def point_mask_relation(projections,masks,*,camera,visibility):
    cp=np.asarray(projections);masks=np.asarray(masks)
    if (type(camera) is not int or camera not in range(1,6) or cp.ndim!=2 or cp.shape[1]!=6
        or cp.dtype.kind not in 'iuf' or not np.isfinite(cp).all() or not np.equal(cp,np.floor(cp)).all()
        or masks.ndim!=3 or masks.dtype!=np.bool_ or min(masks.shape[1:])<=0):
        raise ValueError('integral native projections and original-image boolean mask stack required')
    if (cp.dtype.kind=='f' and (np.any(cp>=2**63) or np.any(cp<-(2**63)))) or (cp.dtype.kind=='u' and np.any(cp>np.uint64(2**63-1))):
        raise ValueError('native coordinates outside exact int64 conversion')
    cp=cp.astype(np.int64,copy=False)
    if not np.isin(cp[:,[0,3]],range(6)).all():raise ValueError('native Perception camera namespace required')
    supplied=visibility is not None
    if supplied:
        visible=np.asarray(visibility)
        if visible.shape!=(len(cp),2) or visible.dtype!=np.bool_:raise ValueError('explicit original-point two-slot boolean visibility required')
    else:visible=np.zeros((len(cp),2),dtype=bool)
    projected=np.zeros((len(cp),len(masks)),dtype=bool);supported=np.zeros_like(projected);projectable=np.zeros((len(cp),2),dtype=bool)
    height,width=masks.shape[1:]
    for slot in range(2):
        c,u,v=cp[:,3*slot:3*slot+3].T
        valid=(c==camera)&(u>=0)&(u<width)&(v>=0)&(v<height);projectable[:,slot]=valid;indices=np.flatnonzero(valid)
        for j,mask in enumerate(masks):
            hits=mask[v[indices],u[indices]];projected[indices,j]|=hits;supported[indices,j]|=hits&visible[indices,slot]
    return {'projected_hits':projected,'visible_hits':supported,'projectable_slots':projectable,
            'visibility_supplied':supplied,'points':len(cp),
            'scope':'untyped original-point teacher-mask relations; no semantic namespace assignment or visibility inferred from projection'}
