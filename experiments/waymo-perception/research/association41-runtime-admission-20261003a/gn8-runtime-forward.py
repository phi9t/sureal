import fcntl,hashlib,json,subprocess,time
from pathlib import Path
from pipeline.runtime_identity import verify_rootfs
cache=Path.home()/'.cache/waystone/waymo-perception/insula';producer=cache/'association41-training-m0-20261003b'
r=json.loads((producer/'receipt.json').read_text());root=cache/'association41-training-20261003a';verify_rootfs(root,r['runtime_lock']['rootfs_sha256'])
package=Path('experiments/waymo-perception').resolve()
manifest=json.loads((cache/'association-runs/contract20261003b/manifest.pending.json').read_text());frame=manifest['frame_bindings'][7]
fixture=cache.parent/'scientific-processing/balanced16-native-v2'/frame['relative_directory']
for name,digest in frame['input_hashes'].items():
 if hashlib.sha256((fixture/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('fixture drift '+name)
out=cache/'association41-gn8-runtime-forward-20261003a';out.mkdir(exist_ok=False)
code='''import hashlib,json,resource,time
from pathlib import Path
import numpy as np,torch
from tier1.models import build,deterministic,objective
from tier1.catalog import BASE
assert torch.cuda.is_available() and torch.cuda.device_count()==1
assert torch.__version__=='2.9.1+cu130'
deterministic();model=build(BASE)
h=hashlib.sha256()
for name,t in sorted(model.state_dict().items()):
 h.update(json.dumps([name,str(t.dtype),list(t.shape)],separators=(',',':')).encode()+b'\\n');h.update(t.detach().cpu().contiguous().numpy().tobytes())
assert h.hexdigest()=='304418a48ff7cc85b141de498cff1ec147ac500d7a28a9e47e044205c23f68b2'
model.cuda().train();torch.cuda.reset_peak_memory_stats()
with np.load('/tmp/fixture/observations.npz',allow_pickle=False) as a:
 assert set(a.files)=={'points','counts','coordinates'}
 obs=[torch.from_numpy(a[k]).cuda() for k in ['points','counts','coordinates']]
with np.load('/tmp/fixture/targets.npz',allow_pickle=False) as a:
 truth=[torch.from_numpy(a[k]).cuda()[None] for k in ['labels','box_targets','direction_targets']]
parameters={n:p.detach().clone() for n,p in model.named_parameters()}
torch.cuda.synchronize();started=time.monotonic()
output=model(*obs,batch_size=1)
assert {k:list(v.shape) for k,v in output.items()}=={'classification':[1,524288,4],'box_residuals':[1,524288,7],'direction':[1,524288,2]}
loss=objective(output,truth,BASE);loss['total'].backward();torch.cuda.synchronize();seconds=time.monotonic()-started
assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
assert all(torch.equal(p.detach(),parameters[n]) for n,p in model.named_parameters())
np.savez_compressed('/outputs/heads.npz',**{k:v.detach().cpu().numpy()[0] for k,v in output.items()})
report={'scope':'one actual fixed-frame GN8/PFNBN forward/backward runtime regression only; legacy targets, NO optimizer/training-study update or fit/native result','initial_tensor_sha256':h.hexdigest(),'loss':{k:float(v.detach().cpu()) for k,v in loss.items()},'positive_anchors':int((truth[0]>0).sum()),'positive_anchors_per_class':{str(k):int((truth[0]==k).sum()) for k in range(1,5)},'all_gradients_finite':True,'parameters_unchanged':True,'optimizer_updates':0,'synchronized_forward_backward_seconds':seconds,'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_reserved_bytes':torch.cuda.max_memory_reserved(),'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'tf32':False,'deterministic':True,'recipe':BASE}
assert report['peak_allocated_bytes']<=8*1024**3 and report['peak_rss_kib']<=16*1024**2
Path('/outputs/check.json').write_text(json.dumps(report,indent=2)+'\\n');print('PASS actual-frame GN8 forward/backward; no optimizer execution')
'''
plan=r['command'][:r['command'].index('--')+1]+['/opt/waymo/bin/python','-c',code]
bind=plan.index('--bind');plan[bind+1]=str(out)
extra=['--ro-bind',str(fixture),'/tmp/fixture','--setenv','CUBLAS_WORKSPACE_CONFIG',':4096:8'];plan[plan.index('--'):plan.index('--')]=extra
source_hashes={str(package/n):h for n,h in manifest['baseline_source_hashes'].items()};source_hashes[str(Path(__file__).resolve())]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
for name,digest in r['driver_hashes'].items():
 if hashlib.sha256((Path('/usr/lib/x86_64-linux-gnu')/name).resolve().read_bytes()).hexdigest()!=digest:raise RuntimeError('driver drift')
with (cache/'architecture-experiments.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);started=time.monotonic();result=subprocess.run(plan,capture_output=True,text=True,timeout=180)
(out/'stdout').write_text(result.stdout);(out/'stderr').write_text(result.stderr)
for name,digest in source_hashes.items():
 if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise RuntimeError('source drift '+name)
receipt={'stage':'GN8 runtime forward/backward only','command':plan,'runtime_lock':r['runtime_lock'],'driver_hashes':r['driver_hashes'],'source_hashes':source_hashes,'fixed_frame':frame,'exit_code':result.returncode,'elapsed_seconds':time.monotonic()-started,'artifacts':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()},'admission_status':'pending independent verification'}
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(result.stdout,result.stderr,flush=True);raise SystemExit(result.returncode)
