from pathlib import Path
import subprocess,sys,tempfile,unittest
from insula.staging_lease import staging_lease

class StagingLeaseTests(unittest.TestCase):
    def child(self,path):
        code='from pathlib import Path; from insula.staging_lease import staging_lease\ntry:\n with staging_lease(Path('+repr(str(path))+')): pass\nexcept ValueError: raise SystemExit(3)'
        return subprocess.run([sys.executable,'-c',code],capture_output=True,text=True).returncode

    def test_exclusive_cross_process_and_release_after_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock=Path(tmp)/'raw.lock'
            with staging_lease(lock):self.assertEqual(self.child(lock),3)
            self.assertEqual(self.child(lock),0)
            with self.assertRaises(RuntimeError):
                with staging_lease(lock):raise RuntimeError('fixture')
            self.assertEqual(self.child(lock),0)

    def test_legacy_acquisition_process_refuses_new_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);script=root/'acquire-scientific-cohort.py';script.write_text("print('ready',flush=True)\ninput()\n")
            process=subprocess.Popen([sys.executable,str(script)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
            try:
                self.assertEqual(process.stdout.readline().strip(),'ready')
                with self.assertRaises(ValueError):
                    with staging_lease(root/'raw.lock'):pass
            finally:
                process.communicate('\n',timeout=5)
            with staging_lease(root/'raw.lock'):pass

    def test_symlink_lock_rejected_without_touching_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);target=root/'keep';target.write_text('retained');lock=root/'raw.lock';lock.symlink_to(target)
            with self.assertRaises(ValueError):
                with staging_lease(lock):pass
            self.assertEqual(target.read_text(),'retained')

if __name__=='__main__':unittest.main()
