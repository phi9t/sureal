"""Bounded 4096-byte native direct-write staging; exact final identity required.

Versioned separately to preserve previously admitted exact-limit code pins.
"""
from contextlib import contextmanager
from pathlib import Path
import re
import resource
import subprocess
import tempfile
from evidence.source_snapshot import file_sha256, require_regular_file
from insula.staging_lease import staging_lease

WAYSTONE='/data02/home/philip.yang/workspace/waystone/scripts/waystone'


def working_bytes(root):
    total=0
    for path in Path(root).rglob('*'):
        if path.is_dir() and not path.is_symlink():
            continue
        total+=require_regular_file(path).stat().st_size
    return total


@contextmanager
def staged_derived_archive(record,cache,*,working_limit_bytes,transfer_command=None):
    """Keep both leases through the caller's offline consumer; remove on exit."""
    size=record['archive_bytes'];expected=record['archive_sha256'];uri=record['archive_hdfs_uri']
    if (type(size) is not int or size<=0 or type(working_limit_bytes) is not int
            or working_limit_bytes<=0 or not isinstance(expected,str)
            or not re.fullmatch('[0-9a-f]{64}',expected)
            or not isinstance(uri,str) or not uri.startswith('hdfs://')):
        raise ValueError('immutable derived archive and positive working cap required')
    cache=Path(cache);working=cache/'scientific-processing';working.mkdir(parents=True,exist_ok=True)
    with staging_lease(working/'cohort-queue.lock'),staging_lease(cache/'raw-staging.lock'):
        stages=working/'semantic-recovery-staging';stages.mkdir(exist_ok=True)
        if list(stages.glob('stage-*')):
            raise ValueError('existing derived staging must be reconciled')
        before=working_bytes(working)
        aligned_size=((size+4095)//4096)*4096
        if before+aligned_size>working_limit_bytes:
            raise ValueError('derived archive exceeds remaining working capacity')
        _,hard=resource.getrlimit(resource.RLIMIT_FSIZE)
        child_limit=min(aligned_size,hard) if hard!=resource.RLIM_INFINITY else aligned_size
        if child_limit<aligned_size:
            raise ValueError('inherited file-size limit cannot admit archive')
        def cap_child():resource.setrlimit(resource.RLIMIT_FSIZE,(child_limit,child_limit))
        with tempfile.TemporaryDirectory(dir=stages,prefix='stage-') as tmp:
            path=Path(tmp)/'scene.tar'
            prefix=transfer_command if transfer_command is not None else ['timeout','--kill-after=10s','600s',WAYSTONE]
            command=[*prefix,'get',uri,str(path)]
            result=subprocess.run(command,capture_output=True,text=True,preexec_fn=cap_child)
            if result.returncode:
                raise ValueError('derived transfer failed or exceeded declared size: '+result.stderr[-1000:])
            path = require_regular_file(path)
            if path.stat().st_size!=size:
                raise ValueError('derived source size/type differs')
            actual=file_sha256(path)
            if actual!=expected:
                raise ValueError('derived archive digest differs')
            yield path,{'sha256':actual,'archive_bytes':size,'hdfs_uri':uri,
                        'working_bytes_before':before,'working_peak_bytes_before_consumer':working_bytes(working),
                        'working_limit_bytes':working_limit_bytes,'file_size_limit_bytes':child_limit,
                        'transfer_contract':'native-direct-write-aligned-v1',
                        'transfer_alignment_bytes':4096,'transfer_padding_bytes':aligned_size-size,
                        'working_peak_bound_bytes':before+aligned_size,
                        'transfer_command':command,'transfer_exit_code':0,
                        'scope':'derived archive staging; not raw sensor reacquisition'}
