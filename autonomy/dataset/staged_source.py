"""Host transfer lifecycle for one bounded, verified scientific raw source."""
from contextlib import contextmanager
from pathlib import Path
import re
import resource
import subprocess
import tempfile
from dataset.scientific_admission import check_raw_capacity
from dataset.source_integrity import verify_source
from insula.staging_lease import staging_lease

WAYSTONE='/data02/home/philip.yang/workspace/waystone/scripts/waystone'


@contextmanager
def staged_source(record, cache, *, retained_bytes, limit_bytes, transfer_command=None):
    """Yield verified bytes under the shared lease; remove this stage on all exits.

    Transfer injection is for controlled lifecycle fixtures. Production callers
    use the sibling Waystone wrapper. RLIMIT_FSIZE also bounds a corrupt mirror
    larger than its declared size, rather than detecting excess only after write.
    """
    cache=Path(cache);cache.mkdir(parents=True,exist_ok=True)
    size=record['source_metadata']['size']
    if type(size) not in (str,int) or not re.fullmatch('[1-9][0-9]*',str(size)):
        raise ValueError('invalid source size')
    size=int(size)
    if record['sha256']!=record['hdfs_roundtrip_sha256']:
        raise ValueError('source/mirror identity conflict')
    if not isinstance(record['hdfs_uri'],str) or not record['hdfs_uri'].startswith('hdfs://'):
        raise ValueError('declared HDFS source required')
    with staging_lease(cache/'raw-staging.lock'):
        processing=cache/'scientific-processing-staging';processing.mkdir(exist_ok=True)
        existing=list((cache/'scientific-source-audit').glob('stage-*'))+list(processing.glob('stage-*'))
        check_raw_capacity(retained_bytes,size,limit_bytes,active_objects=len(existing))
        remaining=limit_bytes-retained_bytes
        _,hard=resource.getrlimit(resource.RLIMIT_FSIZE)
        child_limit=min(remaining,hard) if hard!=resource.RLIM_INFINITY else remaining
        if size>child_limit:raise ValueError('existing file-size limit cannot admit source')
        def cap_child():resource.setrlimit(resource.RLIMIT_FSIZE,(child_limit,child_limit))
        with tempfile.TemporaryDirectory(dir=processing,prefix='stage-') as tmp:
            path=Path(tmp)/'source.parquet'
            command=[*(transfer_command if transfer_command is not None else [WAYSTONE]),'get',record['hdfs_uri'],str(path)]
            result=subprocess.run(command,capture_output=True,text=True,preexec_fn=cap_child)
            if result.returncode:
                raise ValueError('source transfer failed or exceeded file-size cap: '+result.stderr[-1000:])
            evidence=verify_source(path,size_bytes=size,sha256=record['sha256'],md5_base64=record['source_metadata']['md5_hash'])
            evidence.update(hdfs_uri=record['hdfs_uri'],raw_peak_bytes_including_retained=retained_bytes+path.stat().st_size,
                            transfer_command=command,transfer_exit_code=result.returncode,file_size_limit_bytes=child_limit)
            yield path,evidence
