import json,os,signal,subprocess,sys,tempfile,unittest
from pathlib import Path
class WorkerAccountingTests(unittest.TestCase):
 def test_wrapper_imports_helpers_from_frozen_package_root(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);code=root/'code';(code/'resources').mkdir(parents=True);(code/'evidence').mkdir();out=root/'out';out.mkdir()
   (code/'resources/execute_worker.py').write_bytes(Path(__file__).with_name('execute_worker.py').read_bytes())
   (code/'resources/process_lifecycle.py').write_text('def enable_subreaper(): pass\ndef completed_lifecycle(): return {"subreaper_verified": True, "remaining_children": []}\n')
   marker=root/'frozen-helper-used'
   (code/'evidence/source_snapshot.py').write_text('from pathlib import Path\nPath('+repr(str(marker))+').write_text("yes")\ndef require_regular_file(path):\n path=Path(path)\n if not path.is_file(): raise ValueError("missing")\n return path\n')
   worker=root/'worker.py';worker.write_text('print("worker ran",flush=True)\n')
   env={**os.environ,'PYTHONPATH':str(code),'PYTHONDONTWRITEBYTECODE':'1'}
   result=subprocess.run([sys.executable,str(code/'resources/execute_worker.py'),str(out),str(worker)],capture_output=True,text=True,env=env)
   self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(marker.read_text(),'yes')
 def test_worker_source_argv_and_actual_self_peak_are_retained(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);worker=root/'worker.py';worker.write_text('import json,resource,sys\ndata=bytearray(32*1024**2)\nprint(json.dumps({"argv":sys.argv,"peak":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}),flush=True)\n')
   source=worker.read_bytes();shim=Path(__file__).with_name('execute_worker.py');result=subprocess.run([sys.executable,str(shim),str(root),str(worker),'sentinel'],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr);observed=json.loads(result.stdout);proof=json.loads((root/'worker-resource.json').read_text());self.assertEqual(observed['argv'],[str(worker),'sentinel']);self.assertEqual(proof['worker_argv'],observed['argv']);self.assertGreaterEqual(proof['self_peak_rss_kib'],observed['peak']);self.assertEqual(worker.read_bytes(),source)
 def test_unwaited_session_child_cannot_emit_success_receipt(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);worker=root/'worker.py';pidfile=root/'child.pid';worker.write_text('import subprocess,sys\nchild=subprocess.Popen([sys.executable,"-c","import time;time.sleep(5)"],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\nopen('+repr(str(pidfile))+',"w").write(str(child.pid))\n')
   try:
    result=subprocess.run([sys.executable,str(Path(__file__).with_name('execute_worker.py')),str(root),str(worker)],capture_output=True,text=True)
    self.assertNotEqual(result.returncode,0);self.assertFalse((root/'worker-resource.json').exists())
   finally:
    if pidfile.exists():
     try:os.kill(int(pidfile.read_text()),signal.SIGKILL)
     except ProcessLookupError:pass
 def test_failed_worker_cannot_emit_success_receipt(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);worker=root/'worker.py';worker.write_text('raise RuntimeError("controlled failure")\n');shim=Path(__file__).with_name('execute_worker.py');result=subprocess.run([sys.executable,str(shim),str(root),str(worker)],capture_output=True,text=True);self.assertNotEqual(result.returncode,0);self.assertFalse((root/'worker-resource.json').exists())
 def test_completed_orphan_cannot_evade_waited_child_accounting(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);worker=root/'worker.py'
   worker.write_text('import os,time\nparent=os.fork()\nif parent == 0:\n child=os.fork()\n if child == 0:\n  os.setsid();os._exit(0)\n os._exit(0)\nos.waitpid(parent,0)\ntime.sleep(.1)\n')
   result=subprocess.run([sys.executable,str(Path(__file__).with_name('execute_worker.py')),str(root),str(worker)],capture_output=True,text=True)
   self.assertNotEqual(result.returncode,0);self.assertFalse((root/'worker-resource.json').exists())
if __name__=='__main__':unittest.main()
