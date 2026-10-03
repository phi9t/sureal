import pathlib,json,hashlib,copy
import numpy as np
P=pathlib.Path;H=lambda p:hashlib.sha256(P(p).read_bytes()).hexdigest()
r=json.loads(P('/tmp/producer/receipt.json').read_text());report=json.loads(P('/tmp/producer/check.json').read_text());assert r['exit_code']==0
for n,h in r['artifacts'].items():assert H('/tmp/producer/'+n)==h
for n,h in r['source_hashes'].items():
 q='/tmp/probe.py' if n.endswith('/gn8-runtime-forward-b.py') else '/experiment/'+n.split('/experiments/waymo-perception/',1)[1]
 assert H(q)==h
for n,h in r['fixed_frame']['input_hashes'].items():assert H('/tmp/fixture/'+n)==h
with np.load('/tmp/producer/heads.npz',allow_pickle=False) as x:heads={k:x[k].astype(np.float64) for k in x.files}
with np.load('/tmp/fixture/targets.npz',allow_pickle=False) as x:labels=x['labels'];box=x['box_targets'].astype(np.float32).astype(np.float64);direction=x['direction_targets']
assert heads['classification'].shape==(524288,4) and heads['box_residuals'].shape==(524288,7) and heads['direction'].shape==(524288,2)
assert all(np.isfinite(a).all() for a in heads.values());pos=labels>0;den=max(int(pos.sum()),1);assert den==390
assert {str(i):int((labels==i).sum()) for i in range(1,5)}==report['positive_anchors_per_class']
def losses(head):
 l=head['classification'];y=(labels[:,None]==np.arange(1,5)[None,:]);p=np.exp(-np.logaddexp(0,-l));pt=np.where(y,p,1-p);alpha=np.where(y,.25,.75);bce=np.logaddexp(0,l)-y*l;classification=float((alpha*(1-pt)**2*bce*(labels>=0)[:,None]).sum()/den)
 diff=head['box_residuals']-box;diff[:,6]=np.sin(diff[:,6]);a=np.abs(diff);smooth=np.where(a<1/9,4.5*diff**2,a-1/18);localization=float(smooth[pos].sum()/den)
 dl=head['direction'];ce=np.logaddexp(dl[:,0],dl[:,1])-dl[np.arange(len(labels)),direction];dr=float(ce[pos].sum()/den)
 return {'classification':classification,'localization':localization,'direction':dr,'total':classification+2*localization+.2*dr}
computed=losses(heads)
for k,v in computed.items():assert np.isclose(v,report['loss'][k],rtol=2e-6,atol=2e-6),(k,v,report['loss'][k])
mut=copy.deepcopy(heads);mut['box_residuals'][np.flatnonzero(pos)[0],0]+=100;assert not np.isclose(losses(mut)['total'],report['loss']['total'],rtol=2e-6)
assert report['initial_tensor_sha256']=='304418a48ff7cc85b141de498cff1ec147ac500d7a28a9e47e044205c23f68b2' and report['optimizer_updates']==0 and report['tf32'] is False and report['deterministic'] is True
assert report['peak_allocated_bytes']<8*1024**3 and report['peak_reserved_bytes']<8*1024**3 and report['peak_rss_kib']<16*1024**2
out={'scope':'independent CPU literal loss/head/input audit; producer gradient/parameter assertions reviewed but no exported gradients or parameter snapshots to independently reconstruct','producer_receipt_sha256':H('/tmp/producer/receipt.json'),'checker_sha256':H('/tmp/checker.py'),'computed_float64_losses':computed,'producer_fp32_losses':report['loss'],'loss_rtol':2e-6,'tampered_box_loss_rejected':True,'heads_sha256':H('/tmp/producer/heads.npz'),'positive_anchors':den,'resource_report':{k:report[k] for k in ['peak_allocated_bytes','peak_reserved_bytes','peak_rss_kib']}}
P('/outputs/check.json').write_text(json.dumps(out,indent=2));print('PASS literal loss/head/input audit',computed)
