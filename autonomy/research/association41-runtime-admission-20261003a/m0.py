import fcntl,hashlib,json,socket,subprocess,sys,time
from pathlib import Path
from pipeline.runtime_identity import verify_rootfs
from pipeline.insula_entry import launch_plan
role=sys.argv[1]
cache=Path.home()/'.cache/waystone/waymo-perception'
root=cache/'insula'/('association41-'+role+'-20261003a')
lock=json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,lock['rootfs_sha256'])
experiment=Path('experiments/waymo-perception').resolve()
source=Path('.scratch/association41-source').resolve()
if role=='cpu': (source/'sentinel').write_text('readonly input\n')
out=cache/'insula'/('association41-'+role+'-m0-20261003a');out.mkdir(exist_ok=False)
listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(2)
port=listener.getsockname()[1]
with socket.create_connection(('127.0.0.1',port),timeout=1): pass
peer,_=listener.accept();peer.close()
code='''import json,runpy,sys,numpy as np,scipy
from scipy.optimize import linear_sum_assignment
from pathlib import Path
'''
if role=='cpu':
 code+=f"sys.argv=['m0_probe.py','{port}']; runpy.run_module('pipeline.m0_probe',run_name='__main__')\n"
 interpreter='/usr/local/bin/python'
else:
 code+="runpy.run_path('/experiment/gpu/probe.py',run_name='__main__')\n"
 interpreter='/opt/waymo/bin/python'
code+='''assert np.__version__=='2.5.3' and scipy.__version__=='1.18.1'
cost=np.array([[0.,1.],[0.,10.]],dtype=np.float64)
r,c=linear_sum_assignment(cost)
assert r.tolist()==[0,1] and c.tolist()==[1,0] and float(cost[r,c].sum())==1.
try: linear_sum_assignment(np.array([[0.,np.inf],[0.,np.inf]]))
except ValueError: pass
else: raise AssertionError('infeasible assignment accepted')
Path('/outputs/solver.json').write_text(json.dumps({'numpy':np.__version__,'scipy':scipy.__version__,'scipy_file':scipy.__file__,'rows':r.tolist(),'columns':c.tolist(),'objective':float(cost[r,c].sum()),'infeasible_rejected':True}))
'''
if role=='training': code+='''import torch
assert torch.__version__=='2.9.1+cu130'
t=torch.from_numpy(cost).cuda(); assert torch.equal(t.cpu(),torch.from_numpy(cost))
Path('/outputs/interop.json').write_text(json.dumps({'numpy_torch_roundtrip':True,'torch':torch.__version__}))
'''
plan=launch_plan(root,experiment,source,out,[interpreter,'-c',code]);driver={};handle=None
if role=='training':
 handle=(cache/'insula/architecture-experiments.lock').open('a')
 try: fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:
  (out/'blocked.json').write_text(json.dumps({'reason':'existing GPUlock held; no GPU launch'}));raise
 extra=['--tmpfs','/driver']
 for device in ['/dev/nvidia1','/dev/nvidiactl','/dev/nvidia-uvm']:
  if not Path(device).exists(): raise RuntimeError('missing device '+device)
  extra+=['--dev-bind',device,device]
 for prefix in ['libcuda.so','libnvidia-ptxjitcompiler.so','libnvidia-nvvm.so']:
  for p in sorted(Path('/usr/lib/x86_64-linux-gnu').glob(prefix+'*')):
   if p.is_file():
    extra+=['--ro-bind',str(p.resolve()),'/driver/'+p.name]
    driver[p.name]=hashlib.sha256(p.resolve().read_bytes()).hexdigest()
 extra+=['--setenv','PATH','/opt/waymo/bin:/usr/local/cuda/bin:/usr/local/bin:/usr/bin:/bin','--setenv','LD_LIBRARY_PATH','/driver:/usr/local/cuda/lib64','--setenv','CUDA_VISIBLE_DEVICES','0']
 plan[plan.index('--'):plan.index('--')]=extra
paths=[experiment/'association/contract.py',experiment/'association/test_contract.py',Path(__file__).resolve(),experiment/('pipeline/m0_probe.py' if role=='cpu' else 'gpu/probe.py')]
def hashes():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
before=hashes();started=time.monotonic()
try:
 result=subprocess.run(plan,capture_output=True,text=True,timeout=120)
finally:
 listener.close()
 if handle: handle.close()
(out/'stdout').write_text(result.stdout);(out/'stderr').write_text(result.stderr)
assert before==hashes(),'source changed during execution'
receipt={'stage':'association41-'+role+'-M0-producer','runtime_lock':lock,'driver_hashes':driver,'command':plan,'source_hashes':before,'exit_code':result.returncode,'elapsed_seconds':time.monotonic()-started,'artifacts':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()},'admission_status':'pending independent verification'}
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(result.stdout,result.stderr,json.dumps({'output':str(out),'exit_code':result.returncode}),flush=True)
raise SystemExit(result.returncode)
