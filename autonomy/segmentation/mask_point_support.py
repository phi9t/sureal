"""Conservative mask association using native two-slot point projections.

Visibility is required externally; a projection alone is not visibility proof.
Origin declarations are interface guards, not checkpoint provenance validation.
"""
import numpy as np


def mask_point_support(projection,visible,masks,*,origin):
    if origin not in ('predicted-mask','predicted-box-support'):
        raise ValueError('predicted spatial support required')
    cp=np.asarray(projection);visibility=np.asarray(visible)
    if cp.ndim!=2 or cp.shape[1]!=6 or cp.dtype.kind not in 'iu' or visibility.shape!=(len(cp),2) or visibility.dtype!=np.bool_:
        raise ValueError('native integer camera/u/v slots and explicit point visibility required')
    if np.any(cp[:,[0,3]]<0) or np.any(cp[:,[0,3]]>5):raise ValueError('Perception camera namespace required')
    normalized={}
    for camera,prompts in masks.items():
        if type(camera) is not int or camera not in range(1,6):raise ValueError('native camera mask key required')
        ids=set();shape=None;normalized[camera]=[]
        for p in prompts:
            m=np.asarray(p['mask']);identity=p['prompt_id'];category=p['camera_class']
            if not isinstance(identity,str) or not identity or identity in ids or type(category) is not int or not 0<=category<=28 or m.ndim!=2 or m.dtype!=np.bool_ or 0 in m.shape:
                raise ValueError('unique predicted prompt, native camera class and boolean image support required')
            if shape is not None and shape!=m.shape:raise ValueError('one original image shape per camera required')
            ids.add(identity);shape=m.shape
            normalized[camera].append({'prompt_id':identity,'camera_class':category,'mask':m})
    classes=np.zeros(len(cp),dtype=np.int64);support=np.zeros(len(cp),dtype=bool);reasons=np.full(len(cp),'no supported association',dtype='<U32')
    for i,row in enumerate(cp):
        hits=[]
        for slot in range(2):
            camera,u,v=map(int,row[3*slot:3*slot+3])
            if not camera or not visibility[i,slot]:continue
            for p in normalized.get(camera,[]):
                mask=p['mask']
                if 0<=v<mask.shape[0] and 0<=u<mask.shape[1] and mask[v,u]:hits.append((p['prompt_id'],p['camera_class']))
        if not hits:continue
        if len(set(hits))!=1:reasons[i]='prompt or semantic conflict';continue
        identity,category=hits[0]
        if category==0:reasons[i]='undefined semantic prediction';continue
        classes[i]=category;support[i]=True;reasons[i]='supported association'
    return {'camera_classes':classes,'support':support,'reasons':reasons,'points':len(cp),
            'scope':'supplied native pixel correspondences and external visibility only; no metric depth or checkpoint provenance inferred'}
