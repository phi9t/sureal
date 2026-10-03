"""Analytic PFN padded-slot BN contract and CPU/GPU numerical parity."""
import copy
import importlib.util
import json
import time
from pathlib import Path
import numpy as np
import torch
from pipeline.pillar_encoder import PillarFeatureNet, decorate, scatter


def main():
    assert importlib.util.find_spec('tensorflow') is None
    assert torch.cuda.is_available() and torch.cuda.device_count() == 1
    torch.manual_seed(17)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.cuda.reset_peak_memory_stats()
    started = time.monotonic()
    # Independent numpy moments: source BN includes both valid and padded slots.
    model = PillarFeatureNet().double().train()
    with torch.no_grad():
        model.linear.weight.zero_()
        model.linear.weight[:,0] = 1
    values = torch.zeros(2,3,9,dtype=torch.float64)
    values[:,:,0] = torch.tensor([[2.,4.,0.],[6.,0.,0.]],dtype=torch.float64)
    native = model(values).detach().numpy()
    a = np.array([[2.,4.,0.],[6.,0.,0.]])
    mean = a.mean()
    variance = a.var()
    expected = np.maximum((a-mean)/np.sqrt(variance+1e-3),0).max(axis=1)
    np.testing.assert_allclose(native,np.repeat(expected[:,None],64,axis=1),rtol=1e-12,atol=1e-12)
    np.testing.assert_allclose(model.norm.running_mean.detach().numpy(),np.full(64,.01*mean),rtol=1e-12)
    np.testing.assert_allclose(model.norm.running_var.detach().numpy(),np.full(64,.99+.01*a.var(ddof=1)),rtol=1e-12)
    # Eval padding is not masked after BN/ReLU; padded zeros may win the max.
    with torch.no_grad():
        model.norm.running_mean.zero_()
        model.norm.running_var.fill_(1)
        model.norm.bias.fill_(3)
    model.eval()
    padded = torch.zeros(1,2,9,dtype=torch.float64)
    padded[0,0,0] = -2
    np.testing.assert_allclose(model(padded).detach().numpy(),np.full((1,64),3.))

    points = torch.tensor([[[1.,2.,3.,4.],[3.,4.,5.,6.],[99.,99.,99.,99.]],
                           [[-1.,2.,0.,.5],[0.,0.,0.,0.],[0.,0.,0.,0.]]],dtype=torch.float64)
    counts = torch.tensor([2,1])
    coordinates = torch.tensor([[0,0,1,2],[1,0,0,1]])
    decorated = decorate(points,counts,coordinates,cell_size=(2.,2.),origin=(-4.,0.))
    cpu = PillarFeatureNet().double().eval()
    gpu = copy.deepcopy(cpu).cuda()
    x = decorated.detach().requires_grad_()
    y = decorated.cuda().detach().requires_grad_()
    cpu_output = scatter(cpu(x),coordinates,batch_size=2,nx=3,ny=2)
    gpu_output = scatter(gpu(y),coordinates.cuda(),batch_size=2,nx=3,ny=2)
    cpu_output.square().sum().backward()
    gpu_output.square().sum().backward()
    torch.cuda.synchronize()
    torch.testing.assert_close(gpu_output.cpu(),cpu_output,rtol=1e-9,atol=1e-10)
    torch.testing.assert_close(y.grad.cpu(),x.grad,rtol=1e-9,atol=1e-10)
    for c,g in zip(cpu.parameters(),gpu.parameters()):
        assert c.grad is not None and g.grad is not None
        torch.testing.assert_close(g.grad.cpu(),c.grad,rtol=1e-9,atol=1e-10)
    report = {'status':'analytic PFN BN and CPU/GPU parity passed',
              'assertions':['numpy padded-slot BN output','numpy running mean and unbiased running variance',
                            'padding retained after BN/ReLU','CPU/GPU scatter outputs',
                            'CPU/GPU input and parameter gradients','TensorFlow absent','one visible GPU'],
              'device':torch.cuda.get_device_name(0),'seed':17,
              'elapsed_seconds':time.monotonic()-started,
              'peak_allocated_bytes':torch.cuda.max_memory_allocated(),
              'max_output_error':float((gpu_output.cpu()-cpu_output).abs().max()),
              'max_input_gradient_error':float((y.grad.cpu()-x.grad).abs().max()),
              'scope':'analytic encoder only; no resource budget extrapolation, training, detector or held-out claim'}
    Path('/outputs/pillar-probe.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS PFN padded BN and CPU/GPU parity')


if __name__=='__main__':
    main()
