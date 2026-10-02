"""Box-derived detection targets; never substitutes for point semantics."""
import numpy as np

def foreground_support(xyz,boxes,native_classes):
    xyz=np.asarray(xyz,dtype=np.float64);boxes=np.asarray(boxes,dtype=np.float64);classes=np.asarray(native_classes)
    if (xyz.ndim!=2 or xyz.shape[1]!=3 or boxes.ndim!=2 or boxes.shape[1]!=7
        or classes.shape!=(len(boxes),) or not np.issubdtype(classes.dtype,np.integer)
        or not np.isin(classes,[1,2,3,4]).all() or not np.isfinite(xyz).all()
        or not np.isfinite(boxes).all() or np.any(boxes[:,3:6]<=0)):
        raise ValueError('finite XYZ/native upright XYZLWHyaw boxes and native box classes1..4 required')
    membership=np.zeros((len(xyz),4),dtype=bool);indices=[]
    for box,category in zip(boxes,classes):
        delta=xyz-box[:3];c,s=np.cos(box[6]),np.sin(box[6])
        local_x=delta[:,0]*c+delta[:,1]*s;local_y=-delta[:,0]*s+delta[:,1]*c
        # Inclusive mathematical box surfaces; no implicit dilation/tolerance.
        inside=(np.abs(local_x)<=box[3]/2)&(np.abs(local_y)<=box[4]/2)&(np.abs(delta[:,2])<=box[5]/2)
        support=np.flatnonzero(inside);indices.append(support);membership[:,int(category)-1]|=inside
    return {'class_membership':membership,'object_point_indices':indices,'native_classes':classes.copy(),
            'scope':'native box membership targets only; coarse box taxonomy, not full-scene point semantics'}

def selection_diagnostics(targets,selected,*,minimum_points):
    selected=np.asarray(selected);membership=targets['class_membership']
    if selected.dtype!=np.bool_ or selected.shape!=(len(membership),) or type(minimum_points) is not int or minimum_points<1:
        raise ValueError('boolean original-point selection and explicit positive retention minimum required')
    result={'selected_points':int(selected.sum()),'input_points':len(selected),'minimum_points':minimum_points,'classes':{}}
    for category in range(1,5):
        support=membership[:,category-1];denominator=int(support.sum());numerator=int((support&selected).sum())
        objects=[p for p,c in zip(targets['object_point_indices'],targets['native_classes']) if c==category]
        observed=[p for p in objects if len(p)>0];counts=[int(selected[p].sum()) for p in observed]
        result['classes'][str(category)]={'foreground_points':denominator,'selected_foreground_points':numerator,
            'point_recall':numerator/denominator if denominator else None,'annotated_objects':len(objects),
            'objects_without_observed_support':len(objects)-len(observed),'supported_objects':len(observed),
            'objects_retaining_one':sum(n>=1 for n in counts),'objects_retaining_minimum':sum(n>=minimum_points for n in counts)}
    return result
