import pathlib,json,hashlib,socket,sys,copy,importlib.util,os
import torch,numpy as np,scipy
P=pathlib.Path;H=lambda q:hashlib.sha256(P(q).read_bytes()).hexdigest()
r=json.loads(P('/tmp/producer/receipt.json').read_text());assert r['exit_code']==0
for n,h in r['artifacts'].items():assert H('/tmp/producer/'+n)==h
for n,h in r['source_hashes'].items():
 q='/tmp/probe.py' if n.endswith('/m0-b.py') else '/experiment/'+n.split('/experiments/waymo-perception/',1)[1]
 assert H(q)==h
for n,h in r['driver_hashes'].items():assert H('/driver/'+n)==h
home=P(os.environ['HOME']);home.mkdir();assert not list(home.iterdir());assert not P('/data02').exists();assert not P('/root/.config/gcloud').exists()
for q in ['/tmp/producer/gpu-probe.json','/experiment/association/contract.py','/opt/waymo/bin/python']:
 try:P(q).open('ab').close()
 except OSError:pass
 else:raise AssertionError('writable:'+q)
try:socket.create_connection(('127.0.0.1',int(sys.argv[1])),timeout=.5)
except OSError:pass
else:raise AssertionError('network reachable')
assert importlib.util.find_spec('tensorflow') is None
assert torch.__version__=='2.9.1+cu130' and scipy.__version__=='1.18.1' and np.__version__=='2.5.3'
assert torch.cuda.is_available() and torch.cuda.device_count()==1
assert P('/dev/nvidia1').exists() and not P('/dev/nvidia0').exists()
prod=json.loads(P('/tmp/producer/gpu-probe.json').read_text())
def analytic(d):
 assert d['analytic']['y']==[[2,6],[6,12]]
 assert d['analytic']['input_gradient']==[[8,36],[24,72]]
 assert d['analytic']['weight_gradient']==[[40,84],[56,120]]
analytic(prod);mut=copy.deepcopy(prod);mut['analytic']['y'][0][0]+=1
try:analytic(mut)
except AssertionError:pass
else:raise AssertionError('tampered numeric accepted')
assert prod['device']==torch.cuda.get_device_name(0);assert prod['capability']==list(torch.cuda.get_device_capability(0));assert prod['torch']==torch.__version__
x=torch.tensor([[1.,2.],[3.,4.]],device='cuda',dtype=torch.float64,requires_grad=True);w=torch.tensor([[2.,0.],[0.,3.]],device='cuda',dtype=torch.float64,requires_grad=True);y=x@w;y.square().sum().backward();assert y.detach().cpu().tolist()==[[2,6],[6,12]];assert x.grad.cpu().tolist()==[[8,36],[24,72]];assert w.grad.cpu().tolist()==[[40,84],[56,120]]
conv=torch.nn.Conv2d(3,8,3,padding=1).cuda();o=conv(torch.ones((2,3,64,64),device='cuda'));o.square().mean().backward();assert o.shape==(2,8,64,64);assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in conv.parameters())
cost=np.array([[4,1,3],[0,2,5]],dtype=np.float64);rr,cc=scipy.optimize.linear_sum_assignment(cost);assert cost[rr,cc].sum()==1;assert torch.equal(torch.from_numpy(cost).cuda().cpu(),torch.from_numpy(cost));torch.cuda.synchronize()
out={'scope':'independent CUDA runtime/isolation/driver and solver interoperability verification; no optimizer/study update','device':torch.cuda.get_device_name(0),'capability':list(torch.cuda.get_device_capability(0)),'producer_receipt_sha256':H('/tmp/producer/receipt.json'),'checker_sha256':H('/tmp/checker.py'),'rootfs_sha256':r['runtime_lock']['rootfs_sha256'],'driver_hashes':r['driver_hashes'],'source_hashes':r['source_hashes'],'numeric_tamper_rejected':True,'network_blocked':True,'readonly_root_source_input':True,'private_home':True,'single_physical_gpu':'/dev/nvidia1','torch':torch.__version__,'scipy':scipy.__version__,'numpy':np.__version__}
P('/outputs/check.json').write_text(json.dumps(out,indent=2));print('PASS independent CUDA+isolation+driver+numeric-tamper audit')
