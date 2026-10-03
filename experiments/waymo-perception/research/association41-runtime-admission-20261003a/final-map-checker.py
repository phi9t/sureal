import pathlib,json,hashlib
P=pathlib.Path
H=lambda p:hashlib.sha256(P(p).read_bytes()).hexdigest()
J=lambda x:hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=True,separators=(',',':')).encode()).hexdigest()
assert H('/tmp/pending.json')=='e720070f80206aaa5a3fc2fe186021ab7bb161ec28bf5bc0f6a34642c3ec1e1a'
m=json.loads(P('/tmp/pending.json').read_text());b=json.loads(P('/tmp/baseline.json').read_text());r=json.loads(P('/tmp/recon.json').read_text())
assert H('/tmp/baseline.json')==m['baseline_manifest']['sha256']
assert m['frame_bindings']==r['frames']
checks={}
for name,pin in m['baseline_source_hashes'].items():
 assert name.startswith(('tier1/','pipeline/','gpu/'))
 expected=pin['expected'] if isinstance(pin,dict) else pin
 actual=H('/experiment/'+name);assert actual==expected==b['source_hashes'][name],name;checks[name]=actual
for name in ['gpu/norm_variants.py','gpu/architecture_variants.py','gpu/architecture_followups.py','gpu/scored_proposals_v3.py']:assert name in checks
for key,ids in [('eligible_gt_sha256','eligible_ids'),('native_gt_sha256','native_ids')]:
 pre=[{'identity':f['identity'],'ids':sorted(f[ids]),'boxes_sha256':f['boxes_sha256']} for f in m['frame_bindings']]
 assert J(pre)==m['inputs'][key],key
assert J(m['frame_bindings'])==m['inputs']['frames_sha256']
assert J(m['frame_bindings'][7])==m['inputs']['fixed_frame_sha256']
assert J(m['baseline_source_hashes'])==m['inputs']['baseline_sources_sha256']
assert m['budgets']['fixed_primary_updates']==2000
assert m['loss']=={'focal_alpha':.25,'focal_gamma':2.,'smooth_l1_beta':1/9,'direction':'canonical_legacy','localization_weight':2.,'direction_weight':.2,'normalizer':'positive_count'}
for name,pin in m['association_source_hashes'].items():assert H('/experiment/association/'+name)==pin
for key,pre in m['input_hash_preimages'].items():assert J(pre)==m['inputs'][key]
from association.contract import validate_contract
import copy
rr=copy.deepcopy(m['runtime_locks']);rr['cpu']['admission_sha256']='1'*64;cc=copy.deepcopy(m);cc['runtime_locks']=rr
try:validate_contract(cc,inputs=m['inputs'],runtime_locks=rr)
except ValueError as e:assert 'training admission' in str(e)
else:raise AssertionError('GPU pending accepted')
try:validate_contract(m,inputs=m['inputs'],runtime_locks=m['runtime_locks'])
except ValueError as e:rejection=str(e)
else:raise AssertionError('pending admitted')
assert 'admission' in rejection
out={'manifest_sha256':H('/tmp/pending.json'),'checker_sha256':H('/tmp/checker.py'),'verified_source_hashes':checks,'contract_sha256':H('/experiment/association/contract.py'),'test_contract_sha256':H('/experiment/association/test_contract.py'),'pending_rejected':rejection,'all_five_input_hash_preimages_verified':True,'scope':'required tier1/pipeline/gpu only; historical cohort drift retained outside this source-map; native scoring requires later admission'}
P('/outputs/check.json').write_text(json.dumps(out,indent=2));print('PASS required map and all5 digestpreimages',len(checks),'sources; pending rejected:',rejection)
