"""Host transfer lifecycle for one bounded, verified scientific raw source."""
from contextlib import contextmanager
from pathlib import Path
import re
import resource
import tempfile
from blob_store.core import BlobStoreError
from dataset.blob_storage import fetch_record_blob, record_blob, record_store_descriptor
from dataset.scientific_admission import check_raw_capacity
from dataset.source_integrity import verify_source
from insula.staging_lease import staging_lease


@contextmanager
def staged_source(record, cache, *, retained_bytes, limit_bytes, blob_store=None):
    """Yield verified bytes under the shared lease; remove this stage on all exits.

    Production callers and tests use the blob store interface.
    """
    cache=Path(cache);cache.mkdir(parents=True,exist_ok=True)
    size=record['source_metadata']['size']
    if type(size) not in (str,int) or not re.fullmatch('[1-9][0-9]*',str(size)):
        raise ValueError('invalid source size')
    size=int(size)
    blob=record_blob(record)
    if blob['sha256']!=record['sha256'] or blob['bytes']!=size:
        raise ValueError('source/blob identity conflict')
    with staging_lease(cache/'raw-staging.lock'):
        processing=cache/'scientific-processing-staging';processing.mkdir(exist_ok=True)
        existing=list((cache/'scientific-source-audit').glob('stage-*'))+list(processing.glob('stage-*'))
        check_raw_capacity(retained_bytes,size,limit_bytes,active_objects=len(existing))
        remaining=limit_bytes-retained_bytes
        _,hard=resource.getrlimit(resource.RLIMIT_FSIZE)
        child_limit=min(remaining,hard) if hard!=resource.RLIM_INFINITY else remaining
        if size>child_limit:raise ValueError('existing file-size limit cannot admit source')
        with tempfile.TemporaryDirectory(dir=processing,prefix='stage-') as tmp:
            path=Path(tmp)/'source.parquet'
            try:
                fetch_record_blob(record,path,blob_store=blob_store)
            except BlobStoreError as error:
                raise ValueError('source blob fetch failed') from error
            evidence=verify_source(path,size_bytes=size,sha256=record['sha256'],md5_base64=record['source_metadata']['md5_hash'])
            evidence.update(raw_peak_bytes_including_retained=retained_bytes+path.stat().st_size,
                            file_size_limit_bytes=child_limit)
            evidence['blob']=dict(blob)
            if 'store_descriptor' in record:
                evidence['store_descriptor']=record_store_descriptor(record)
            elif 'hdfs_uri' in record:
                evidence['legacy_hdfs_uri']=record['hdfs_uri']
            yield path,evidence
