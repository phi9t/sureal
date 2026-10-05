"""Independent literal native shape admission, without extractor reuse."""
import hashlib
import json
from collections.abc import Mapping
import pyarrow.parquet as pq
from .source_integrity import verify_source


def verify_native_range_shapes(path,report,*,scene,source,inventory):
    verify_source(path,**source)
    if (not isinstance(report,Mapping) or report.get('scene')!=scene
        or not isinstance(report.get('records'),list) or not isinstance(inventory,Mapping)
        or type(inventory.get('rows')) is not int or inventory['rows']<0):
        raise ValueError('external identity/inventory and complete report required')
    keys=['key.segment_context_name','key.frame_timestamp_micros','key.laser_name']
    fields=['[LiDARComponent].range_image_return1.shape','[LiDARComponent].range_image_return2.shape']
    digest=hashlib.sha256();seen=set();index=count=present=null=0
    table=pq.ParquetFile(path)
    if set(k for k in table.schema_arrow.names if k.startswith('key.'))!=set(keys):
        raise ValueError('native source key columns differ')
    for batch in table.iter_batches(batch_size=97,columns=keys+fields):
        for row in batch.to_pylist():
            key={k:row[k] for k in keys};text=json.dumps(key,sort_keys=True,separators=(',',':'))
            if (text in seen or key[keys[0]]!=scene or type(key[keys[1]]) is not int
                or not 0<=key[keys[1]]<2**63 or type(key[keys[2]]) is not int
                or key[keys[2]] not in range(1,6)):
                raise ValueError('source identity invalid or duplicate')
            seen.add(text);digest.update((text+'\n').encode());count+=1
            for ret,field in enumerate(fields,1):
                shape=row[field]
                if shape is not None:
                    if len(shape)!=3 or any(type(v) is not int or v<=0 for v in shape) or shape[2]!=4:
                        raise ValueError('source dimensions invalid')
                    present+=1
                else:null+=1
                expected={'context':scene,'timestamp':key[keys[1]],'laser':key[keys[2]],'return':ret,'native_shape':shape}
                if index>=len(report['records']) or report['records'][index]!=expected:
                    raise ValueError('reported native shape/identity differs')
                index+=1
    if (index!=len(report['records']) or count!=inventory['rows']
        or digest.hexdigest()!=inventory['key_sha256'] or report.get('native_rows')!=count
        or report.get('key_sha256')!=digest.hexdigest()
        or report.get('present_shape_records')!=present or report.get('null_shape_records')!=null):
        raise ValueError('complete report/inventory accounting differs')
    verify_source(path,**source)
    return {'scene':scene,'records_verified':index,'native_rows':count,
            'present_shape_records':present,'null_shape_records':null,
            'source_sha256':source['sha256'],'scope':'independent literal source-shape comparison; provenance/runtime admission external'}
