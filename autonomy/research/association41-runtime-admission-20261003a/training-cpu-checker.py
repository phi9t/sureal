import json,pathlib,hashlib,importlib.util
import numpy as np,scipy,torch
from tier1.models import build
from tier1.catalog import BASE
P=pathlib.Path
H=lambda q:hashlib.sha256(P(q).read_bytes()).hexdigest()
r=json.loads(P('/tmp/producer/receipt.json').read_text());producer=json.loads(P('/tmp/producer/check.json').read_text());assert r['exit_code']==0
for n,h in r['artifacts'].items():assert H('/tmp/producer/'+n)==h
for n,h in r['source_hashes'].items():
 q='/tmp/probe.py' if n.endswith('/training-root-cpu-probe.py') else '/experiment/'+n.split('/experiments/waymo-perception/',1)[1]
 assert H(q)==h
assert torch.__version__=='2.9.1+cu130' and scipy.__version__=='1.18.1' and np.__version__=='2.5.3'
assert not torch.cuda.is_available() and torch.cuda.device_count()==0 and not list(P('/dev').glob('nvidia*'))
assert importlib.util.find_spec('tensorflow') is None
cost=np.array([[4,1,3],[0,2,5]],dtype=np.float64);rr,cc=scipy.optimize.linear_sum_assignment(cost);assert len(set(cc))==2 and cost[rr,cc].sum()==1
# Seed and execution flags reconstructed directly, not through producer helper.
torch.manual_seed(17);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.deterministic=True;torch.backends.cudnn.benchmark=False;torch.use_deterministic_algorithms(True)
model=build(BASE);count=sum(x.numel() for x in model.parameters());h=hashlib.sha256()
for name in sorted(model.state_dict()):
 t=model.state_dict()[name];h.update(json.dumps([name,str(t.dtype),list(t.shape)],separators=(',',':')).encode()+bytes([10]));h.update(t.detach().contiguous().numpy().tobytes())
assert count==4847144 and h.hexdigest()=='304418a48ff7cc85b141de498cff1ec147ac500d7a28a9e47e044205c23f68b2'
assert set(producer['initial_tensor_sha256'].values())=={h.hexdigest()} and set(producer['parameters'].values())=={count}
assert any(isinstance(m,torch.nn.BatchNorm1d) for m in model.modules());assert any(isinstance(m,torch.nn.GroupNorm) and m.num_groups==8 for m in model.modules());assert not any(isinstance(m,torch.nn.BatchNorm2d) for m in model.modules())
out={'scope':'independent training-root CPU-only initial-state and solver verification; no CUDA driver regression, optimizer or admission','initial_sha256':h.hexdigest(),'parameters':count,'CUDA_devices':0,'producer_receipt_sha256':H('/tmp/producer/receipt.json'),'probe_sha256':H('/tmp/probe.py'),'checker_sha256':H('/tmp/checker.py'),'producer_sources_rehashed':r['source_hashes'],'rootfs_expected_sha256':r['runtime_lock']['rootfs_sha256']}
P('/outputs/check.json').write_text(json.dumps(out,indent=2));print('PASS independent CPU initial digest',h.hexdigest(),'parameters',count)
