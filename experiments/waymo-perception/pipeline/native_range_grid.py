"""Lossless point-to-native-grid adapter with separate semantic coverage."""
import numpy as np

def native_range_grid(record, native_shape):
    if (len(native_shape)!=3 or any(type(x) is not int or x<=0 for x in native_shape) or native_shape[2]!=4):
        raise ValueError('explicit native H/W/four-channel shape required')
    if not record['return_present']:raise ValueError('absent return has no native observation grid')
    h,w,_=native_shape;identity=record['identity'];pixels=np.asarray(identity['pixels'])
    if pixels.ndim!=2 or pixels.shape[1]!=2 or not np.issubdtype(pixels.dtype,np.integer):raise ValueError('integer native pixel identity required')
    n=len(pixels)
    if np.any(pixels<0) or np.any(pixels[:,0]>=h) or np.any(pixels[:,1]>=w) or len(np.unique(pixels,axis=0))!=n:
        raise ValueError('duplicate or out-of-native-grid pixel')
    physical=np.asarray(record['observations']['physical_features'])
    if physical.shape!=(n,3) or not np.isfinite(physical).all() or np.any(physical[:,0]<=0):raise ValueError('valid native physical ranges required')
    y,x=pixels.T;measurements=np.zeros((h,w,3),dtype=physical.dtype);measurements[y,x]=physical
    indices=np.full((h,w),-1,dtype=np.int64);indices[y,x]=np.arange(n)
    labels=np.full((h,w),-1,dtype=np.int64);supervised=np.zeros((h,w),dtype=bool)
    segmentation=record['targets'].get('segmentation')
    if segmentation is not None:
        segmentation=np.asarray(segmentation)
        if (identity['laser']!=1 or segmentation.shape!=(n,2) or not np.issubdtype(segmentation.dtype,np.integer)
            or np.any(segmentation[:,0]<-1) or not np.isin(segmentation[:,1],range(23)).all()):raise ValueError('native TOP semantic namespace required')
        labels[y,x]=segmentation[:,1];supervised[y,x]=segmentation[:,1]!=0
    return {'identity':{k:v for k,v in identity.items() if k!='pixels'},'native_shape':tuple(native_shape),
            'measurements':measurements,'valid':indices>=0,'source_indices':indices,'point_pixels':pixels.copy(),
            'semantic_labels':labels,'semantic_supervised':supervised,'annotation_present':segmentation is not None}

def gather_range_features(grid,features):
    features=np.asarray(features)
    if features.ndim<2 or features.shape[:2]!=grid['source_indices'].shape:raise ValueError('features differ from native grid')
    y,x=grid['point_pixels'].T
    return features[y,x]
