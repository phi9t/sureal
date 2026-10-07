from pathlib import Path
import datetime,hashlib,json,subprocess,sys,time
code=Path('autonomy').resolve();sys.path.insert(0,str(code))
from insula.entry import launch_plan
from insula.runtime_identity import verify_rootfs
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
variant=sys.argv[1];assert variant in ['masked_pfn','window_bev','coarse_mlp']
cache=Path.home()/'.cache/waystone/waymo-perception';
def enforce_storage(reserve=0):
 used=sum(p.stat().st_size for p in (cache/'scientific-processing').rglob('*') if p.is_file())
 if used+reserve>15*1024**3:
  (code/('research/architecture-'+variant+'-storage-failure.json')).write_text(json.dumps({'used_bytes':used,'reserve_bytes':reserve,'cap_bytes':15*1024**3}))
  raise RuntimeError('scientific working storage cap exceeded')
enforce_storage(64*1024**2)
evidence=code/('research/architecture-'+variant+'-execution-verified.json');training=json.loads(evidence.read_text())
for p,h in training['artifacts'].items():assert sha(p)==h
manifest=json.loads(json.dumps(training['manifest']));manifest['decoder_candidate']='score-first-v2';manifest['decoder_sha256']=sha(code/'detection/scored_proposals_v2.py');manifest['secondary_spec_sha256']=sha(code/'research/normalization-secondary-decoder-spec.md');frame=manifest['frames'][0];scene,timestamp=frame['identity'].split(':');frame['physical_sha256']=sha(cache/'scientific-processing/overfit-point-frames-v1'/scene/'producer'/f'{timestamp}.npz');frame['boxes_sha256']=sha(cache/'scientific-processing/overfit-box-targets-v1'/scene/'producer/targets.json')
base=cache/('insula/architecture-'+variant+'-score-first-v1');base.mkdir();inputs=base/'input';inputs.mkdir();(inputs/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
output=cache/('scientific-processing/architecture-'+variant+'-score-first-v1');output.mkdir();workers=Path('.scratch').resolve();worker_pins={name:sha(workers/name) for name in ['prepare-norm-score-first.py','native-one-batch-overfit-metrics.py']};locks={}
for name,root in [('prepare',cache/'insula/rootfs-v2'),('score',cache/'metrics-rootfs')]:
 lock=json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,lock['rootfs_sha256']);locks[name]=lock
checks=[];results=[];started=datetime.datetime.now(datetime.timezone.utc).isoformat();clock=time.monotonic()
for curve in training['validation']['checkpoint_curve']:
 step=curve['step'];directory=output/str(step);directory.mkdir();prepared=directory/'prepared';prepared.mkdir();scored=directory/'scored';scored.mkdir();source=cache/('scientific-processing/architecture-'+variant+'-v1')/('checkpoint-%04d'%step)
 for stage,root,src,out,worker in [('prepare',cache/'insula/rootfs-v2',source,prepared,'prepare-norm-score-first.py'),('score',cache/'metrics-rootfs',prepared,scored,'native-one-batch-overfit-metrics.py')]:
  enforce_storage(16*1024**2)
  command=launch_plan(root,code,src,out,['python','/tmp/workers/'+worker]);i=command.index('--');command[i:i]=['--ro-bind',str(workers),'/tmp/workers','--ro-bind',str(inputs),'/tmp/inputs','--ro-bind',str(cache/'scientific-processing/overfit-point-frames-v1'),'/tmp/physical','--ro-bind',str(cache/'scientific-processing/overfit-box-targets-v1'),'/tmp/boxes','--ro-bind',str(cache/'scientific-processing/overfit-native-cache-v1'),'/tmp/native']
  with (out/'live.log').open('w') as log:run=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
  assert run.returncode==0,(step,stage,(out/'live.log').read_text());enforce_storage();checks.append({'step':step,'name':stage,'command':command,'exit_code':0})
 enforce_storage()
 score=json.loads((scored/'check.json').read_text());quality=score['LEVEL2_per_class'];minimum=min(x['APH'] for x in quality.values());row={'step':step,'cumulative_train_seconds':curve['cumulative_train_seconds'],'evaluation_losses':curve['evaluation_losses'],'LEVEL2_per_class':quality,'mean_populated_class_APH':score['mean_populated_class_APH'],'mean_gate_passed':score['APH_gate_passed'],'populated_class_gate_passed':minimum>=.8,'minimum_populated_class_APH':minimum};results.append(row)
 print('SCORED',step,'meanAPH',row['mean_populated_class_APH'],'minimum',minimum,flush=True)
 (code/('research/architecture-'+variant+'-score-first-progress.json')).write_text(json.dumps({'expected_checkpoints':len(training['validation']['checkpoint_curve']),'scored_checkpoints':len(results),'curve':results},indent=2)+'\n')
assert all(sha(workers/name)==h for name,h in worker_pins.items()) and sha(code/'detection/scored_proposals_v2.py')==manifest['decoder_sha256']
first={}
for key in ['mean_gate_passed','populated_class_gate_passed']:
 passed=[i for i,x in enumerate(results) if x[key]]
 if not passed:first[key]={'status':'not reached at sampled checkpoints','budget_updates':2000,'budget_train_seconds':training['validation']['cumulative_train_seconds']}
 else:
  i=passed[0];first[key]={'status':'first observed sampled pass; sustained/final pass separate','bracket_updates':[results[i-1]['step'] if i else 0,results[i]['step']],'bracket_train_seconds':[results[i-1]['cumulative_train_seconds'] if i else 0,results[i]['cumulative_train_seconds']]}
result={'started_utc':started,'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks,'runtime_locks':locks,'decoder_sha256':manifest['decoder_sha256'],'training_evidence_sha256':sha(evidence),'worker_hashes':worker_pins,'manifest_sha256':sha(inputs/'manifest.json'),'validation':{'curve':results,'first_observed_pass':first,'scoring_wall_seconds':time.monotonic()-clock,'scope':'sampled checkpoint diagnostic curve; independent retained audit still required; no exact threshold crossing or heldout claim'},'artifacts':{str(p):sha(p) for p in output.rglob('*') if p.is_file()}}
(code/('research/architecture-'+variant+'-score-first-verified.json')).write_text(json.dumps(result,indent=2)+'\n');print('PASS live sampled learning curve scored',flush=True)
