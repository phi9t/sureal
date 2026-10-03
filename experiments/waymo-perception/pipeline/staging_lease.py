"""Exclusive local raw-staging ownership, including pre-lease acquisition guards."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat


def legacy_acquisition_pids():
    """Inspect live same-user process argv; do not trust an ownership marker file."""
    result=[]
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit() or int(entry.name)==os.getpid():continue
        try:
            if entry.stat().st_uid!=os.getuid():continue
            argv=(entry/'cmdline').read_bytes().split(b'\0')
        except (FileNotFoundError,ProcessLookupError):continue
        except PermissionError as error:raise ValueError('cannot verify staging process ownership') from error
        if any(arg and Path(os.fsdecode(arg)).name=='acquire-scientific-cohort.py' for arg in argv):
            result.append(int(entry.name))
    return sorted(result)


@contextmanager
def staging_lease(lock_path):
    """Reject competing leases and live legacy acquisition; never stop either."""
    descriptor=None;locked=False
    try:
        descriptor=os.open(lock_path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):raise ValueError('staging lock is not a regular file')
        fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB);locked=True
        blockers=legacy_acquisition_pids()
        if blockers:raise ValueError('live acquisition already owns raw staging: '+','.join(map(str,blockers)))
        yield
    except OSError as error:
        raise ValueError('raw staging lease unavailable') from error
    finally:
        if descriptor is not None:
            if locked:fcntl.flock(descriptor,fcntl.LOCK_UN)
            os.close(descriptor)
