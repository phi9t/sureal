import json,pathlib,hashlib,collections,itertools,socket,sys,copy
import numpy as np,scipy, scipy.optimize,pyarrow.parquet as pq
from PIL import Image
from association.contract import validate_contract,prediction_alpha
from association.test_contract import fixture
P=pathlib.Path
H=lambda p:hashlib.sha256(P(p).read_bytes()).hexdigest()
def mapped(p):
 s=str(p); marker='/scientific-processing/'
 return P('/tmp/scientific')/s.split(marker,1)[1]
assert not P('/data02').exists()
assert sys.executable=='/usr/local/bin/python'
assert scipy.__version__=='1.18.1' and np.__version__=='2.5.3'
assert str(scipy.__file__).startswith('/usr/local/lib/')
for q in ['/experiment/association/contract.py','/tmp/baseline.json','/tmp/producer/matrix.npy','/usr/local/bin/python']:
 try:P(q).open('ab').close()
 except OSError:pass
 else:raise AssertionError('writable:'+q)
try:
 socket.create_connection(('127.0.0.1',int(sys.argv[1])),timeout=.5)
except OSError:pass
else:raise AssertionError('network reachable')
assert np.load('/tmp/producer/matrix.npy').tolist()==[14,38,62]
assert pq.read_table('/tmp/producer/synthetic.parquet').to_pydict()=={'id':[7,11,19],'value':[.25,.5,.75]}
with Image.open('/tmp/producer/synthetic.png') as im:
 assert im.size==(3,2) and list(im.getdata())==[(17,29,43)]*6
r=json.loads(P('/tmp/producer/receipt.json').read_text());assert r['exit_code']==0
for name,h in r['artifacts'].items():assert H('/tmp/producer/'+name)==h
recon=json.loads(P('/tmp/audit/input-rehash.json').read_text());assert H('/tmp/baseline.json')==recon['manifest_sha256']; counts=collections.Counter();native=0;bindings=[]
for f in recon['frames']:
 ctx,ts=f['identity'].split(':');q=mapped(f['boxes_path']);assert H(q)==f['boxes_sha256'];rows=[r for fr in json.loads(q.read_text())['frames'] for r in fr['rows'] if str(r['frame_timestamp_micros'])==ts];eligible=[r for r in rows if r['num_lidar_points_in_box']>0 and -64<=r['box'][0]<64 and -64<=r['box'][1]<64 and -4<=r['box'][2]<6]
 assert sorted(r['object_id'] for r in rows)==f['native_ids'];assert sorted(r['object_id'] for r in eligible)==f['eligible_ids'];counts.update(r['type'] for r in eligible);native+=len(rows)
for x in recon['native_input_byte_checks']+recon['physical_byte_checks']:
 q=mapped(x['path']);assert H(q)==x['expected'];bindings.append({'path':str(q),'sha256':H(q)})
assert native==1279 and dict(counts)=={1:533,2:255,3:231,4:34};assert recon['frames'][7]['eligible']==73
for name,x in recon['source_rehash'].items():assert H(P('/experiment')/name)==x['expected']
variants=[]
def reject(name,c,i,r):
 try:validate_contract(c,inputs=i,runtime_locks=r)
 except ValueError:variants.append(name)
 else:raise AssertionError('accepted '+name)
c,i,r=fixture();validate_contract(c,inputs=i,runtime_locks=r)
for sec,key,val in [('schema_version',None,True),('model','seed',True),('optimizer','lr',float('nan')),('budgets','step_seconds',7201),('inputs','frames_sha256','f'*64)]:
 cc=copy.deepcopy(c)
 if key is None:cc[sec]=val
 else:cc[sec][key]=val
 reject(str((sec,key)),cc,i,r)
for role in ['cpu','training']:
 rr=copy.deepcopy(r);del rr[role];cc=copy.deepcopy(c);cc['runtime_locks']=rr;reject('missing '+role,cc,i,rr)
rr=copy.deepcopy(r);rr['training']['scipy_version']='1.18.0';cc=copy.deepcopy(c);cc['runtime_locks']=rr;reject('version drift',cc,i,rr)
for n in [-1,True,1.2,float('inf')]:
 try:prediction_alpha(n)
 except ValueError:pass
 else:raise AssertionError('alpha invalid')
assert [prediction_alpha(n) for n in [64,160,256]]==[0,.5,1]
lap=[]
for mat in [[[4,1,3],[0,2,5]],[[0,0,1],[0,0,1]],[[1,7,3],[2,4,0]],[[0,float('inf'),3],[float('inf'),1,2]]]:
 a=np.asarray(mat,dtype=np.float64);rows,cols=scipy.optimize.linear_sum_assignment(a);obj=float(a[rows,cols].sum());best=min(sum(a[x,perm[x]] for x in range(a.shape[0])) for perm in itertools.permutations(range(a.shape[1]),a.shape[0]));assert obj==best and len(set(cols))==len(rows);lap.append(obj)
try:scipy.optimize.linear_sum_assignment(np.array([[np.inf,np.inf],[0,1]]))
except ValueError:variants.append('infeasible LAP')
else:raise AssertionError('infeasible accepted')
out={'status':'CPU independent checks pass; overall Task41.1 pending GPU and concrete study manifest','eligible':sum(counts.values()),'native':native,'classes':dict(counts),'fixed_eligible':73,'producer_receipt_sha256':H('/tmp/producer/receipt.json'),'checker_sha256':H('/tmp/audit/checker.py'),'input_bindings':bindings,'negative_variants':variants,'lap_exhaustive_objectives':lap,'live_source_hashes':{n:H('/experiment/'+n) for n in ['association/contract.py','association/test_contract.py']},'scipy':scipy.__version__,'numpy':np.__version__}
P('/outputs/check.json').write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if k!='input_bindings'}))
