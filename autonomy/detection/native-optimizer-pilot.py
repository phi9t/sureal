"""Fixed native-training-cache optimizer pilot; not an overfit acceptance run."""
import importlib.util, json, resource, time
from pathlib import Path
import numpy as np
import torch
from detection.pillar_detector import PillarDetector
from detection.detector_loss import detector_loss
from evidence.source_snapshot import file_sha256 as sha

assert importlib.util.find_spec('tensorflow') is None
assert torch.cuda.is_available() and torch.cuda.device_count() == 1
manifest=json.loads(Path('/tmp/inputs/manifest.json').read_text())
torch.manual_seed(17)
torch.backends.cuda.matmul.allow_tf32=False
torch.backends.cudnn.allow_tf32=False
model=PillarDetector(nx=512,ny=512,classes=4,anchors_per_cell=8,cell_size=(.25,.25),origin=(-64.,-64.)).cuda().train()
optimizer=torch.optim.Adam(model.parameters(),lr=1e-4,betas=(.9,.999),eps=1e-8,weight_decay=0,foreach=False)
torch.cuda.reset_peak_memory_stats()
start=time.monotonic(); records=[]
for frame in manifest['frames']:
    directory=Path('/tmp/native')/frame['relative_directory']
    for name,digest in frame['sha256'].items():
        assert sha(directory/name)==digest
    t=time.monotonic()
    with np.load(directory/'observations.npz',allow_pickle=False) as data:
        assert set(data.files)=={'points','counts','coordinates'}
        points=torch.from_numpy(data['points'].astype(np.float32)).cuda()
        counts=torch.from_numpy(data['counts']).cuda()
        coordinates=torch.from_numpy(data['coordinates']).cuda()
    with np.load(directory/'targets.npz',allow_pickle=False) as data:
        labels=torch.from_numpy(data['labels']).cuda()[None]
        boxes=torch.from_numpy(data['box_targets'].astype(np.float32)).cuda()[None]
        directions=torch.from_numpy(data['direction_targets']).cuda()[None]
    optimizer.zero_grad(set_to_none=True)
    output=model(points,counts,coordinates,batch_size=1)
    assert output['classification'].shape==(1,524288,4)
    loss=detector_loss(output['classification'],output['box_residuals'],output['direction'],labels,boxes,directions)
    loss['total'].backward()
    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
    norm=torch.nn.utils.clip_grad_norm_(model.parameters(),10,error_if_nonfinite=True)
    before=model.class_head.bias.detach().clone()
    optimizer.step()
    assert not torch.equal(before,model.class_head.bias)
    assert all(torch.isfinite(p).all() for p in model.parameters())
    torch.cuda.synchronize()
    records.append({'identity':frame['identity'],'loss':{k:v.detach().item() for k,v in loss.items()},'gradient_norm_before_clip':norm.item(),'positive_anchors':int((labels>0).sum()),'io_and_step_seconds':time.monotonic()-t})
checkpoint=Path('/outputs/checkpoint.pt')
torch.save({'model':model.state_dict(),'optimizer':optimizer.state_dict(),'steps':len(records),'manifest_sha256':sha(Path('/tmp/inputs/manifest.json')),'torch_rng':torch.get_rng_state(),'cuda_rng':torch.cuda.get_rng_state()},checkpoint)
restored=torch.load(checkpoint,weights_only=True,map_location='cpu')
clone=PillarDetector(nx=512,ny=512,classes=4,anchors_per_cell=8,cell_size=(.25,.25),origin=(-64.,-64.)).cuda()
clone.load_state_dict(restored['model']);model.eval();clone.eval()
with torch.no_grad():
    expected=model(points,counts,coordinates,batch_size=1)
    actual=clone(points,counts,coordinates,batch_size=1)
    for key in expected: torch.testing.assert_close(actual[key],expected[key],rtol=0,atol=0)
clone_optimizer=torch.optim.Adam(clone.parameters(),lr=1e-4,betas=(.9,.999),eps=1e-8,weight_decay=0,foreach=False)
clone_optimizer.load_state_dict(restored['optimizer'])
state_bytes=0
for left,right in zip(optimizer.state.values(),clone_optimizer.state.values()):
    assert left.keys()==right.keys()
    for key in left:
        torch.testing.assert_close(left[key],right[key],rtol=0,atol=0)
        assert torch.isfinite(right[key]).all()
        state_bytes+=left[key].numel()*left[key].element_size()
    assert left['step'].item()==16
report={'scope':'16 native training-frame diagnostic optimizer updates; no overfit score, export acceptance, heldout result or main-study budget estimate','steps':records,'native_optimizer_updates':len(records),'checkpoint_exact_output_and_optimizer_roundtrip':True,'checkpoint_sha256':sha(checkpoint),'checkpoint_bytes':checkpoint.stat().st_size,'optimizer_state_bytes':state_bytes,'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_reserved_bytes':torch.cuda.max_memory_reserved(),'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'elapsed_seconds':time.monotonic()-start,'torch':torch.__version__,'device':torch.cuda.get_device_name(0),'seed':17,'tf32':False,'gradient_clip':10}
assert report['peak_allocated_bytes']<=8*1024**3
assert report['peak_rss_kib']<=16*1024**2
Path('/outputs/check.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS native optimizer pilot; exact checkpoint restoration; 16 diagnostic updates',flush=True)
