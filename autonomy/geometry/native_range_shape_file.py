"""Read native shape metadata only after immutable source-byte admission."""
import re
import pyarrow.parquet as pq
from evidence.source_integrity import verify_source
from evidence.source_snapshot import require_regular_file
from .native_range_shapes import native_range_shapes,KEYS,SHAPES


def read_native_range_shapes(path,*,scene,source,inventory):
    if (not isinstance(source,dict) or set(source)!={'size_bytes','sha256','md5_base64'}
        or type(source['size_bytes']) is not int or source['size_bytes']<=0
        or not isinstance(source['sha256'],str)
        or not re.fullmatch('[0-9a-f]{64}',source['sha256'])):
        raise ValueError('external immutable byte identity required')
    actual=verify_source(path,**source)
    table=pq.ParquetFile(require_regular_file(path))
    keys=[k for k in table.schema_arrow.names if k.startswith('key.')]
    if set(keys)!=set(KEYS) or any(k not in table.schema_arrow.names for k in SHAPES):
        raise ValueError('complete native identity/shape columns required')
    def rows():
        for batch in table.iter_batches(batch_size=64,columns=list(KEYS+SHAPES)):
            yield from batch.to_pylist()
    result=native_range_shapes(rows(),scene=scene,inventory=inventory)
    verify_source(path,**source)
    return {'source':actual,'shapes':result,'scope':'byte-admitted native metadata only; staging/membership/runtime admission external'}
