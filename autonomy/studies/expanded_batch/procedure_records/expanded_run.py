"""Serial GPU sweep, native quality gating, and replay before snapshot release."""
import argparse,fcntl,json,os,shutil,sys,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path[:0]=[str(P),str(P/'tier1'),str(P/'architecture')]
from admission import reserve_write,fit_interval
from tier1.receipt_lifecycle import load_release_records
from advanced.catalog import catalog
from advanced.recovery import restore_curve,retain_admission,recover_checkpoint
from storage import sha,unique_payload_bytes,deduplicate
from insula.entry import launch_plan
from insula.runtime_identity import verify_rootfs
from experiment_runner import run_stage
C=Path.home()/'.cache/waystone/waymo-perception';W=C/'scientific-processing'
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True);parser.add_argument('--contracts-only',action='store_true');parser.add_argument('--reuse-baseline',type=Path);parser.add_argument('--baseline-trajectory',type=Path);parser.add_argument('--resume',action='store_true');a=parser.parse_args();assert a.run_id.isalnum()
 lock=(C/'insula/architecture-experiments.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 run=C/'insula'/f'advanced-{a.run_id}'
 if a.resume:
  assert run.is_dir();source=run/'source';package=source/'experiment';original_metadata=json.loads((run/'run.json').read_text());pins=original_metadata['source_sha256'];assert all(sha(source/p)==h for p,h in pins.items())
  override=None;override_pins={}
 else:
  run.mkdir();source=run/'source';source.mkdir();package=source/'experiment';package.mkdir()
  for folder in ['pipeline','gpu','cohort','tier1','advanced','research']:shutil.copytree(P/folder,package/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
  text=(package/'cohort/audit_proposals.py').read_text().replace("len(r['manifest']['frames'])==16","len(r['manifest']['frames'])==1").replace("'frames':16","'frames':1");(package/'cohort/audit_proposals.py').write_text(text)
  for file in ['prepare_v2.py','metrics.py']:
   path=package/'cohort'/file;path.write_text(path.read_text().replace('16-frame','one-frame'))
  pins={str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()};override=None;override_pins={}
 fixturepath=P/'research/tier1-allclass-fixture-verified.json';fixture=json.loads(fixturepath.read_text())
 for key in ['targets','report','physical','boxes']:assert sha(fixture[key])==fixture[key+'_sha256']
 for p,h in fixture['source_pins'].items():assert sha(p)==h
 for control in fixture['controls'].values():
  for key in ['observations','lineage']:assert sha(control[key])==control[key+'_sha256']
 roots={'cpu':C/'insula/rootfs-v2','gpu':C/'gpu-rootfs','metrics':C/'metrics-rootfs'};old=json.loads((C/'detector-gpu-live-a/receipt.json').read_text());locks={}
 for name,root in roots.items():locks[name]=old['runtime_lock'] if name=='gpu' else json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,locks[name]['rootfs_sha256'])
 for p,h in old['driver_hashes'].items():assert sha(p)==h
 native=W/'balanced16-native-v2';physical=W/'balanced16-physical-v2';boxes=W/'balanced16-labels-v2';scene,t=fixture['identity'].split(':');relative=f'{scene}/{t}/producer'
 frame={'identity':fixture['identity'],'split':'training','relative_directory':relative,'sha256':{n:sha(native/relative/n) for n in ['observations.npz','targets.npz','report.json']},'physical_sha256':fixture['physical_sha256'],'boxes_sha256':fixture['boxes_sha256']}
 metadata={'fixture_receipt_sha256':sha(fixturepath),'source_sha256':pins,'runtime_locks':locks,'driver_hashes':old['driver_hashes'],'matrix':catalog(),'scope':'one fixed all-class batch; native all four LEVEL2 APH >= .8 at consecutive terminal checkpoints; training only'};
 if not a.resume:(run/'run.json').write_text(json.dumps(metadata,indent=2))
 checks=[];summary={'run_directory':str(run),'metadata_sha256':sha(run/'run.json'),'cases':{},'scope':metadata['scope']};summarypath=P/'research'/f'advanced-{a.run_id}-results.json'
 if a.resume:summary=json.loads(summarypath.read_text());summary['finished']=False;summarypath.write_text(json.dumps(summary,indent=2))
 def validate():
  assert all(sha(source/p)==h for p,h in pins.items());assert unique_payload_bytes(W)<=15*1024**3
 def stage(name,root,src,out,worker,inputs,observation,extra=None):
  receiptpath=run/(name+'-verified.json')
  if a.resume and receiptpath.exists():
   evidence=json.loads(receiptpath.read_text());assert evidence['metadata_sha256']==summary['metadata_sha256'];assert all(sha(p)==h for p,h in evidence['artifacts'].items());checks.append({'receipt':str(receiptpath),'sha256':sha(receiptpath)});print('REUSED ADMITTED',name,flush=True);return evidence
  if a.resume and out.exists() and any(out.iterdir()) and not (worker=='advanced/train.py' and not json.loads((inputs/'job.json').read_text()).get('replay',False)):out.rename(out.with_name(out.name+'-unadmitted-'+str(time.time_ns())))
  out.mkdir(exist_ok=True)
  if root=='cpu' and worker.endswith('prepare_v3.py'):reserve_write(W,4*1024**2)
  if root=='metrics':reserve_write(W,4*1024**2)
  if root=='gpu':
   cmd=old['checks'][0]['command'].copy();cmd[cmd.index('/experiment')-1]=str(package);cmd[cmd.index('/outputs')-1]=str(out);cmd[-1]='/experiment/'+worker
  else:cmd=launch_plan(roots[root],package,src,out,['python','/experiment/'+worker])
  override_active=override is not None and root=='gpu' and (worker=='tier1/state_contract.py' or (worker=='advanced/train.py' and json.loads((inputs/'job.json').read_text()).get('replay',False)))
  if override_active:cmd[-1]='/tmp/replay-control/'+('state_contract.py' if worker=='tier1/state_contract.py' else 'train.py')
  i=cmd.index('--');cmd[i:i]=['--ro-bind',str(inputs),'/tmp/inputs','--ro-bind',str(observation),'/tmp/fixture','--ro-bind',str(Path(fixture['targets']).parent),'/tmp/targets','--ro-bind',str(native),'/tmp/native','--ro-bind',str(physical),'/tmp/physical','--ro-bind',str(boxes),'/tmp/boxes','--ro-bind',str(package/'cohort'),'/tmp/workers','--ro-bind',str(W),'/tmp/scientific','--setenv','CUBLAS_WORKSPACE_CONFIG',':4096:8',*(['--ro-bind',str(override),'/tmp/replay-control'] if override_active else []),*(extra or [])]
  print('RUN',name,flush=True);started=time.monotonic()
  with (out/'live.log').open('a') as log:r=run_stage(cmd,source,dict(os.environ),log,timeout=7200)
  if r.returncode:raise RuntimeError(name+' failed: '+str(out/'live.log'))
  validate();durable=run/'stage-evidence'/name;durable.mkdir(parents=True)
  for file in ['check.json','live.log']:
   if (out/file).exists():shutil.copy(out/file,durable/file)
  transient=worker=='advanced/train.py' and not json.loads((inputs/'job.json').read_text()).get('replay',False)
  artifacts={str(p):sha(p) for p in (durable if worker=='advanced/train.py' else out).rglob('*') if p.is_file()}
  receipt={'override_source_sha256':override_pins if override_active else {},'transient_artifacts':{str(p):sha(p) for p in out.rglob('*') if p.is_file() and p.name not in ['check.json','live.log']} if transient else {},'name':name,'command':cmd,'exit_code':0,'elapsed_seconds':time.monotonic()-started,'artifacts':artifacts,'input_job_sha256':sha(inputs/'job.json'),'metadata_sha256':summary['metadata_sha256'],'validation':json.loads((out/'check.json').read_text()) if (out/'check.json').exists() else None};receiptpath=run/(name+'-verified.json');receiptpath.write_text(json.dumps(receipt,indent=2));checks.append({'receipt':str(receiptpath),'sha256':sha(receiptpath)});print('ADMITTED',name,flush=True);return receipt
 admissionpath=P/'research/advanced-native-admission-verified.json';admitted=json.loads(admissionpath.read_text());assert set(admitted['cases'])==set(catalog())
 for path,digest in admitted['source_pins'].items():assert sha(path)==digest
 for folder in ['advanced','pipeline','tier1','gpu']:
  for current in (package/folder).rglob('*.py'):
   relative=current.relative_to(package);matches=[path for path in admitted['source_pins'] if path.endswith('/experiment/'+str(relative))];assert len(matches)==1 and sha(current)==admitted['source_pins'][matches[0]],('admission source mismatch',relative)
 for name,evidence in admitted['cases'].items():
  assert evidence['validation']['case']==catalog()[name] and evidence['validation']['fixed_head_shape']
  assert evidence['exit_code']==0 and evidence['validation']['exact_repeated_three_update_model_adam_rng']
  assert all(sha(path)==digest for path,digest in evidence['artifacts'].items())
 (run/'admission-reference.json').write_text(json.dumps(retain_admission(admissionpath,run),indent=2))
 grouping=json.loads((P/'research/advanced-grouping-fixture-verified.json').read_text());ranges=json.loads((P/'research/advanced-range-fixture-verified.json').read_text())
 for receipt in [grouping,ranges]:assert all(sha(path)==digest for path,digest in receipt['artifacts'].items())
 if a.contracts_only:return
 for name,case in catalog().items():
  if a.resume and summary['cases'].get(name,{}).get('status') in ['sustained native overfit','failed to overfit by 10000 updates']:continue
  if name=='baseline' and a.reuse_baseline:
   prior=json.loads(a.reuse_baseline.read_text());baseline=prior['cases']['baseline'];assert baseline['status'] in ['sustained native overfit','failed to overfit by 10000 updates'];summary['cases']['baseline']={**baseline,'reused_from':str(a.reuse_baseline),'reused_result_sha256':sha(a.reuse_baseline),'time_to_fit':fit_interval(baseline['curve'])};summarypath.write_text(json.dumps(summary,indent=2));continue
  if case.get('equivalence_control'):
   assert fixture['controls']['all_pillars']['validation']['packing']['exact_baseline_observations'];summary['cases'][name]={'status':'exact observation equivalence control','same_as':'baseline','native_quality_curve_inherited':True};summarypath.write_text(json.dumps(summary,indent=2));continue
  case_run=run/name;case_run.mkdir(exist_ok=a.resume);inputs=case_run/'inputs';inputs.mkdir(exist_ok=a.resume);(inputs/'manifest.json').write_text(json.dumps({'frames':[frame]}));control=case['observation'];observation=Path(grouping['controls'][control]['observations'] if control in grouping['controls'] else ranges['observations'] if control=='range_fusion' else fixture['controls']['baseline']['observations']).parent;assert sha(observation/'observations.npz')==admitted['cases'][name]['observations_sha256'];output=W/f'advanced-{a.run_id}-{name}';output.mkdir(exist_ok=a.resume);records=restore_curve(summary['cases'].get(name,{})) if a.resume else [];release=load_release_records(case_run/'snapshot-release.json') if a.resume else [];case_checks=len(checks)
  if a.resume:
   for receiptpath in run.glob(name+'-*-verified.json'):
    evidence=json.loads(receiptpath.read_text());assert all(sha(p)==h for p,h in evidence['artifacts'].items());checks.append({'receipt':str(receiptpath),'sha256':sha(receiptpath)})
  if a.resume:recover_checkpoint(output)
  resumed_trajectory=a.resume and (output/'checkpoint.pt').exists()
  adopted=(name=='baseline' and a.baseline_trajectory is not None) or resumed_trajectory
  if adopted:
   trajectory=output if resumed_trajectory else a.baseline_trajectory;v=json.loads((trajectory/'check.json').read_text());assert v['case']==case
   if not resumed_trajectory:
    for file in ['check.json','checkpoint.pt']:os.link(trajectory/file,output/file)
   assert sha(output/'checkpoint.pt')==v['checkpoint_sha256']
   for point in ([] if resumed_trajectory else v['checkpoint_curve']):
    d=output/f"checkpoint-{point['step']:04d}";d.mkdir();os.link(trajectory/d.name/'heads-00.npz',d/'heads-00.npz')
   adoption={'trajectory':str(trajectory),'check_sha256':sha(trajectory/'check.json'),'checkpoint_sha256':sha(trajectory/'checkpoint.pt'),'original_source_metadata_sha256':sha(C/'insula/tier1-overfit20261002a/run.json')}
   if resumed_trajectory:(case_run/'trajectory-adoption-recovery-v1.json').write_text(json.dumps(adoption,indent=2))
   else:summary['adopted_baseline']=adoption;(run/'baseline-adoption.json').write_text(json.dumps(adoption,indent=2))
  try:
   reserve_write(W,(20 if adopted else 320)*1024**2)
   for target in ([v['updates']]+[s for s in [300,500,750,1000,1500,2000,3000,4000,6000,8000,10000] if s>v['updates']] if adopted else [300,500,750,1000,1500,2000,3000,4000,6000,8000,10000]):
    job={'case':case,'target':target};(inputs/'job.json').write_text(json.dumps(job));resume=output/'resume';resume.mkdir(exist_ok=True)
    if not adopted:
     if (output/'checkpoint.pt').exists():os.replace(output/'checkpoint.pt',resume/'checkpoint.pt');job['retained_sha256']=sha(resume/'checkpoint.pt');(inputs/'job.json').write_text(json.dumps(job))
     stage(name+'-train-'+str(target),'gpu',source,output,'advanced/train.py',inputs,observation,['--ro-bind',str(resume),'/tmp/retained'])
    initial=output/'checkpoint-0000/heads-00.npz';matches=[initial]
    for candidate in W.glob('tier1-*/checkpoint-0000/heads-00.npz'):
     if candidate!=initial and candidate.stat().st_size==initial.stat().st_size and sha(candidate)==sha(initial):matches.append(candidate)
    if len(matches)>1:deduplicate(matches)
    validation=json.loads((output/'check.json').read_text());stage(name+'-loss-'+str(target),'cpu',output,case_run/('loss-'+str(target)),'tier1/loss.py',inputs,observation)
    done={x['step'] for x in records}
    def scorepoint(point):
     step=point['step']
     if step in done:return
     heads=output/f'checkpoint-{step:04d}';directory=output/'scoring'/str(step);directory.mkdir(parents=True,exist_ok=a.resume);prepared=directory/'prepared';scored=directory/'scored'
     stage(name+'-prepare-'+str(step),'cpu',heads,prepared,'tier1/prepare_v3.py',inputs,observation);stage(name+'-score-'+str(step),'metrics',prepared,scored,'cohort/metrics.py',inputs,observation)
     values=json.loads((scored/'check.json').read_text());receipt={'manifest':{'frames':[frame]},'validation':values,'artifacts':{str(p):sha(p) for folder in [prepared,scored] for p in folder.iterdir() if p.is_file()}};receiptpath=directory/'score-receipt.json';receiptpath.write_text(json.dumps(receipt,indent=2));expected=directory/'expected.json';expected.write_text(json.dumps({'receipt':receipt,'receipt_sha256':sha(receiptpath)}));extra=['--ro-bind',str(scored),'/tmp/scored','--ro-bind',str(heads),'/tmp/heads','--ro-bind',str(expected),'/tmp/expected.json','--ro-bind',str(receiptpath),'/tmp/score-receipt.json']
     stage(name+'-proposal-audit-'+str(step),'cpu',prepared,directory/'proposal-audit','tier1/audit_proposals_v3.py',inputs,observation,extra);stage(name+'-metric-audit-'+str(step),'metrics',prepared,directory/'metric-audit','cohort/audit_metrics.py',inputs,observation,extra)
     aph={k:v['APH'] for k,v in values['LEVEL2_per_class'].items()};passed=set(aph)=={'1','2','3','4'} and all(v>=.8 for v in aph.values());records.append({**point,'LEVEL2_per_class':values['LEVEL2_per_class'],'all_class_quality_passed':passed});print('QUALITY',name,step,aph,flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
     futures=[pool.submit(scorepoint,point) for point in validation['checkpoint_curve'] if point['step'] not in done]
     for future in futures:future.result()
    records.sort(key=lambda x:x['step'])
    passed=len(records)>=2 and all(x['all_class_quality_passed'] for x in records[-2:]);summary['cases'][name]={'status':'quality passed; replay pending' if passed else 'running extension' if target<10000 else 'budget exhausted; replay pending','curve':records,'parameters':validation['parameters'],'updates':target};summarypath.write_text(json.dumps(summary,indent=2))
    (inputs/'job.json').write_text(json.dumps({'case':case,'target':target,'replay':True,'retained_sha256':sha(output/'checkpoint.pt')}));stage(name+'-replay-'+str(target),'gpu',source,case_run/('replay-'+str(target)),'advanced/train.py',inputs,observation,['--ro-bind',str(output),'/tmp/retained'])
    if (resume/'checkpoint.pt').exists():
     ledger=case_run/'model-supersessions.json';entries=json.loads(ledger.read_text()) if ledger.exists() else [];entries.append({'old_sha256':sha(resume/'checkpoint.pt'),'new_sha256':sha(output/'checkpoint.pt'),'same_Adam_trajectory_through':target});ledger.write_text(json.dumps(entries,indent=2));(resume/'checkpoint.pt').unlink()
    # All snapshot hashes/native/literal receipts and exact replay are durable before release.
    for point in validation['checkpoint_curve']:
     if point['step'] in [0,target]:continue
     heads=output/f"checkpoint-{point['step']:04d}"/'heads-00.npz'
     if not heads.exists():continue
     release.append({'path':str(heads),'sha256':sha(heads),'canonical_head_sha256':point['head_sha256']});(case_run/'snapshot-release.json').write_text(json.dumps({'released_only_after_exact_replay_and_all_native_and_literal_audits':True,'released':release},indent=2));heads.unlink();heads.parent.rmdir()
    if passed or target==10000:break
    adopted=False
   (case_run/'snapshot-release.json').write_text(json.dumps({'released_only_after_exact_replay_and_all_native_and_literal_audits':True,'released':release},indent=2));summary['cases'][name].update({'status':'sustained native overfit' if passed else 'failed to overfit by 10000 updates','output_directory':str(output),'cumulative_train_seconds':validation['cumulative_train_seconds'],'time_to_fit':fit_interval(records),'clipped_steps':validation['clipped_steps'],'verification_receipts':checks[case_checks:],'snapshot_release_sha256':sha(case_run/'snapshot-release.json')})
  except Exception as exc:
   summary['cases'][name]={'status':'execution failed; artifacts retained','error':str(exc),'curve':records,'output_directory':str(output)};print('FAIL CASE',name,str(exc),flush=True)
  summary['unique_scientific_payload_bytes']=unique_payload_bytes(W);summarypath.write_text(json.dumps(summary,indent=2));validate()
 summary['finished']=True;summary['verification_receipts']=checks;summarypath.write_text(json.dumps(summary,indent=2));print('TERMINAL SWEEP',str(summarypath),flush=True)
if __name__=='__main__':main()
