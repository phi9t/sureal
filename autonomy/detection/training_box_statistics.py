"""Native training-frame box distributions; no silent anchor policy selection.

Membership must come from independently admitted original source manifests.
This function checks declared membership, not its cryptographic provenance.
"""
import math
import numpy as np


def training_box_statistics(records,*,membership):
    values={i:[] for i in range(1,5)};tracks={i:set() for i in values};frames=set();seen=set();contexts=set()
    for r in records:
        context=r.get('context_name');m=membership.get(context)
        if not m or m.get('official_split')!='training' or m.get('research_splits')!=['train']:
            raise ValueError('admitted training-only membership required')
        timestamp=r.get('frame_timestamp_micros');identity=r.get('object_id');category=r.get('type')
        if type(timestamp) is not int or not 0<=timestamp<2**63 or not isinstance(identity,str) or not identity or type(category) is not int or category not in values:
            raise ValueError('native frame/object/class identity required')
        key=(context,timestamp,identity)
        if key in seen:raise ValueError('duplicate native frame/object')
        seen.add(key);box=r.get('box')
        if not isinstance(box,list) or len(box)!=7 or any(type(x) not in (int,float) or not math.isfinite(x) for x in box) or any(x<=0 for x in box[3:6]):
            raise ValueError('finite native upright box with positive dimensions required')
        values[category].append([*box[3:6],box[2]]);tracks[category].add((context,identity));frames.add((context,timestamp));contexts.add(context)
    classes={}
    for category,rows in values.items():
        a=np.asarray(rows,dtype=np.float64)
        classes[str(category)]={'box_rows':len(rows),'unique_tracks':len(tracks[category]),
            'median_length_width_height_center_z':np.median(a,axis=0).tolist() if rows else None,
            'p10_length_width_height_center_z':np.quantile(a,.1,axis=0,method='linear').tolist() if rows else None,
            'p90_length_width_height_center_z':np.quantile(a,.9,axis=0,method='linear').tolist() if rows else None}
    return {'rows':len(seen),'frames':len(frames),'observed_scenes':sorted(contexts),'classes':classes,
        'weighting':'one equally weighted native box row per frame/object; repeated track observations retained',
        'geometry':'native length,width,height,center_z in vehicle reference; no ROI clipping or heading-template inference',
        'scope':'training distribution only; missing class stays absent, no adopted anchors or scientific configuration'}
