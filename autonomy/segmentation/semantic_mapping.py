"""Candidate conservative camera-semantic to native point refinement.

This is a versioned research candidate, not a universal ontology equivalence.
Callers separately verify semantic-head provenance and calibrated visibility.
"""
import numpy as np

MAPPING_VERSION='camera29-lidar23-conservative-candidate-v1'
DIRECT={2:1,3:2,4:3,5:4,6:12,7:13,9:7,10:6,11:5,
        14:11,15:10,17:8,18:9,19:14,20:18,21:19,22:20}
AMBIGUOUS={23:(17,22),24:(15,16),26:(18,20,21,22)}


def refine_point_classes(baseline,camera_classes,geometric_support,*,semantic_origin):
    if semantic_origin!='predicted-camera-semantic':
        raise ValueError('predicted fine camera semantics required; boxes/annotations are distinct')
    baseline=np.asarray(baseline);camera=np.asarray(camera_classes);support=np.asarray(geometric_support)
    if baseline.ndim!=1 or camera.shape!=baseline.shape or support.shape!=baseline.shape or support.dtype!=np.bool_:
        raise ValueError('paired point predictions and explicit boolean geometric support required')
    if baseline.dtype.kind not in 'iu' or camera.dtype.kind not in 'iu' or np.any(baseline<0) or np.any(baseline>22) or np.any(camera<0) or np.any(camera>28):
        raise ValueError('native LiDAR/camera semantic namespaces required')
    predictions=baseline.copy();transferred=np.zeros(len(baseline),dtype=bool)
    reasons=np.full(len(baseline),'unmapped taxonomy',dtype='<U24')
    for category in AMBIGUOUS:reasons[camera==category]='ambiguous taxonomy'
    reasons[camera==0]='undefined prediction'
    reasons[~support]='unsupported geometry'
    for camera_id,point_id in DIRECT.items():
        selected=(camera==camera_id)&support
        predictions[selected]=point_id;transferred[selected]=True;reasons[selected]='transferred'
    return {'predictions':predictions,'transferred':transferred,'reasons':reasons,
            'mapping_version':MAPPING_VERSION,'points':len(baseline)}
