"""Share the actual experiment lock with retention without releasing ownership."""
import fcntl,os,stat
from pathlib import Path

def acquire_experiment_lock(path,inherited_fd=None):
 path=Path(path)
 if any(p.is_symlink() for p in [path,*path.parents]):raise ValueError('regular experiment lock ancestry required')
 if inherited_fd is None:
  descriptor=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
 else:
  if type(inherited_fd) is not int or inherited_fd<0:raise ValueError('valid inherited lock descriptor required')
  try:descriptor=os.dup(inherited_fd)
  except OSError as error:raise ValueError('inherited descriptor missing') from error
 try:
  found=os.fstat(descriptor);expected=path.stat()
  if not stat.S_ISREG(found.st_mode) or (found.st_dev,found.st_ino)!=(expected.st_dev,expected.st_ino):raise ValueError('inherited descriptor is not the declared experiment lock')
  fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
  return os.fdopen(descriptor,'a')
 except BaseException:
  os.close(descriptor);raise
