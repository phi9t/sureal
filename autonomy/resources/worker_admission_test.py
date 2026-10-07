import copy,unittest
from resources.stage_accounting import admit_worker
class WorkerAdmissionTests(unittest.TestCase):
 def fixture(self):
  host={'command':['python','shim.py','/resources','worker.py'],'exit_code':0,'timed_out':False,'peak_rss_kib':100,'elapsed_seconds':1.,'measurement':'wait4.ru_maxrss_KiB_largest_waited_child','kernel_scope':{'path':'/user.slice/sureal-sustained-fixture.scope','memory_max_bytes':1024**3,'memory_swap_max_bytes':0,'oom':0,'oom_kill':0,'members_verified':True,'process_ids':[111]},'stage_lifecycle':{'caller_pid':111,'scope_members_before':[111],'scope_members_after':[111],'subreaper_verified':True,'remaining_children':[]}}
  worker={'worker_argv':['worker.py'],'worker_pid':123,'measurement':'in-runtime getrusage SELF and waited CHILDREN KiB','self_peak_rss_kib':150,'waited_child_peak_rss_kib':100,'peak_rss_kib':150,'elapsed_seconds':.8,'exit_code':0,'child_lifecycle':{'subreaper_verified':True,'remaining_children':[]}};return host,worker
 def test_actual_worker_peak_is_checked_separately(self):
  host,worker=self.fixture();self.assertEqual(admit_worker(host,worker,host['command'],['worker.py'],1024**3)['peak_rss_bytes'],150*1024)
 def test_worker_aliases_malformed_peak_and_foreign_argv_refused(self):
  for fault in ['argv','units','self','child','peak','over','pid','exit','elapsed','lifecycle-missing','lifecycle-children']:
   host,d=self.fixture()
   if fault=='argv':d['worker_argv']=['other.py']
   elif fault=='units':d['measurement']='copied preparation RSS'
   elif fault=='self':d['self_peak_rss_kib']=True
   elif fault=='child':d['waited_child_peak_rss_kib']=-1
   elif fault=='peak':d['peak_rss_kib']=100
   elif fault=='over':d['self_peak_rss_kib']=2*1024**2;d['peak_rss_kib']=d['self_peak_rss_kib']
   elif fault=='pid':d['worker_pid']=0
   elif fault=='exit':d['exit_code']=True
   elif fault=='elapsed':d['elapsed_seconds']=float('nan')
   elif fault=='lifecycle-missing':d.pop('child_lifecycle',None)
   else:d['child_lifecycle']={'subreaper_verified':True,'remaining_children':[124]}
   with self.subTest(fault=fault),self.assertRaises(ValueError):admit_worker(host,d,host['command'],['worker.py'],1024**3)
if __name__=='__main__':unittest.main()
