import copy,json,math,sys,tempfile,unittest
from pathlib import Path
from resources.stage_accounting import measure,admit

class ProcessAccountingTests(unittest.TestCase):
 def run_child(self,source,timeout=10):
  with tempfile.TemporaryDirectory() as temp:
   with (Path(temp)/'log').open('w+') as stream:
    result=measure([sys.executable,'-c',source],cwd=temp,stream=stream,timeout=timeout)
    stream.seek(0);return result,stream.read()
 def test_waited_grandchild_peak_is_observed(self):
  child="import resource,json;data=bytearray(32*1024**2);print(json.dumps({'rss':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}),flush=True)"
  result,output=self.run_child('import subprocess,sys;subprocess.run([sys.executable,"-c",'+repr(child)+'],check=True)')
  observed=json.loads(output)['rss'];self.assertGreater(observed,32768);self.assertGreaterEqual(result['peak_rss_kib'],observed);self.assertEqual(result['exit_code'],0)
 def test_each_process_peak_is_not_cumulative(self):
  large,_=self.run_child('x=bytearray(48*1024**2)');small,_=self.run_child('pass')
  self.assertGreater(large['peak_rss_kib']-small['peak_rss_kib'],24*1024)
 def test_timeout_keeps_measured_failed_outcome(self):
  result,_=self.run_child('import time;time.sleep(10)',timeout=.05)
  self.assertTrue(result['timed_out']);self.assertNotEqual(result['exit_code'],0);self.assertGreater(result['peak_rss_kib'],0)
 def test_invalid_timeout_refused_before_start(self):
  for timeout in [True,0,-1,float('nan'),float('inf')]:
   with self.assertRaises(ValueError):self.run_child('raise Exception("must not execute")',timeout=timeout)

class AdmissionTests(unittest.TestCase):
 def fixture(self):
  return {'command':['python','worker.py'],'exit_code':0,'timed_out':False,'peak_rss_kib':100,'elapsed_seconds':1.,'measurement':'wait4.ru_maxrss_KiB_largest_waited_child','kernel_scope':{'path':'/user.slice/test/sureal-sustained-fixture.scope','memory_max_bytes':1024**3,'memory_swap_max_bytes':0,'oom':0,'oom_kill':0,'members_verified':True,'process_ids':[111]},'stage_lifecycle':{'caller_pid':111,'scope_members_before':[111],'scope_members_after':[111],'subreaper_verified':True,'remaining_children':[]}}
 def test_complete_measured_bound_is_admitted(self):
  self.assertEqual(admit(self.fixture(),['python','worker.py'],1024**3)['peak_rss_bytes'],102400)
 def test_mutated_or_missing_resource_proof_is_refused(self):
  for fault in ['command','exit','timeout','rss','boolrss','units','missing','cap','swap','oom','member','elapsed','scope','lifecycle-missing','lifecycle-children']:
   d=copy.deepcopy(self.fixture())
   if fault=='command':d['command']=['other']
   elif fault=='exit':d['exit_code']=True
   elif fault=='timeout':d['timed_out']=True
   elif fault=='rss':d['peak_rss_kib']=2*1024**2
   elif fault=='boolrss':d['peak_rss_kib']=True
   elif fault=='units':d['measurement']='inherited export RSS'
   elif fault=='missing':del d['kernel_scope']
   elif fault=='cap':d['kernel_scope']['memory_max_bytes']='max'
   elif fault=='swap':d['kernel_scope']['memory_swap_max_bytes']=1
   elif fault=='oom':d['kernel_scope']['oom_kill']=1
   elif fault=='member':d['kernel_scope']['members_verified']=False
   elif fault=='elapsed':d['elapsed_seconds']=float('nan')
   elif fault=='scope':d['kernel_scope']['path']='/unrelated'
   elif fault=='lifecycle-missing':d.pop('stage_lifecycle',None)
   else:d['stage_lifecycle']={'subreaper_verified':True,'remaining_children':[321]}
   with self.subTest(fault=fault),self.assertRaises(ValueError):admit(d,['python','worker.py'],1024**3)
if __name__=='__main__':unittest.main()
