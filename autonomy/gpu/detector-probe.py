"""Synthetic full-model GPU/resource pilot; no optimization or quality claim."""
import importlib.util
import json
import time
from pathlib import Path
import torch
from detection.pillar_detector import PillarDetector
from detection.detector_loss import detector_loss


def main():
    assert importlib.util.find_spec('tensorflow') is None
    assert torch.cuda.is_available() and torch.cuda.device_count()==1
    torch.manual_seed(17)
    torch.backends.cuda.matmul.allow_tf32=False
    torch.backends.cudnn.allow_tf32=False
    torch.cuda.reset_peak_memory_stats()
    grid=512;pillars=20000;slots=32
    model=PillarDetector(nx=grid,ny=grid,classes=4,anchors_per_cell=2,
                         cell_size=(.25,.25),origin=(-64.,-64.)).cuda().train()
    cells=torch.randperm(grid*grid,device='cuda')[:pillars]
    coordinates=torch.stack((torch.zeros_like(cells),torch.zeros_like(cells),cells//grid,cells%grid),dim=1)
    points=torch.rand(pillars,slots,4,device='cuda')
    points[:,:,0]=(coordinates[:,3,None]+points[:,:,0])*.25-64
    points[:,:,1]=(coordinates[:,2,None]+points[:,:,1])*.25-64
    points[:,:,2]=points[:,:,2]*4-2
    counts=torch.full((pillars,),slots,device='cuda',dtype=torch.int64)
    times=[];losses=[]
    for _ in range(3):
        model.zero_grad(set_to_none=True)
        torch.cuda.synchronize();started=time.monotonic()
        output=model(points,counts,coordinates,batch_size=1)
        expected=2*(grid//2)**2
        assert output['classification'].shape==(1,expected,4)
        labels=torch.zeros(1,expected,dtype=torch.int64,device='cuda');labels[:,:10]=1
        result=detector_loss(output['classification'],output['box_residuals'],output['direction'],labels,
                             torch.zeros_like(output['box_residuals']),torch.zeros_like(labels))
        assert torch.isfinite(result['total'])
        result['total'].backward()
        assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
        torch.cuda.synchronize();times.append(time.monotonic()-started);losses.append(float(result['total'].detach()))
    report={'status':'synthetic integrated GPU detector/loss pilot passed',
            'seed':17,'device':torch.cuda.get_device_name(0),'torch':torch.__version__,
            'grid':[grid,grid],'batch_size':1,'pillars':pillars,'points_per_pillar':slots,
            'physical_channels':['x','y','z','intensity'],'classes':4,'anchors_per_cell':2,
            'parameter_count':sum(p.numel() for p in model.parameters()),
            'forward_backward_seconds':times,'synthetic_losses':losses,
            'peak_allocated_bytes':torch.cuda.max_memory_allocated(),
            'peak_reserved_bytes':torch.cuda.max_memory_reserved(),
            'optimizer_steps':0,'tf32':False,
            'assertions':['single visible GPU','TensorFlow absent','stride-two anchor count',
                          'finite integrated loss','finite gradients for all parameters'],
            'scope':'synthetic model resource pilot only; native packing/I/O/optimizer cost, scientific budget, training and held-out quality unverified'}
    Path('/outputs/detector-probe.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS full detector GPU resource pilot',report['peak_allocated_bytes'],times)


if __name__=='__main__':main()
