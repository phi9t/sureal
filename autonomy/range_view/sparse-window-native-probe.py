"""Untrained native pillar→masked attention→BEV integration; no optimizer."""
import importlib.util,json,time
from pathlib import Path
import numpy as np
import torch
from detection.pillar_encoder import PillarFeatureNet,decorate,scatter
from evidence.source_snapshot import file_sha256
from range_view.sparse_window_attention import SparseWindowAttention
from range_view.sparse_windows import partition_sparse_windows

trusted=json.loads(Path('/mnt/trusted.json').read_text());source=Path('/source/output/packed.npz')
assert file_sha256(source)==trusted['packed_sha256']
assert importlib.util.find_spec('tensorflow') is None
assert torch.cuda.is_available() and torch.cuda.device_count()==1
torch.manual_seed(17);torch.backends.cuda.matmul.allow_tf32=False
with np.load(source,allow_pickle=False) as data:
 points=torch.from_numpy(data['points']).float().cuda()
 counts=torch.from_numpy(data['counts']).cuda()
 coordinates=torch.from_numpy(data['coordinates']).cuda()
 native_coords=data['coordinates'][:,[0,2,3]].copy()
 source_indices=data['source_indices'].copy()
assert np.count_nonzero(source_indices>=0)==int(counts.sum())
grouping=partition_sparse_windows(native_coords,window_shape=(8,8),shift=(4,4))
ids=np.concatenate([b['token_indices'][b['valid_mask']] for b in grouping['buckets'].values()])
np.testing.assert_array_equal(np.sort(ids),np.arange(len(native_coords)))
pfn=PillarFeatureNet().cuda().train()
attention=SparseWindowAttention(64,4,window_shape=(8,8),shift=(4,4)).cuda().train()
torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();started=time.monotonic()
tokens=pfn(decorate(points,counts,coordinates,cell_size=(.25,.25),origin=(-64.,-64.)))
updated=attention(tokens,native_coords)
canvas=scatter(updated,coordinates,batch_size=1,nx=512,ny=512)
assert torch.isfinite(canvas).all()
torch.testing.assert_close(canvas[coordinates[:,0],:,coordinates[:,2],coordinates[:,3]],updated)
canvas.square().mean().backward()
assert all(p.grad is not None and torch.isfinite(p.grad).all() for module in [pfn,attention] for p in module.parameters())
torch.cuda.synchronize()
report={'status':'native untrained PFN attention BEV forward/backward passed',
        'packed_sha256':trusted['packed_sha256'],'pillars':len(native_coords),'retained_points':int(counts.sum()),
        'windows':grouping['windows'],'window_shape':[8,8],'shift':[4,4],
        'padded_slots':sum(b['token_indices'].size for b in grouping['buckets'].values()),
        'channels':64,'heads':4,'seed':17,'optimizer_steps':0,
        'forward_backward_seconds':time.monotonic()-started,'peak_allocated_bytes':torch.cuda.max_memory_allocated(),
        'device':torch.cuda.get_device_name(0),'scope':'engineering frame only; attention operator has no positional/residual/multiscale/diffusion blocks or trained detection claims'}
Path('/outputs/check.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS native sparse attention integration',report)
