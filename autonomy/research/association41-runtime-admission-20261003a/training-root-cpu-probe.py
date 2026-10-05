import hashlib,json,subprocess,time
from pathlib import Path
from pipeline.runtime_identity import verify_rootfs
from pipeline.insula_entry import launch_plan
cache=Path.home()/'.cache/waystone/waymo-perception/insula';root=cache/'association41-training-20261003a'
lock=json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,lock['rootfs_sha256'])
out=cache/'association41-training-cpu-probe-20261003a';out.mkdir(exist_ok=False)
experiment=Path('experiments/waymo-perception').resolve();source=Path('.scratch/association41-source').resolve()
code='''import hashlib,importlib.util,json,sys
from pathlib import Path
import numpy as np,scipy,torch
from scipy.optimize import linear_sum_assignment
from tier1.models import build,deterministic
from tier1.catalog import BASE
assert not torch.cuda.is_available() and torch.cuda.device_count()==0
assert torch.__version__=='2.9.1+cu130' and scipy.__version__=='1.18.1' and np.__version__=='2.5.3'
assert importlib.util.find_spec('tensorflow') is None
cost=np.array([[0.,1.],[0.,10.]],dtype=np.float64);r,c=linear_sum_assignment(cost)
assert c.tolist()==[1,0] and float(cost[r,c].sum())==1.
digests={};models={};counts={}
for treatment in ['A0','A1','A2','A3']:
 deterministic();model=build(BASE);h=hashlib.sha256()
 for name,t in sorted(model.state_dict().items()):
  a=t.detach().cpu().contiguous().numpy()
  h.update(json.dumps([name,str(t.dtype),list(t.shape)],separators=(',',':')).encode()+b'\\n');h.update(a.tobytes())
 digests[treatment]=h.hexdigest()
 counts[treatment]=sum(p.numel() for p in model.parameters())
 assert all(not p.is_cuda for p in model.parameters())
 assert any(isinstance(m,torch.nn.GroupNorm) and m.num_groups==8 for m in model.modules())
 assert any(isinstance(m,torch.nn.BatchNorm1d) for m in model.modules())
 del model
assert len(set(digests.values()))==1
Path('/outputs/check.json').write_text(json.dumps({'scope':'training-root CPU-only solver availability and seeded initial model fixture; no GPU, optimizer or runtime admission','torch':torch.__version__,'scipy':scipy.__version__,'numpy':np.__version__,'initial_tensor_sha256':digests,'parameters':counts,'recipe':BASE,'CUDA_visible_devices':0,'initial_hash_encoding':'sorted name,dtype,shape compact UTF8JSON + LF followed by contiguous NumPy native bytes'}))
print('PASS training-root CPU solver and identical four-case initial GN8/PFNBN tensors; no optimizer or GPU')
'''
plan=launch_plan(root,experiment,source,out,['/opt/waymo/bin/python','-c',code]);started=time.monotonic()
result=subprocess.run(plan,capture_output=True,text=True,timeout=120)
(out/'stdout').write_text(result.stdout);(out/'stderr').write_text(result.stderr)
receipt={'command':plan,'runtime_lock':lock,'exit_code':result.returncode,'elapsed_seconds':time.monotonic()-started,'source_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__).resolve(),experiment/'tier1/models.py',experiment/'tier1/catalog.py',experiment/'gpu/norm_variants.py',experiment/'gpu/architecture_variants.py',experiment/'gpu/architecture_followups.py',experiment/'pipeline/pillar_detector.py',experiment/'pipeline/detector_loss.py']},'artifacts':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()},'admission_status':'pending independent verification and CUDA/driver regression; CPU-only fixture'}
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(result.stdout,result.stderr,flush=True);raise SystemExit(result.returncode)
