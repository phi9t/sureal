"""Native range-image dimensions with complete original row/key admission.

Input is metadata only. Null shape means a missing native shape, never an inferred
empty grid. Source-byte and membership admission must occur before this adapter.
"""
import hashlib
import json
import re
from collections.abc import Mapping

KEYS=('key.segment_context_name','key.frame_timestamp_micros','key.laser_name')
SHAPES=tuple(f'[LiDARComponent].range_image_return{i}.shape' for i in (1,2))

def native_range_shapes(rows,*,scene,inventory):
    if (not isinstance(scene,str) or not scene or not isinstance(inventory,Mapping)
        or type(inventory.get('rows')) is not int or inventory['rows']<0
        or not isinstance(inventory.get('key_sha256'),str)
        or not re.fullmatch('[0-9a-f]{64}',inventory['key_sha256'])):
        raise ValueError('explicit scene and admitted native key inventory required')
    seen=set();digest=hashlib.sha256();records=[];count=present=null=0
    for row in rows:
        if not isinstance(row,Mapping) or any(k not in row for k in KEYS+SHAPES):
            raise ValueError('native keys and both shape fields required')
        if any(k.startswith('key.') and k not in KEYS for k in row):
            raise ValueError('unexpected native identity fields')
        context,timestamp,laser=(row[k] for k in KEYS)
        if (context!=scene or type(timestamp) is not int or not 0<=timestamp<2**63
            or type(laser) is not int or laser not in range(1,6)):
            raise ValueError('native context/time/sensor identity differs')
        identity=json.dumps({k:row[k] for k in KEYS},sort_keys=True,separators=(',',':'))
        if identity in seen:raise ValueError('duplicate native row')
        seen.add(identity);digest.update((identity+'\n').encode());count+=1
        if count>inventory['rows']:raise ValueError('extra source rows')
        for ret,field in enumerate(SHAPES,1):
            shape=row[field]
            if shape is not None:
                if (not isinstance(shape,(list,tuple)) or len(shape)!=3
                    or any(type(x) is not int or x<=0 for x in shape) or shape[2]!=4):
                    raise ValueError('native positive H/W and four channels required')
                shape=list(shape);present+=1
            else:null+=1
            records.append({'context':context,'timestamp':timestamp,'laser':laser,
                            'return':ret,'native_shape':shape})
    if count!=inventory['rows'] or digest.hexdigest()!=inventory['key_sha256']:
        raise ValueError('complete native row/key inventory differs')
    return {'scene':scene,'native_rows':count,'key_sha256':digest.hexdigest(),
            'present_shape_records':present,'null_shape_records':null,'records':records,
            'scope':'native metadata dimensions only; no positive-return extent inference'}
