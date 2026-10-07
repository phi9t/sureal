"""Synthetic optimizer-inclusive resource fixture; no dataset or quality claim."""
import importlib.util,json,time,resource
from pathlib import Path
import torch
from detection.pillar_detector import PillarDetector
from detection.detector_loss import detector_loss
assert importlib.util.find_spec('tensorflow') is None
assert torch.cuda.is_available() and torch.cuda.device_count()==1
torch.manual_seed(17);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
grid=512;pillars=20000;slots=32;anchors=8
model=PillarDetector(nx=grid,ny=grid,classes=4,anchors_per_cell=anchors,cell_size=(.25,.25),origin=(-64.,-64.)).cuda().train()
optimizer=torch.optim.Adam(model.parameters(),lr=1e-4,betas=(.9,.999),eps=1e-8,weight_decay=0,foreach=False)
cells=torch.randperm(grid*grid,device='cuda')[:pillars]
coords=torch.stack((torch.zeros_like(cells),torch.zeros_like(cells),cells//grid,cells%grid),dim=1)
points=torch.rand(pillars,slots,4,device='cuda');points[:,:,0]=(coords[:,3,None]+points[:,:,0])*.25-64;points[:,:,1]=(coords[:,2,None]+points[:,:,1])*.25-64;points[:,:,2]=points[:,:,2]*4-2
counts=torch.full((pillars,),slots,device='cuda',dtype=torch.int64)
n=anchors*(grid//2)**2;labels=torch.zeros((1,n),device='cuda',dtype=torch.int64)
for cls in range(1,5):labels[:,(cls-1)*10:cls*10]=cls
targets=torch.zeros((1,n,7),device='cuda');direction=torch.zeros_like(labels)
torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats();timings=[];losses=[];probe=None
for step in range(3):
 optimizer.zero_grad(set_to_none=True);torch.cuda.synchronize();start=time.monotonic()
 out=model(points,counts,coords,batch_size=1);assert out['classification'].shape==(1,n,4)
 result=detector_loss(out['classification'],out['box_residuals'],out['direction'],labels,targets,direction);assert torch.isfinite(result['total']);result['total'].backward()
 assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
 if step==0:
  parameter=model.class_head.bias;old=parameter.detach().clone();gradient=parameter.grad.detach().clone()
 optimizer.step()
 if step==0:
  expected=old-1e-4*gradient/(gradient.abs()+1e-8)
  torch.testing.assert_close(parameter.detach(),expected,rtol=1e-5,atol=2e-8);probe=True
 assert all(torch.isfinite(p).all() for p in model.parameters())
 torch.cuda.synchronize();timings.append(time.monotonic()-start);losses.append(result['total'].detach().item())
parameters=list(model.parameters());state=optimizer.state
assert len(state)==len(parameters)
state_bytes=0
for p in parameters:
 st=state[p];assert set(st)=={'step','exp_avg','exp_avg_sq'} and st['step'].item()==3
 assert st['exp_avg'].shape==p.shape and st['exp_avg_sq'].shape==p.shape
 assert torch.isfinite(st['exp_avg']).all() and torch.isfinite(st['exp_avg_sq']).all()
 state_bytes+=sum(v.numel()*v.element_size() for v in st.values())
expected_bytes=sum(2*p.numel()*p.element_size()+4 for p in parameters);assert state_bytes==expected_bytes
report={'seed':17,'device':torch.cuda.get_device_name(0),'torch':torch.__version__,'grid':[grid,grid],'pillars':pillars,'points_per_pillar':slots,'classes':4,'anchors_per_cell':anchors,'parameters':sum(p.numel() for p in parameters),'parameter_tensors':len(parameters),'synthetic_optimizer_steps':3,'optimizer':'Adam lr1e-4 betas(.9,.999) eps1e-8 weight_decay0 foreachFalse','optimizer_state_bytes':state_bytes,'first_update_analytic_check':probe,'step_seconds':timings,'synthetic_losses':losses,'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_reserved_bytes':torch.cuda.max_memory_reserved(),'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'tf32':False,'scope':'synthetic resource fixture only; no native I/O, assignment, dataset training, scientific budget or quality acceptance'}
Path('/outputs/check.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS synthetic optimizer-inclusive resource fixture',report['peak_allocated_bytes'],timings)
