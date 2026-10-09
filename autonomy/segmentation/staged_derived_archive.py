"""One verified derived archive under queue exclusion and working-storage cap."""
from contextlib import contextmanager
from pathlib import Path
import re
import resource
import tempfile
from blob_store.core import (
    BlobStore,
    BlobStoreError,
    blob_adapter_from_descriptor,
    blob_key_from_uri,
    default_waystone_descriptor,
    validate_blob_key,
)
from evidence.source_snapshot import file_sha256, require_regular_file
from insula.staging_lease import staging_lease

def working_bytes(root):
    total=0
    for path in Path(root).rglob('*'):
        if path.is_dir() and not path.is_symlink():
            continue
        total+=require_regular_file(path).stat().st_size
    return total


def _archive_identity(record):
    blob=record.get('archive_blob') if isinstance(record,dict) else None
    if isinstance(blob,dict):
        size=blob.get('bytes');expected=blob.get('sha256')
    else:
        size=record['archive_bytes'];expected=record['archive_sha256']
    return size,expected


def _record_store_descriptor(record):
    descriptor=record.get('store_descriptor') or record.get('blob_store_descriptor')
    if descriptor is None:
        return default_waystone_descriptor()
    return descriptor


def _archive_location(record):
    blob=record.get('archive_blob') if isinstance(record,dict) else None
    if isinstance(blob,dict) and 'key' in blob:
        return blob['key']
    if 'archive_blob_key' in record:
        return record['archive_blob_key']
    return record['archive_hdfs_uri']


def _blob_store_and_key(record,blob_store,blob_adapter):
    location=_archive_location(record)
    descriptor=_record_store_descriptor(record)
    adapter=blob_adapter
    if blob_store is None and adapter is None:
        adapter=blob_adapter_from_descriptor(descriptor)
    if isinstance(location,str) and not location.startswith('hdfs://'):
        key=validate_blob_key(location)
    else:
        key=blob_key_from_uri(location,adapter if adapter is not None else descriptor)
    if blob_store is None:
        blob_store=BlobStore(adapter)
    return blob_store,key


@contextmanager
def staged_derived_archive(record,cache,*,working_limit_bytes,blob_store=None,blob_adapter=None):
    """Keep both leases through the caller's offline consumer; remove on exit."""
    size,expected=_archive_identity(record);location=_archive_location(record)
    if (type(size) is not int or size<=0 or type(working_limit_bytes) is not int
            or working_limit_bytes<=0 or not isinstance(expected,str)
            or not re.fullmatch('[0-9a-f]{64}',expected)
            or not isinstance(location,str)):
        raise ValueError('immutable derived archive and positive working cap required')
    store,key=_blob_store_and_key(record,blob_store,blob_adapter)
    cache=Path(cache);working=cache/'scientific-processing';working.mkdir(parents=True,exist_ok=True)
    with staging_lease(working/'cohort-queue.lock'),staging_lease(cache/'raw-staging.lock'):
        stages=working/'semantic-recovery-staging';stages.mkdir(exist_ok=True)
        if list(stages.glob('stage-*')):
            raise ValueError('existing derived staging must be reconciled')
        before=working_bytes(working)
        if before+size>working_limit_bytes:
            raise ValueError('derived archive exceeds remaining working capacity')
        _,hard=resource.getrlimit(resource.RLIMIT_FSIZE)
        child_limit=min(size,hard) if hard!=resource.RLIM_INFINITY else size
        if child_limit<size:
            raise ValueError('inherited file-size limit cannot admit archive')
        with tempfile.TemporaryDirectory(dir=stages,prefix='stage-') as tmp:
            path=Path(tmp)/'scene.tar'
            try:
                store.get(key,path,expected,expected_bytes=size)
            except BlobStoreError as error:
                raise ValueError('derived blob fetch failed') from error
            path = require_regular_file(path)
            if path.stat().st_size!=size:
                raise ValueError('derived source size/type differs')
            actual=file_sha256(path)
            if actual!=expected:
                raise ValueError('derived archive digest differs')
            evidence={'sha256':actual,'archive_bytes':size,'blob_key':key,
                        'store_descriptor':_record_store_descriptor(record),
                        'working_bytes_before':before,'working_peak_bytes_before_consumer':working_bytes(working),
                        'working_limit_bytes':working_limit_bytes,'file_size_limit_bytes':child_limit,
                        'transfer_exit_code':0,'verified_by_readback':True,
                        'scope':'derived archive staging; not raw sensor reacquisition'}
            if isinstance(location,str) and location.startswith('hdfs://'):
                evidence['hdfs_uri']=location
            yield path,evidence
