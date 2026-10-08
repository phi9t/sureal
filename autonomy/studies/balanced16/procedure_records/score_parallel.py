"""Native pooled cohort metrics plus separate literal proposals/export audits."""
import argparse,hashlib,json,subprocess,sys,time
from pathlib import Path
PACKAGE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(PACKAGE))
from insula.entry import launch_plan
from insula.runtime_identity import verify_rootfs
from balanced import uncovered_count
from protocol import quality_gate
from admissions import required_fit_admissions
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
parser=argparse.ArgumentParser();parser.add_argument('variant',choices=['baseline','residual_bev']);parser.add_argument('--run-id',required=True);a=parser.parse_args();cache=Path.home()/'.cache/waystone/waymo-perception';run=cache/'insula'/f'cohort16-{a.variant}-{a.run_id}';meta=json.loads((run/'run.json').read_text());source=run/'source';package=source/'autonomy';output=cache/'scientific-processing'/f'cohort16-{a.variant}-{a.run_id}';training=json.loads((run/'train-verified.json').read_text());manifest=meta['manifest'];inputs=run/'inputs';workers=run/'scoring-workers-parallel-v3';workers.mkdir();
for filename in ['prepare_v2.py','metrics.py','audit_proposals.py','audit_metrics.py','balanced.py']:(workers/filename).write_bytes((PACKAGE/'cohort'/filename).read_bytes())
pins={str(p):sha(p) for p in workers.glob('*.py')};required_fit_admissions(run)
def verify():
 assert sha(inputs/'manifest.json')==meta['manifest_sha256']
 for p,h in meta['source_sha256'].items():assert sha(source/p)==h
 for p,h in training['artifacts'].items():assert sha(p)==h
 for p,h in pins.items():assert sha(p)==h
 for frame in manifest['frames']:
  for name,h in frame['sha256'].items():assert sha(cache/'scientific-processing/balanced16-native-v2'/frame['relative_directory']/name)==h
verify();roots={'cpu':cache/'insula/rootfs-v2','metrics':cache/'metrics-rootfs'};locks={}
for name,root in roots.items():locks[name]=json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,locks[name]['rootfs_sha256'])
base=run/'scoring-parallel-v3';base.mkdir();records=[];checks=[];start=time.monotonic()
def stage(name,root,src,out,worker,extra=None):
 out.mkdir();command=launch_plan(roots[root],package,src,out,['python','/tmp/workers/'+worker]);i=command.index('--');command[i:i]=['--ro-bind',str(workers),'/tmp/workers','--ro-bind',str(inputs),'/tmp/inputs',*[x for folder,target in [('balanced16-native-v2','/tmp/native'),('balanced16-physical-v2','/tmp/physical'),('balanced16-labels-v2','/tmp/boxes')] for x in ['--ro-bind',str(cache/'scientific-processing'/folder),target]],*(extra or [])]
 print('RUN',name,flush=True)
 with (out/'live.log').open('w') as log:result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
 assert result.returncode==0,(name,str(out/'live.log'));checks.append({'name':name,'command':command,'exit_code':0});verify()
def checkpoint(curve):
 step=curve['step'];directory=base/str(step);directory.mkdir();prepared=directory/'prepared';scored=directory/'scored';heads=output/f'checkpoint-{step:04d}'
 stage(f'prepare-{step}','cpu',heads,prepared,'prepare_v2.py');stage(f'score-{step}','metrics',prepared,scored,'metrics.py');values=json.loads((scored/'check.json').read_text());receipt={'manifest':manifest,'validation':values,'artifacts':{str(p):sha(p) for folder in [prepared,scored] for p in folder.iterdir() if p.is_file()}};receiptpath=directory/'score-receipt.json';receiptpath.write_text(json.dumps(receipt,indent=2));expected=directory/'expected.json';expected.write_text(json.dumps({'receipt':receipt,'receipt_sha256':sha(receiptpath)}));extra=['--ro-bind',str(scored),'/tmp/scored','--ro-bind',str(heads),'/tmp/heads','--ro-bind',str(expected),'/tmp/expected.json','--ro-bind',str(receiptpath),'/tmp/score-receipt.json']
 stage(f'proposal-audit-{step}','cpu',prepared,directory/'proposal-audit','audit_proposals.py',extra);stage(f'export-metric-audit-{step}','metrics',prepared,directory/'metric-audit','audit_metrics.py',extra)
 for p,h in receipt['artifacts'].items():assert sha(p)==h
 aph={k:v['APH'] for k,v in values['LEVEL2_per_class'].items()};record=({'step':step,'cumulative_train_seconds':curve['cumulative_train_seconds'],'LEVEL2_per_class':values['LEVEL2_per_class'],'all_class_quality_passed':quality_gate(aph),'mean_APH':values['mean_populated_class_APH']});print('SCORED',step,aph,flush=True);return record

from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=3) as pool:records=sorted(pool.map(checkpoint,training['validation']['checkpoint_curve']),key=lambda r:r['step'])
result={'curve':records,'native_scoring_and_audits_seconds':time.monotonic()-start,'full_class_fit_passed':len(records)==len(manifest['execution']['checkpoint_grid']) and all(x['all_class_quality_passed'] for x in records[-2:]) and training['validation']['loss_gate_passed'],'scope':'training-only readiness gate; no heldout/generalization claim','checks':checks,'runtime_locks':locks,'worker_hashes':pins,'training_receipt_sha256':sha(run/'train-verified.json'),'required_fit_admissions':required_fit_admissions(run),'artifacts':{str(p):sha(p) for p in base.rglob('*') if p.is_file()}}
(PACKAGE/'research'/f'cohort16-{a.variant}-{a.run_id}-quality-parallel-v3.json').write_text(json.dumps(result,indent=2)+'\n')
print('FINAL FIT GATE',result['full_class_fit_passed'],flush=True)
