import os,sys,tempfile,time,unittest
from pathlib import Path
from geometry.native_shape_transfer import bounded_transfer
class TransferTests(unittest.TestCase):
 def test_success_and_nonzero_exit_propagated(self):
  self.assertEqual(bounded_transfer([sys.executable,'-c','pass'],timeout_seconds=2)['exit_code'],0)
  self.assertEqual(bounded_transfer([sys.executable,'-c','raise SystemExit(7)'],timeout_seconds=2)['exit_code'],7)
 def test_timeout_kills_and_reaps_owned_process(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'pid';program='import os,time; from pathlib import Path; Path('+repr(str(p))+').write_text(str(os.getpid())); time.sleep(20)';start=time.monotonic()
   with self.assertRaisesRegex(ValueError,'deadline'):bounded_transfer([sys.executable,'-c',program],timeout_seconds=.3)
   self.assertLess(time.monotonic()-start,3);self.assertTrue(p.exists());self.assertFalse(Path('/proc/'+p.read_text()).exists())
 def test_invalid_deadlines_refused(self):
  for value in [0,-1,True,float('inf'),float('nan')]:
   with self.assertRaises(ValueError):bounded_transfer([sys.executable,'-c','pass'],timeout_seconds=value)
if __name__=='__main__':unittest.main()
