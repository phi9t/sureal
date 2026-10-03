import fcntl,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from cohort.sustained_controller_lock import acquire_experiment_lock
class ControllerLockTests(unittest.TestCase):
 def test_shared_descriptor_keeps_lock_after_child_releases_copy(self):
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp)/'experiment.lock'
   with acquire_experiment_lock(p) as held:
    command=[sys.executable,'-c',"from cohort.sustained_controller_lock import acquire_experiment_lock; import sys; acquire_experiment_lock(sys.argv[1],int(sys.argv[2])).close()",str(p),str(held.fileno())]
    subprocess.run(command,pass_fds=(held.fileno(),),check=True)
    with p.open('a') as other:
     with self.assertRaises(BlockingIOError):fcntl.flock(other,fcntl.LOCK_EX|fcntl.LOCK_NB)
   with acquire_experiment_lock(p):pass
 def test_foreign_boolean_missing_and_symlink_descriptors_refused(self):
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp)/'lock';p.touch();foreign=Path(temp)/'foreign';foreign.touch()
   with foreign.open('a') as stream:
    with self.assertRaises(ValueError):acquire_experiment_lock(p,stream.fileno())
   for fd in [True,-1,999999]:
    with self.assertRaises(ValueError):acquire_experiment_lock(p,fd)
   link=Path(temp)/'link';link.symlink_to(p)
   with self.assertRaises(ValueError):acquire_experiment_lock(link)
 def test_another_open_description_cannot_bypass_existing_owner(self):
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp)/'lock'
   with acquire_experiment_lock(p),p.open('a') as other:
    with self.assertRaises(BlockingIOError):acquire_experiment_lock(p,other.fileno())
if __name__=='__main__':unittest.main()
