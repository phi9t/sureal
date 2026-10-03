"""Analytic GPU runtime verifier; this is not model-quality evidence."""
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import time
import torch


def main():
    assert importlib.util.find_spec('tensorflow') is None
    assert torch.cuda.is_available(), 'GPU computation required'
    assert torch.cuda.device_count()==1, 'expose one selected device'
    torch.cuda.reset_peak_memory_stats()
    started=time.monotonic()
    x=torch.tensor([[1.,2.],[3.,4.]],device='cuda',dtype=torch.float64,requires_grad=True)
    weights=torch.tensor([[2.,0.],[0.,3.]],device='cuda',dtype=torch.float64,requires_grad=True)
    y=x@weights
    # Independent analytic values and derivatives of sum((x @ weights)^2).
    assert torch.equal(y.detach().cpu(),torch.tensor([[2.,6.],[6.,12.]],dtype=torch.float64))
    y.square().sum().backward()
    assert torch.equal(x.grad.cpu(),torch.tensor([[8.,36.],[24.,72.]],dtype=torch.float64))
    assert torch.equal(weights.grad.cpu(),torch.tensor([[40.,84.],[56.,120.]],dtype=torch.float64))
    conv=torch.nn.Conv2d(3,8,3,padding=1).cuda()
    image=torch.ones((2,3,64,64),device='cuda')
    output=conv(image);output.square().mean().backward()
    assert output.shape==(2,8,64,64) and torch.isfinite(output).all()
    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in conv.parameters())
    torch.cuda.synchronize()
    report={'device':torch.cuda.get_device_name(0),'capability':list(torch.cuda.get_device_capability(0)),
            'torch':torch.__version__,'cuda':torch.version.cuda,'elapsed_seconds':time.monotonic()-started,
            'peak_allocated_bytes':torch.cuda.max_memory_allocated(),
            'assertions':['analytic float64 matrix result','analytic input/weight gradients','convolution forward/backward finite','single visible CUDA device','TensorFlow absent'],
            'packages':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()},
            'checkpoint':'none: analytic runtime fixtures',
            'analytic':{'x':x.detach().cpu().tolist(),'weights':weights.detach().cpu().tolist(),
                        'y':y.detach().cpu().tolist(),'input_gradient':x.grad.cpu().tolist(),
                        'weight_gradient':weights.grad.cpu().tolist()}}
    Path('/outputs/gpu-probe.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS GPU analytic and convolution fixtures')

if __name__=='__main__':main()
