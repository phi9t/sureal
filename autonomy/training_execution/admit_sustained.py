"""Serialized, source-frozen native balanced16 admission pilot (0/19/35).

No native fit or research promotion. Retains all payloads for later verified
HDFS publication; never evicts another run or bypasses the scientific cap.
"""
import argparse,fcntl,json,os,re,shutil,time
from pathlib import Path
P=Path(__file__).resolve().parents[1]
from studies.architecture.experiment_runner import run_stage
from insula.launch_plan import load_default_runtime_lock,record_plan,render_plan
from insula.runtime_roots import current_cpu_rootfs, current_gpu_rootfs, current_metrics_rootfs
from resources.scientific_payload import sha,unique_payload_bytes
from resources.scientific_budget import reserve_write
from detection.sustained_contract import validate_contract
from resources.sustained_scoring_budget import stage_timeout
from training_execution.sustained_sources import cache_snapshot_for_runtime,snapshot_sources,validate_sources
from training_execution.sustained_stage_inputs import freeze_inputs
from training_execution.sustained_controller_backend import GPU_INDEX,build_sustained_stage_plan,driver_hashes_from_plan

C=Path.home()/'.cache/waystone/waymo-perception';W=C/'scientific-processing'
GPU_ROOT=current_gpu_rootfs(C);CPU_ROOT=current_cpu_rootfs(C);METRICS_ROOT=current_metrics_rootfs(C)
WORKER_ENTRIES={
 'train_sustained.py':'/experiment/training_execution/train_sustained.py',
 'replay_sustained.py':'/experiment/training_execution/replay_sustained.py',
 'audit_sustained_loss.py':'/experiment/training_execution/audit_sustained_loss.py',
 'prepare_sustained_v3.py':'/experiment/evaluation/prepare_sustained_v3.py',
 'audit_proposals_sustained_v3.py':'/experiment/evaluation/audit_proposals_sustained_v3.py',
 'metrics_sustained_v3.py':'/experiment/evaluation/metrics_sustained_v3.py',
 'audit_metrics_sustained_v3.py':'/experiment/evaluation/audit_metrics_sustained_v3.py',
}

def worker_entry(worker):
 try:return WORKER_ENTRIES[worker]
 except KeyError as error:raise ValueError('declared sustained worker required') from error

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True);parser.add_argument('--expanded-run-id',default='expanded20261002a');a=parser.parse_args()
 if any(re.fullmatch('[A-Za-z0-9]{1,64}',v) is None for v in [a.run_id,a.expanded_run_id]):raise ValueError('bounded alphanumeric run IDs required')
 lock=(C/'insula/architecture-experiments.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 results=P/'research'/f'advanced-{a.expanded_run_id}-results.json';closure=P/'research'/f'advanced-closure-{a.expanded_run_id}-verified.json'
 evidence=json.loads(closure.read_text());matrix=json.loads(results.read_text())
 if evidence['candidate_sha256']!=sha(results) or not evidence['validation']['all_cases_finished'] or len(evidence['validation']['rows'])!=8 or not matrix['finished']:raise ValueError('independent complete expanded closure required')
 for path,digest in evidence['artifacts'].items():
  if sha(path)!=digest:raise ValueError('expanded closure artifact differs')
 reserve_write(W,2*1024**3)
 historical=C/'insula/cohort16-baseline-balanced20261002a/run.json';old_manifest=json.loads(historical.read_text())['manifest'];candidate=json.loads((P/'research/balanced16-sustained.candidate.json').read_text());frames=old_manifest['frames']
 validate_contract(candidate,[{k:f[k] for k in ['identity','split','sha256']} for f in frames])
 native=W/'balanced16-native-v2'
 for frame in frames:
  parts=Path(frame['relative_directory'])
  if parts.is_absolute() or '..' in parts.parts:raise ValueError('unsafe native frame path')
  for name,digest in frame['sha256'].items():
   if sha(native/parts/name)!=digest:raise ValueError('original native frame changed')
 runtime_lock=load_default_runtime_lock(GPU_ROOT);cpu_runtime_lock=load_default_runtime_lock(CPU_ROOT);metric_runtime_lock=load_default_runtime_lock(METRICS_ROOT)
 runtime=runtime_lock.data;cpu_runtime=cpu_runtime_lock.data;metric_runtime=metric_runtime_lock.data
 R=C/'insula'/f'balanced16-sustained-admission-{a.run_id}';R.mkdir()
 pins=snapshot_sources(P,destination=R/'code');cache_snapshot_for_runtime(pins,R/'source-snapshots');package=Path(pins['source_snapshot_root'])/'autonomy';validate_sources(package,pins,runtime,runtime)
 runtime_path=R/'runtime-lock.json';runtime_path.write_text(json.dumps(runtime,indent=2)+'\n')
 anchor_path=P/'research/training-anchor-templates.candidate.json';anchor_receipt=json.loads((P/'research/training-anchor-candidate-verified.json').read_text())
 if sha(anchor_path)!=anchor_receipt['expected']['candidate_sha256']:raise ValueError('admitted anchor templates changed')
 manifest={'candidate':candidate,'frames':frames,'recipe':'baseline','source_hashes':pins,'runtime_lock':runtime};source=R/'input';source.mkdir();manifest_path=source/'manifest.json';manifest_path.write_text(json.dumps(manifest,indent=2)+'\n');manifest_sha=sha(manifest_path);(source/'anchor-templates.json').write_bytes(anchor_path.read_bytes())
 output=W/f'balanced16-sustained-admission-{a.run_id}';output.mkdir();receipts={}
 def stage(name,worker,directory,extra,gpu=True,metrics=False):
  directory.mkdir();stage_source,input_hashes=freeze_inputs(source,R/(name+'-input'));stage_runtime_lock=metric_runtime_lock if metrics else runtime_lock if gpu else cpu_runtime_lock
  plan=build_sustained_stage_plan(stage_runtime_lock,package=package,stage_source=stage_source,output=directory,worker=worker,native=native,physical=W/'balanced16-physical-v2',boxes=W/'balanced16-labels-v2',runtime_lock_path=runtime_path,scientific_root=W,source_snapshot_store=R/'source-snapshots',extra=extra,gpu_index=GPU_INDEX if gpu else None,source_snapshot_digest=pins['source_snapshot_sha256'],input_source=source)
  command=render_plan(plan);launch_record=record_plan(plan)
  with (directory/'live.log').open('w') as log:result=run_stage(command,package,dict(os.environ),log,timeout=stage_timeout(metrics))
  if result.returncode:raise RuntimeError(f'{name} failed; retained log: {directory}/live.log')
  validate_sources(package,pins,runtime,runtime)
  if any(sha(path)!=digest for path,digest in input_hashes.items()):raise ValueError('immutable stage inputs changed')
  if sha(manifest_path)!=manifest_sha or unique_payload_bytes(W)>15*1024**3 or unique_payload_bytes(output)>2*1024**3:raise ValueError('manifest or storage admission violated')
  stage_runtime=metric_runtime if metrics else runtime if gpu else cpu_runtime
  receipt={'stage':name,'command':command,'launch_plan':launch_record,'exit_code':0,'source_hashes':pins,'runtime_lock':stage_runtime,'driver_hashes':driver_hashes_from_plan(plan) if gpu else {},'manifest_sha256':manifest_sha,'expanded_closure_sha256':sha(closure),'historical_manifest_sha256':sha(historical),'input_hashes':input_hashes,'job_sha256':sha(stage_source/'job.json') if worker=='train_sustained.py' else None,'artifacts':{str(p):sha(p) for p in directory.rglob('*') if p.is_file()},'scope':'native engineering pilot only; sustained fitting/science/native APH pending'}
  receipt_path=R/(name+'-verified.json');receipt_path.write_text(json.dumps(receipt,indent=2)+'\n');receipts[name]={'path':str(receipt_path),'sha256':sha(receipt_path)};print('ADMITTED',name,flush=True)
 previous=None
 for step in [0,19,35]:
  (source/'job.json').write_text(json.dumps({'target_step':step,'retained_sha256':sha(previous/'checkpoint.pt') if previous else None}))
  directory=output/f'update-{step:02d}';stage(f'train-{step}','train_sustained.py',directory,{'/tmp/retained':previous} if previous else {})
  report=json.loads((directory/'check.json').read_text())
  if report['updates']!=step or report['stop_reason']!='sample' or not report['resource_gate_passed']:raise ValueError('pilot chunk not admitted')
  audit={'checkpoint_sha256':sha(directory/'checkpoint.pt'),'head_hashes':report['head_hashes'],'pilot_reference':step==35}
  if step==35:audit['previous_checkpoint_sha256']=sha(previous/'checkpoint.pt')
  (source/'audit.json').write_text(json.dumps(audit));audit_dir=R/f'audit-{step:02d}';audit_inputs={'/tmp/retained':directory}
  if step==35:audit_inputs['/tmp/previous']=previous
  stage(f'audit-{step}','replay_sustained.py',audit_dir,audit_inputs)
  replay=json.loads((audit_dir/'replay.json').read_text())
  if len(replay['checked_frames'])!=16 or step==35 and len(replay['pilot_reference_checks'])!=2:raise ValueError('mandatory full16/restart audit missing')
  (source/'loss-audit.json').write_text(json.dumps({'manifest_sha256':manifest_sha,'report_sha256':sha(directory/'check.json'),'head_hashes':report['head_hashes']}))
  # The loss worker reads retained report/heads through /source; stage inputs
  # remain separately immutable at /tmp/inputs.
  stage(f'literal-loss-{step}','audit_sustained_loss.py',R/f'loss-{step:02d}',{'/source':directory},gpu=False)
  (source/'export-audit.json').write_text(json.dumps({'manifest_sha256':manifest_sha,'anchor_templates_sha256':sha(source/'anchor-templates.json'),'head_hashes':report['head_hashes']}))
  prepared=R/f'prepared-{step:02d}';stage(f'export-{step}','prepare_sustained_v3.py',prepared,{'/source':directory/'heads'},gpu=False)
  export_receipt=json.loads(Path(receipts[f'export-{step}']['path']).read_text());export_receipt['inputs']={p:h for p,h in export_receipt['input_hashes'].items() if Path(p).name in {'manifest.json','anchor-templates.json','export-audit.json'}};export_receipt['validation']=json.loads((prepared/'preparation.json').read_text());(source/'score-receipt.json').write_text(json.dumps(export_receipt,indent=2)+'\n');(source/'expected.json').write_text(json.dumps({'receipt':export_receipt,'receipt_sha256':sha(source/'score-receipt.json')}))
  stage(f'proposals-{step}','audit_proposals_sustained_v3.py',R/f'proposal-audit-{step:02d}',{'/source':prepared,'/tmp/heads':directory/'heads','/tmp/score-receipt.json':source/'score-receipt.json','/tmp/expected.json':source/'expected.json'},gpu=False)
  scored=R/f'scored-{step:02d}';stage(f'score-{step}','metrics_sustained_v3.py',scored,{'/source':prepared},gpu=False,metrics=True)
  score_receipt=json.loads(Path(receipts[f'score-{step}']['path']).read_text());score_receipt['parent_artifacts']=export_receipt['artifacts'];score_receipt['validation']=json.loads((scored/'check.json').read_text());(source/'score-receipt.json').write_text(json.dumps(score_receipt,indent=2)+'\n');(source/'expected.json').write_text(json.dumps({'receipt':score_receipt,'receipt_sha256':sha(source/'score-receipt.json')}))
  stage(f'metrics-audit-{step}','audit_metrics_sustained_v3.py',R/f'metric-audit-{step:02d}',{'/source':prepared,'/tmp/scored':scored,'/tmp/score-receipt.json':source/'score-receipt.json','/tmp/expected.json':source/'expected.json'},gpu=False,metrics=True)
  previous=directory
 final={'run_directory':str(R),'output_directory':str(output),'manifest_sha256':manifest_sha,'stage_receipts':receipts,'scope':'native baseline0/19/35 exact state/heads/reference pilot; no sustained-fit or scientific acceptance'}
 (P/'research'/f'balanced16-sustained-admission-{a.run_id}-verified.json').write_text(json.dumps(final,indent=2)+'\n');print('PASS native baseline admission pilot; sustained controller/HDFS gates remain',flush=True)
if __name__=='__main__':main()
