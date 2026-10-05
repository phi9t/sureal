"""Read native shape metadata only after immutable source-byte admission."""
import base64
import hashlib
import os
import re
import stat
import pyarrow.parquet as pq
from .native_range_shapes import native_range_shapes,KEYS,SHAPES


def read_native_range_shapes(path,*,scene,source,inventory):
    if (not isinstance(source,dict) or set(source)!={'size_bytes','sha256','md5_base64'}
        or type(source['size_bytes']) is not int or source['size_bytes']<=0
        or not isinstance(source['sha256'],str)
        or not re.fullmatch('[0-9a-f]{64}',source['sha256'])):
        raise ValueError('external immutable byte identity required')
    try:
        md5=base64.b64decode(source['md5_base64'],validate=True)
        if len(md5)!=16 or base64.b64encode(md5).decode()!=source['md5_base64']:
            raise ValueError('canonical MD5 required')
    except (ValueError,TypeError) as error:raise ValueError('canonical MD5 required') from error
    try:fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    except OSError as error:raise ValueError('regular nonsymlink source required') from error
    with os.fdopen(fd,'rb') as handle:
        before=os.fstat(handle.fileno())
        identity=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        if not stat.S_ISREG(before.st_mode) or before.st_size!=source['size_bytes']:
            raise ValueError('immutable source size differs')
        sha,md5=hashlib.sha256(),hashlib.md5();count=0
        for block in iter(lambda:handle.read(1024*1024),b''):
            count+=len(block);sha.update(block);md5.update(block)
        actual={'size_bytes':count,'sha256':sha.hexdigest(),
                'md5_base64':base64.b64encode(md5.digest()).decode()}
        if actual!=source or identity(before)!=identity(os.fstat(handle.fileno())):
            raise ValueError('source content differs or changed before decoding')
        handle.seek(0);table=pq.ParquetFile(handle)
        keys=[k for k in table.schema_arrow.names if k.startswith('key.')]
        if set(keys)!=set(KEYS) or any(k not in table.schema_arrow.names for k in SHAPES):
            raise ValueError('complete native identity/shape columns required')
        def rows():
            for batch in table.iter_batches(batch_size=64,columns=list(KEYS+SHAPES)):
                yield from batch.to_pylist()
        result=native_range_shapes(rows(),scene=scene,inventory=inventory)
        if identity(before)!=identity(os.fstat(handle.fileno())):
            raise ValueError('source changed while decoding')
    return {'source':actual,'shapes':result,'scope':'byte-admitted native metadata only; staging/membership/runtime admission external'}
