import json,os,sys,tempfile,unittest
from pathlib import Path
from resources.scoped_stage import run_scoped
class ScopedStageTests(unittest.TestCase):
 def test_uncapped_invocation_refuses_before_worker_start(self):
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'must-not-exist'
   with (Path(temp)/'log').open('w') as stream,self.assertRaises(ValueError):
    run_scoped([sys.executable,'-c',f'open({str(path)!r},"w").write("bad")'],cwd=temp,stream=stream,timeout=5,cap_bytes=16*1024**3)
   self.assertFalse(path.exists())
if __name__=='__main__':unittest.main()
