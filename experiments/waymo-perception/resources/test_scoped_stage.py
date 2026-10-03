import json,os,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from resources.scoped_stage import run_scoped
from resources.process_lifecycle import direct_children
class ScopedStageTests(unittest.TestCase):
 def test_uncapped_invocation_refuses_before_worker_start(self):
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'must-not-exist'
   with (Path(temp)/'log').open('w') as stream,self.assertRaises(ValueError):
    run_scoped([sys.executable,'-c',f'open({str(path)!r},"w").write("bad")'],cwd=temp,stream=stream,timeout=5,cap_bytes=16*1024**3)
   self.assertFalse(path.exists())

 def settle(self,*args):
  try:from resources.scoped_stage import _settle_launchers
  except ImportError:self.fail('terminal launcher accounting must wait boundedly for actual adopted helper completion')
  return _settle_launchers(*args)

 def scope(self,*args):
  return {'path':'/fixture/sureal-sustained-helper.scope','process_ids':sorted([os.getpid(),*direct_children()])}

 def test_delayed_launcher_exit_is_waited_and_measured_before_terminal_snapshot(self):
  pid=os.fork()
  if pid==0:
   time.sleep(.02);os._exit(0)
  try:
   with patch('resources.scoped_stage.read_scope',self.scope):
    completed,terminal,children=self.settle(16*1024**3,os.getpid(),time.monotonic()+.5)
   self.assertEqual(children,[]);self.assertEqual(terminal['process_ids'],[os.getpid()])
   self.assertIn(pid,[r['pid'] for r in completed]);self.assertGreater(next(r['peak_rss_kib'] for r in completed if r['pid']==pid),0)
   with self.assertRaises(ChildProcessError):os.waitpid(pid,os.WNOHANG)
  finally:
   try:os.kill(pid,9);os.waitpid(pid,0)
   except ProcessLookupError:pass
   except ChildProcessError:pass

 def test_running_launcher_descendant_still_remains_a_violation_after_deadline(self):
  pid=os.fork()
  if pid==0:
   time.sleep(5);os._exit(0)
  try:
   started=time.monotonic()
   with patch('resources.scoped_stage.read_scope',self.scope):
    completed,terminal,children=self.settle(16*1024**3,os.getpid(),started+.03)
   self.assertIn(pid,children);self.assertIn(pid,terminal['process_ids']);self.assertNotIn(pid,[r['pid'] for r in completed]);self.assertLess(time.monotonic()-started,.5)
  finally:
   os.kill(pid,9);os.waitpid(pid,0)
if __name__=='__main__':unittest.main()
