"""Trusted engineering frame to GPU model; diagnostic targets, no optimizer."""
import hashlib
import importlib.util
import json
import time
from pathlib import Path
import numpy as np
import torch
from detection.pillar_detector import PillarDetector
from detection.detector_loss import detector_loss


def main():
    trusted=json.loads(Path('/mnt/trusted.json').read_text())
    payload=Path('/source/output/packed.npz')
    assert hashlib.sha256(payload.read_bytes()).hexdigest()==trusted['packed_sha256']
    assert importlib.util.find_spec('tensorflow') is None
    assert torch.cuda.is_available() and torch.cuda.device_count()==1
    torch.manual_seed(17)
    torch.backends.cuda.matmul.allow_tf32=False
    torch.backends.cudnn.allow_tf32=False
    torch.cuda.reset_peak_memory_stats()
    started=time.monotonic()
    with np.load(payload,allow_pickle=False) as native:
        # Model observations explicitly cast float64 physical measurements to FP32.
        points=torch.from_numpy(native['points']).float().cuda()
        counts=torch.from_numpy(native['counts']).cuda()
        coordinates=torch.from_numpy(native['coordinates']).cuda()
        retained=int(counts.sum())
    model=PillarDetector(nx=512,ny=512,classes=4,anchors_per_cell=2,
                         cell_size=(.25,.25),origin=(-64.,-64.)).cuda().train()
    torch.cuda.synchronize();forward_start=time.monotonic()
    output=model(points,counts,coordinates,batch_size=1)
    labels=torch.zeros(1,131072,dtype=torch.int64,device='cuda')
    # All-background is an analytic gradient fixture, not native supervision.
    loss=detector_loss(output['classification'],output['box_residuals'],output['direction'],labels,
                       torch.zeros_like(output['box_residuals']),torch.zeros_like(labels))
    assert torch.isfinite(loss['total'])
    loss['total'].backward()
    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
    torch.cuda.synchronize()
    report={'status':'trusted native engineering points to full GPU detector passed',
            'packed_sha256':trusted['packed_sha256'],'input_cast':'physical float64 to model float32',
            'pillars':len(counts),'retained_points':retained,'grid':[512,512],
            'anchor_predictions':output['classification'].shape[1],
            'forward_backward_seconds':time.monotonic()-forward_start,
            'total_seconds':time.monotonic()-started,'peak_allocated_bytes':torch.cuda.max_memory_allocated(),
            'device':torch.cuda.get_device_name(0),'optimizer_steps':0,
            'target_status':'synthetic all-background diagnostic only; native box targets not loaded',
            'scope':'native observation/model integration only; no trained predictions, overfit or held-out accuracy'}
    Path('/outputs/check.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS native GPU model integration',report)


if __name__=='__main__':main()
