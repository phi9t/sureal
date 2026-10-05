import tempfile,unittest
from pathlib import Path
from resources.kernel_scope import read_scope
class KernelScopeTests(unittest.TestCase):
 def fixture(self,root):
  proc=root/'proc';cg=root/'cgroups';path='/user.slice/sureal-sustained-test.scope';scope=cg/path.lstrip('/')
  scope.mkdir(parents=True);(proc/'self').mkdir(parents=True);(proc/'123').mkdir();(proc/'self/cgroup').write_text('0::'+path+'\n');(proc/'123/cgroup').write_text('0::'+path+'\n')
  for name,value in [('memory.max','67108864'),('memory.swap.max','0'),('memory.events','low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\n'),('cgroup.procs','123\n')]: (scope/name).write_text(value)
  return proc,cg,scope
 def test_actual_scope_controls_and_process_membership_required(self):
  with tempfile.TemporaryDirectory() as temp:
   proc,cg,scope=self.fixture(Path(temp));d=read_scope(67108864,pid=123,proc=proc,cgroups=cg);self.assertTrue(d['members_verified']);self.assertEqual(d['memory_max_bytes'],67108864)
 def test_kernel_limits_oom_and_escape_refused(self):
  for fault in ['max','swap','oom','oom_kill','escaped','unsafe','missing','duplicate','boolpid','procs-missing','procs-malformed','pid-absent']:
   with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
    proc,cg,scope=self.fixture(Path(temp));pid=123
    if fault=='max':(scope/'memory.max').write_text('max')
    elif fault=='swap':(scope/'memory.swap.max').write_text('1')
    elif fault=='oom':(scope/'memory.events').write_text('oom 1\noom_kill 0\n')
    elif fault=='oom_kill':(scope/'memory.events').write_text('oom 0\noom_kill 1\n')
    elif fault=='escaped':(proc/'123/cgroup').write_text('0::/other\n')
    elif fault=='unsafe':(proc/'self/cgroup').write_text('0::/user.slice/../sureal-sustained-test.scope\n')
    elif fault=='missing':(scope/'memory.max').unlink()
    elif fault=='duplicate':(scope/'memory.events').write_text('oom 0\noom 0\noom_kill 0\n')
    elif fault=='procs-missing':(scope/'cgroup.procs').unlink()
    elif fault=='procs-malformed':(scope/'cgroup.procs').write_text('123\nbad\n')
    elif fault=='pid-absent':(scope/'cgroup.procs').write_text('456\n')
    else:pid=True
    with self.assertRaises(ValueError):read_scope(67108864,pid=pid,proc=proc,cgroups=cg)
if __name__=='__main__':unittest.main()
