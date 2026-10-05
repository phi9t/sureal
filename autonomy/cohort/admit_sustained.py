"""Serialized, source-frozen native balanced16 admission pilot (0/19/35).

No native fit or research promotion. Retains all payloads for later verified
HDFS publication; never evicts another run or bypasses the scientific cap.
"""
import argparse,fcntl,json,os,re,shutil,sys,time
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path[:0]=[str(P),str(P/'architecture')]
from experiment_runner import run_stage
from pipeline.runtime_identity import verify_rootfs
from pipeline.insula_entry import launch_plan
from tier1.storage import sha,unique_payload_bytes
from tier1.admission import reserve_write
from cohort.sustained_contract import validate_contract
from cohort.sustained_scoring_budget import stage_timeout
from cohort.sustained_sources import snapshot_sources,validate_sources
from cohort.sustained_stage_inputs import freeze_inputs,bind_stage_paths

C=Path.home()/'.cache/waystone/waymo-perception';W=C/'scientific-processing'

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
 old=json.loads((C/'detector-gpu-live-a/receipt.json').read_text());runtime=old['runtime_lock'];verify_rootfs(C/'gpu-rootfs',runtime['rootfs_sha256'])
 metric_runtime=json.loads(Path(str(C/'metrics-rootfs')+'.lock.json').read_text());verify_rootfs(C/'metrics-rootfs',metric_runtime['rootfs_sha256'])
 for path,digest in old['driver_hashes'].items():
  if sha(path)!=digest:raise ValueError('driver changed')
 R=C/'insula'/f'balanced16-sustained-admission-{a.run_id}';R.mkdir();package=R/'code';package.mkdir()
 for folder in ['pipeline','gpu','tier1','cohort','evidence']:
  for path in (P/folder).rglob('*.py'):
   if '__pycache__' in path.parts:continue
   dest=package/path.relative_to(P);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
 pins=snapshot_sources(package,R/'source-snapshots');validate_sources(package,pins,runtime,runtime)
 runtime_path=R/'runtime-lock.json';runtime_path.write_text(json.dumps(runtime,indent=2)+'\n')
 anchor_path=P/'research/training-anchor-templates.candidate.json';anchor_receipt=json.loads((P/'research/training-anchor-candidate-verified.json').read_text())
 if sha(anchor_path)!=anchor_receipt['expected']['candidate_sha256']:raise ValueError('admitted anchor templates changed')
 manifest={'candidate':candidate,'frames':frames,'recipe':'baseline','source_hashes':pins,'runtime_lock':runtime};source=R/'input';source.mkdir();manifest_path=source/'manifest.json';manifest_path.write_text(json.dumps(manifest,indent=2)+'\n');manifest_sha=sha(manifest_path);(source/'anchor-templates.json').write_bytes(anchor_path.read_bytes())
 output=W/f'balanced16-sustained-admission-{a.run_id}';output.mkdir();receipts={}
 def stage(name,worker,directory,extra,gpu=True,metrics=False):
  directory.mkdir();stage_source,input_hashes=freeze_inputs(source,R/(name+'-input'));command=old['checks'][0]['command'].copy()
  if gpu:
   for target,path in [('/experiment',package),('/source',stage_source),('/outputs',directory)]:command[command.index(target)-1]=str(path)
   command[-1]='/experiment/cohort/'+worker
  elif metrics:command=launch_plan(C/'metrics-rootfs',package,stage_source,directory,['python','/experiment/cohort/'+worker])
  else:command=launch_plan(C/'gpu-rootfs',package,stage_source,directory,['/opt/waymo/bin/python','/experiment/cohort/'+worker])
  extra=bind_stage_paths(extra,source,stage_source)
  index=command.index('--');command[index:index]=['--ro-bind',str(stage_source),'/tmp/inputs','--ro-bind',str(native),'/tmp/native','--ro-bind',str(W/'balanced16-physical-v2'),'/tmp/physical','--ro-bind',str(W/'balanced16-labels-v2'),'/tmp/boxes','--ro-bind',str(runtime_path),'/tmp/runtime-lock.json','--ro-bind',str(W),'/tmp/scientific','--ro-bind',str(R/'source-snapshots'),'/tmp/source-snapshots','--setenv','SUREAL_SOURCE_SNAPSHOT_STORE','/tmp/source-snapshots','--setenv','CUBLAS_WORKSPACE_CONFIG',':4096:8',*extra]
  with (directory/'live.log').open('w') as log:result=run_stage(command,package,dict(os.environ),log,timeout=stage_timeout(metrics))
  if result.returncode:raise RuntimeError(f'{name} failed; retained log: {directory}/live.log')
  validate_sources(package,pins,runtime,runtime)
  if any(sha(path)!=digest for path,digest in input_hashes.items()):raise ValueError('immutable stage inputs changed')
  if sha(manifest_path)!=manifest_sha or unique_payload_bytes(W)>15*1024**3 or unique_payload_bytes(output)>2*1024**3:raise ValueError('manifest or storage admission violated')
  receipt={'stage':name,'command':command,'exit_code':0,'source_hashes':pins,'runtime_lock':metric_runtime if metrics else runtime,'driver_hashes':old['driver_hashes'] if gpu else {},'manifest_sha256':manifest_sha,'expanded_closure_sha256':sha(closure),'historical_manifest_sha256':sha(historical),'input_hashes':input_hashes,'job_sha256':sha(stage_source/'job.json') if worker=='train_sustained.py' else None,'artifacts':{str(p):sha(p) for p in directory.rglob('*') if p.is_file()},'scope':'native engineering pilot only; sustained fitting/science/native APH pending'}
  receipt_path=R/(name+'-verified.json');receipt_path.write_text(json.dumps(receipt,indent=2)+'\n');receipts[name]={'path':str(receipt_path),'sha256':sha(receipt_path)};print('ADMITTED',name,flush=True)
 previous=None
 for step in [0,19,35]:
  (source/'job.json').write_text(json.dumps({'target_step':step,'retained_sha256':sha(previous/'checkpoint.pt') if previous else None}))
  directory=output/f'update-{step:02d}';stage(f'train-{step}','train_sustained.py',directory,['--ro-bind',str(previous),'/tmp/retained'] if previous else [])
  report=json.loads((directory/'check.json').read_text())
  if report['updates']!=step or report['stop_reason']!='sample' or not report['resource_gate_passed']:raise ValueError('pilot chunk not admitted')
  audit={'checkpoint_sha256':sha(directory/'checkpoint.pt'),'head_hashes':report['head_hashes'],'pilot_reference':step==35}
  if step==35:audit['previous_checkpoint_sha256']=sha(previous/'checkpoint.pt')
  (source/'audit.json').write_text(json.dumps(audit));audit_dir=R/f'audit-{step:02d}';stage(f'audit-{step}','replay_sustained.py',audit_dir,['--ro-bind',str(directory),'/tmp/retained',*(['--ro-bind',str(previous),'/tmp/previous'] if step==35 else [])])
  replay=json.loads((audit_dir/'replay.json').read_text())
  if len(replay['checked_frames'])!=16 or step==35 and len(replay['pilot_reference_checks'])!=2:raise ValueError('mandatory full16/restart audit missing')
  (source/'loss-audit.json').write_text(json.dumps({'manifest_sha256':manifest_sha,'report_sha256':sha(directory/'check.json'),'head_hashes':report['head_hashes']}))
  # The loss worker reads retained report/heads through /source; stage inputs
  # remain separately immutable at /tmp/inputs.
  stage(f'literal-loss-{step}','audit_sustained_loss.py',R/f'loss-{step:02d}',['--ro-bind',str(directory),'/source'],gpu=False)
  (source/'export-audit.json').write_text(json.dumps({'manifest_sha256':manifest_sha,'anchor_templates_sha256':sha(source/'anchor-templates.json'),'head_hashes':report['head_hashes']}))
  prepared=R/f'prepared-{step:02d}';stage(f'export-{step}','prepare_sustained_v3.py',prepared,['--ro-bind',str(directory/'heads'),'/source'],gpu=False)
  export_receipt=json.loads(Path(receipts[f'export-{step}']['path']).read_text());export_receipt['inputs']={p:h for p,h in export_receipt['input_hashes'].items() if Path(p).name in {'manifest.json','anchor-templates.json','export-audit.json'}};export_receipt['validation']=json.loads((prepared/'preparation.json').read_text());(source/'score-receipt.json').write_text(json.dumps(export_receipt,indent=2)+'\n');(source/'expected.json').write_text(json.dumps({'receipt':export_receipt,'receipt_sha256':sha(source/'score-receipt.json')}))
  stage(f'proposals-{step}','audit_proposals_sustained_v3.py',R/f'proposal-audit-{step:02d}',['--ro-bind',str(prepared),'/source','--ro-bind',str(directory/'heads'),'/tmp/heads','--ro-bind',str(source/'score-receipt.json'),'/tmp/score-receipt.json','--ro-bind',str(source/'expected.json'),'/tmp/expected.json'],gpu=False)
  scored=R/f'scored-{step:02d}';stage(f'score-{step}','metrics_sustained_v3.py',scored,['--ro-bind',str(prepared),'/source'],gpu=False,metrics=True)
  score_receipt=json.loads(Path(receipts[f'score-{step}']['path']).read_text());score_receipt['parent_artifacts']=export_receipt['artifacts'];score_receipt['validation']=json.loads((scored/'check.json').read_text());(source/'score-receipt.json').write_text(json.dumps(score_receipt,indent=2)+'\n');(source/'expected.json').write_text(json.dumps({'receipt':score_receipt,'receipt_sha256':sha(source/'score-receipt.json')}))
  stage(f'metrics-audit-{step}','audit_metrics_sustained_v3.py',R/f'metric-audit-{step:02d}',['--ro-bind',str(prepared),'/source','--ro-bind',str(scored),'/tmp/scored','--ro-bind',str(source/'score-receipt.json'),'/tmp/score-receipt.json','--ro-bind',str(source/'expected.json'),'/tmp/expected.json'],gpu=False,metrics=True)
  previous=directory
 final={'run_directory':str(R),'output_directory':str(output),'manifest_sha256':manifest_sha,'stage_receipts':receipts,'scope':'native baseline0/19/35 exact state/heads/reference pilot; no sustained-fit or scientific acceptance'}
 (P/'research'/f'balanced16-sustained-admission-{a.run_id}-verified.json').write_text(json.dumps(final,indent=2)+'\n');print('PASS native baseline admission pilot; sustained controller/HDFS gates remain',flush=True)
if __name__=='__main__':main()
