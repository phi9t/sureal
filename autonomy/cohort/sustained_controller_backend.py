"""Source-frozen live native backend for the four-case sustained workflow."""
import json,os,re,shutil,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path[:0]=[str(P),str(P/'architecture')]
from insula.entry import launch_plan
from insula.runtime_identity import verify_rootfs
from resources.scientific_payload import sha,unique_payload_bytes
from resources.scientific_budget import reserve_write
from cohort.sustained_contract import validate_contract
from cohort.sustained_sources import snapshot_sources,validate_sources
from cohort.sustained_stage_inputs import freeze_inputs,bind_stage_paths
from cohort.sustained_scoring_budget import stage_timeout
from cohort.sustained_checkpoint_inventory import freeze_checkpoint_inventory
from cohort.sustained_admission import admit_sample
from cohort.sustained_controller_sources import freeze_host_sources,validate_host_sources
C=Path.home()/'.cache/waystone/waymo-perception';W=C/'scientific-processing'

def write(path,value):
 path=Path(path);temporary=path.with_suffix(path.suffix+'.tmp')
 with temporary.open('w') as stream:json.dump(value,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
 os.replace(temporary,path)
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)

class NativeBackend:
 def __init__(self,run_id,recipe,lock,*,resume=False):
  if re.fullmatch('[A-Za-z0-9]{1,64}',run_id) is None or recipe not in {'baseline','residual_bev','class_balanced','prior_bias'}:raise ValueError('declared run ID and recipe required')
  self.lock=lock;self.recipe=recipe;self.run_id=run_id;case='balanced16-sustained-'+recipe.replace('_','-')+'-'+run_id;self.R=C/'insula'/case;self.output=W/case
  historical=C/'insula/cohort16-baseline-balanced20261002a/run.json';frames=json.loads(historical.read_text())['manifest']['frames'];candidate=json.loads((P/'research/balanced16-sustained.candidate.json').read_text());validate_contract(candidate,[{k:f[k] for k in ['identity','split','sha256']} for f in frames]);self.native=W/'balanced16-native-v2'
  for frame in frames:
   directory=Path(frame['relative_directory'])
   if directory.is_absolute() or '..' in directory.parts:raise ValueError('safe native frame required')
   for name,digest in frame['sha256'].items():
    if sha(self.native/directory/name)!=digest:raise ValueError('original native frame changed')
  self.old=json.loads((C/'detector-gpu-live-a/receipt.json').read_text());self.runtime=self.old['runtime_lock'];self.metric_runtime=json.loads(Path(str(C/'metrics-rootfs')+'.lock.json').read_text())
  verify_rootfs(C/'gpu-rootfs',self.runtime['rootfs_sha256']);verify_rootfs(C/'metrics-rootfs',self.metric_runtime['rootfs_sha256'])
  for path,digest in self.old['driver_hashes'].items():
   if sha(path)!=digest:raise ValueError('original GPU driver changed')
  self.package=self.R/'code';self.source=self.R/'input';self.runtime_path=self.R/'runtime-lock.json';self.verifier=self.R/'verifier'
  if resume:
   run=json.loads((self.R/'run.json').read_text());self.host_pins=run['host_source_pins'];self.pins=run['source_hashes'];self.manifest=json.loads((self.source/'manifest.json').read_text());self.manifest_sha=run['manifest_sha256'];self.anchor_sha=run['anchor_templates_sha256']
   if run['run_id']!=run_id or run['recipe']!=recipe or self.manifest['candidate']!=candidate or self.manifest['frames']!=frames or self.manifest['recipe']!=recipe or self.manifest['runtime_lock']!=self.runtime:raise ValueError('frozen resumed identity differs')
  else:
   reserve_write(W,2*1024**3);self.R.mkdir();self.output.mkdir();self.package.mkdir();self.source.mkdir();self.verifier.mkdir();self.host_pins=freeze_host_sources(P,self.R/'host-source')
   for folder in ['pipeline','gpu','tier1','cohort','evidence']:
    for path in (P/folder).rglob('*.py'):
     if '__pycache__' in path.parts:continue
     destination=self.package/path.relative_to(P);destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,destination)
   self.pins=snapshot_sources(self.package,self.R/'source-snapshots');self.manifest={'candidate':candidate,'frames':frames,'recipe':recipe,'source_hashes':self.pins,'runtime_lock':self.runtime};write(self.source/'manifest.json',self.manifest);self.manifest_sha=sha(self.source/'manifest.json');write(self.runtime_path,self.runtime)
   anchors=P/'research/training-anchor-templates.candidate.json';anchor_receipt=json.loads((P/'research/training-anchor-candidate-verified.json').read_text())
   if sha(anchors)!=anchor_receipt['expected']['candidate_sha256']:raise ValueError('admitted anchor templates changed')
   self.anchor_sha=anchor_receipt['expected']['candidate_sha256'];shutil.copyfile(anchors,self.source/'anchor-templates.json')
   for name in ['audit_sustained_transition.py','sustained_chunk_reference.py']:shutil.copyfile(self.package/'cohort'/name,self.verifier/name)
   write(self.R/'run.json',{'run_id':run_id,'recipe':recipe,'manifest_sha256':self.manifest_sha,'source_hashes':self.pins,'host_source_pins':self.host_pins,'anchor_templates_sha256':self.anchor_sha,'scope':'training-only fixed16 one-factor case; no heldout promotion'})
  self.verifier_pins={str(p):sha(p) for p in self.verifier.iterdir()};self.guard()
 def guard(self):
  validate_host_sources(P,self.host_pins);validate_sources(self.package,self.pins,self.runtime,self.runtime)
  admitted_anchor=json.loads((P/'research/training-anchor-candidate-verified.json').read_text())['expected']['candidate_sha256']
  if self.anchor_sha!=admitted_anchor or sha(self.source/'anchor-templates.json')!=self.anchor_sha:raise ValueError('externally admitted decoder anchors changed')
  source_pins=self.pins['source_pins']
  if sha(self.source/'manifest.json')!=self.manifest_sha or json.loads(self.runtime_path.read_text())!=self.runtime or set(Path(p).name for p in self.verifier_pins)!={'audit_sustained_transition.py','sustained_chunk_reference.py'} or any(sha(p)!=h or h!=source_pins['cohort/'+Path(p).name] for p,h in self.verifier_pins.items()):raise ValueError('frozen manifest/runtime/verifier changed')
  if unique_payload_bytes(W)>15*1024**3 or unique_payload_bytes(self.output)>2*1024**3:raise ValueError('scientific/case storage cap exceeded')
 def stage(self,name,worker,directory,extra,*,gpu=True,metrics=False,logical_step=None):
  from experiment_runner import run_stage
  self.guard();receipt_path=self.R/(name+'-verified.json')
  if receipt_path.exists():
   receipt=json.loads(receipt_path.read_text());self.check_stage(receipt)
   if receipt['requested_stage']!=name or receipt['output_directory']!=str(directory):raise ValueError('completed stage identity differs')
   return receipt_path
  if directory.exists():raise RuntimeError('unfinished stage retained; automatic restart forbidden: '+str(directory))
  directory.mkdir();stage_source,input_hashes=freeze_inputs(self.source,self.R/(name+'-input'));command=self.old['checks'][0]['command'].copy()
  if gpu:
   for target,path in [('/experiment',self.package),('/source',stage_source),('/outputs',directory)]:command[command.index(target)-1]=str(path)
   command[-1]='/tmp/verifier/audit_sustained_transition.py' if worker=='audit_sustained_transition.py' else '/experiment/cohort/'+worker
  else:command=launch_plan(C/('metrics-rootfs' if metrics else 'gpu-rootfs'),self.package,stage_source,directory,['python' if metrics else '/opt/waymo/bin/python','/experiment/cohort/'+worker])
  extra=bind_stage_paths(extra,self.source,stage_source);index=command.index('--');command[index:index]=['--ro-bind',str(stage_source),'/tmp/inputs','--ro-bind',str(self.native),'/tmp/native','--ro-bind',str(W/'balanced16-physical-v2'),'/tmp/physical','--ro-bind',str(W/'balanced16-labels-v2'),'/tmp/boxes','--ro-bind',str(self.runtime_path),'/tmp/runtime-lock.json','--ro-bind',str(W),'/tmp/scientific','--ro-bind',str(self.R/'source-snapshots'),'/tmp/source-snapshots','--setenv','SUREAL_SOURCE_SNAPSHOT_STORE','/tmp/source-snapshots','--setenv','CUBLAS_WORKSPACE_CONFIG',':4096:8',*extra]
  with (directory/'live.log').open('w') as log:result=run_stage(command,self.package,dict(os.environ),log,timeout=stage_timeout(metrics))
  if result.returncode:raise RuntimeError('failed native stage retained: '+name)
  self.guard();actual_step=json.loads((directory/'check.json').read_text())['updates'] if worker=='train_sustained.py' else logical_step
  semantic=name if actual_step is None else name.rsplit('-',1)[0]+'-'+str(actual_step)
  receipt={'stage':semantic,'requested_stage':name,'command':command,'output_directory':str(directory),'exit_code':0,'source_hashes':self.pins,'runtime_lock':self.metric_runtime if metrics else self.runtime,'driver_hashes':self.old['driver_hashes'] if gpu else {},'verifier_source_pins':self.verifier_pins if worker=='audit_sustained_transition.py' else {},'manifest_sha256':self.manifest_sha,'input_hashes':input_hashes,'artifacts':{str(p):sha(p) for p in directory.rglob('*') if p.is_file()},'scope':'source-frozen live checkpoint stage; full downstream admission required'};self.check_stage(receipt);write(receipt_path,receipt);print('ADMITTED',self.recipe,name,flush=True);return receipt_path
 def check_stage(self,receipt,*,released_root=None):
  if type(receipt['exit_code']) is not int or receipt['exit_code']!=0 or receipt['manifest_sha256']!=self.manifest_sha or receipt['source_hashes']!=self.pins or not receipt['artifacts'] or not receipt['input_hashes']:raise ValueError('complete stage identity/input/output bindings required')
  stage=receipt['stage'].rsplit('-',1)[0];workers={'train':'train_sustained.py','audit':'audit_sustained_transition.py','literal-loss':'audit_sustained_loss.py','export':'prepare_sustained_v3.py','proposals':'audit_proposals_sustained_v3.py','score':'metrics_sustained_v3.py','metrics-audit':'audit_metrics_sustained_v3.py'}
  if stage not in workers:raise ValueError('unknown native stage')
  metric=stage in {'score','metrics-audit'};gpu=stage in {'train','audit'};command=receipt['command'];entry='/tmp/verifier/'+workers[stage] if stage=='audit' else '/experiment/cohort/'+workers[stage]
  if command[-1]!=entry or receipt['runtime_lock']!=(self.metric_runtime if metric else self.runtime) or receipt['driver_hashes']!=(self.old['driver_hashes'] if gpu else {}) or receipt['verifier_source_pins']!=(self.verifier_pins if stage=='audit' else {}):raise ValueError('native worker/runtime/driver/verifier differs')
  if command[command.index('/experiment')-1]!=str(self.package) or command[command.index('/outputs')-1]!=receipt['output_directory']:raise ValueError('native code/output mount differs')
  if command[command.index('/tmp/source-snapshots')-1]!=str(self.R/'source-snapshots') or command[command.index('SUREAL_SOURCE_SNAPSHOT_STORE')+1]!='/tmp/source-snapshots':raise ValueError('source snapshot store mount differs')
  inputs=self.R/(receipt['requested_stage']+'-input')
  if receipt['input_hashes'].get(str(inputs/'manifest.json'))!=self.manifest_sha or command[command.index('/source')-1]!=str(inputs) or command[command.index('/tmp/inputs')-1]!=str(inputs):raise ValueError('exact immutable stage manifest/input mounts required')
  for group in ['input_hashes','driver_hashes','verifier_source_pins','artifacts']:
   for path,digest in receipt[group].items():
    if released_root is not None and Path(path).is_relative_to(released_root):continue
    value=Path(path)
    if not value.is_file() or any(p.is_symlink() for p in [value,*value.parents]) or sha(value)!=digest:raise ValueError('stage evidence changed: '+path)
 def train_and_admit(self,previous,target):
  previous_root=Path(previous['root']) if previous else None;previous_sha=previous['checkpoint_sha256'] if previous else None;start=previous['step'] if previous else 0
  write(self.source/'job.json',{'target_step':target,'retained_sha256':previous_sha});directory=self.output/f'update-{target:02d}';refs={}
  refs['train']=self.stage(f'train-{target}','train_sustained.py',directory,['--ro-bind',str(previous_root),'/tmp/retained'] if previous else [])
  report=json.loads((directory/'check.json').read_text());step=report['updates']
  if not report['resource_gate_passed']:raise RuntimeError('resource-censored producer retained; no quality promotion')
  checkpoint_sha=sha(directory/'checkpoint.pt');audit={'checkpoint_sha256':checkpoint_sha,'head_hashes':report['head_hashes'],'pilot_reference':False};write(self.source/'audit.json',audit);write(self.source/'transition.json',{'manifest_sha256':self.manifest_sha,'checkpoint_sha256':checkpoint_sha,'previous_checkpoint_sha256':previous_sha,'report_sha256':sha(directory/'check.json'),'start_step':start,'terminal_step':step})
  audited=self.R/f'audit-{target:02d}';refs['audit']=self.stage(f'audit-{target}','audit_sustained_transition.py',audited,['--ro-bind',str(self.verifier),'/tmp/verifier','--ro-bind',str(directory),'/tmp/retained',*(['--ro-bind',str(previous_root),'/tmp/previous'] if previous else [])],logical_step=step)
  write(self.source/'loss-audit.json',{'manifest_sha256':self.manifest_sha,'report_sha256':sha(directory/'check.json'),'head_hashes':report['head_hashes']});lossdir=self.R/f'loss-{target:02d}';refs['literal-loss']=self.stage(f'literal-loss-{target}','audit_sustained_loss.py',lossdir,['--ro-bind',str(directory),'/source'],gpu=False,logical_step=step)
  write(self.source/'export-audit.json',{'manifest_sha256':self.manifest_sha,'anchor_templates_sha256':self.anchor_sha,'head_hashes':report['head_hashes']});prepared=self.R/f'prepared-{target:02d}';refs['export']=self.stage(f'export-{target}','prepare_sustained_v3.py',prepared,['--ro-bind',str(directory/'heads'),'/source'],gpu=False,logical_step=step)
  export=json.loads(refs['export'].read_text());export['inputs']={p:h for p,h in export['input_hashes'].items() if Path(p).name in {'manifest.json','anchor-templates.json','export-audit.json'}};export['validation']=json.loads((prepared/'preparation.json').read_text());write(self.source/'score-receipt.json',export);write(self.source/'expected.json',{'receipt':export,'receipt_sha256':sha(self.source/'score-receipt.json')});proposals=self.R/f'proposal-audit-{target:02d}';refs['proposals']=self.stage(f'proposals-{target}','audit_proposals_sustained_v3.py',proposals,['--ro-bind',str(prepared),'/source','--ro-bind',str(directory/'heads'),'/tmp/heads','--ro-bind',str(self.source/'score-receipt.json'),'/tmp/score-receipt.json','--ro-bind',str(self.source/'expected.json'),'/tmp/expected.json'],gpu=False,logical_step=step)
  scored=self.R/f'scored-{target:02d}';refs['score']=self.stage(f'score-{target}','metrics_sustained_v3.py',scored,['--ro-bind',str(prepared),'/source'],gpu=False,metrics=True,logical_step=step)
  score=json.loads(refs['score'].read_text());score['parent_artifacts']=export['artifacts'];score['validation']=json.loads((scored/'check.json').read_text());write(self.source/'score-receipt.json',score);write(self.source/'expected.json',{'receipt':score,'receipt_sha256':sha(self.source/'score-receipt.json')});metricdir=self.R/f'metric-audit-{target:02d}';refs['metrics-audit']=self.stage(f'metrics-audit-{target}','audit_metrics_sustained_v3.py',metricdir,['--ro-bind',str(prepared),'/source','--ro-bind',str(scored),'/tmp/scored','--ro-bind',str(self.source/'score-receipt.json'),'/tmp/score-receipt.json','--ro-bind',str(self.source/'expected.json'),'/tmp/expected.json'],gpu=False,metrics=True,logical_step=step)
  sample=admit_sample(manifest=self.manifest,manifest_sha256=self.manifest_sha,producer=report,producer_sha256=sha(directory/'check.json'),replay=json.loads((audited/'replay.json').read_text()),transition=json.loads((audited/'transition.json').read_text()),previous_checkpoint_sha256=previous_sha,start_step=start,loss=json.loads((lossdir/'check.json').read_text()),proposals=json.loads((proposals/'check.json').read_text()),score=score['validation'],metric=json.loads((metricdir/'check.json').read_text()))
  final=self.R/f'checkpoint-{target:02d}-admitted.json';write(final,{'output_directory':str(directory),'manifest_path':str(self.source/'manifest.json'),'manifest_sha256':self.manifest_sha,'step':step,'stage_receipts':{name:{'path':str(path),'sha256':sha(path)} for name,path in refs.items()},'scope':'full seven-stage native engineering checkpoint; no heldout promotion'});freeze_checkpoint_inventory(directory,final,sha(final));reportcopy=self.R/f'producer-report-{target:02d}.json';shutil.copyfile(directory/'check.json',reportcopy)
  return {'step':step,'target_step':target,'root':str(directory),'checkpoint_sha256':checkpoint_sha,'final_path':str(final),'final_sha256':sha(final),'report':report,'report_snapshot':str(reportcopy),'report_sha256':sha(reportcopy),'sample':sample,'released':False}
 def persist(self,records,decision=None,diagnostic=None):
  self.guard();old=json.loads((self.R/'state.json').read_text()) if (self.R/'state.json').exists() else {}
  write(self.R/'state.json',{'manifest_sha256':self.manifest_sha,'records':records,'decision':decision if decision is not None else old.get('decision'),'diagnostic':diagnostic if diagnostic is not None else old.get('diagnostic'),'scope':'training-only admitted samples; scientific promotion separate'})
  livepath=P/'research'/f'balanced16-sustained-{self.run_id}-live.json';live=json.loads(livepath.read_text()) if livepath.exists() else {'run_id':self.run_id,'cases':{},'scope':'fixed16 training-only live checkpoint status; no heldout scientific claim'}
  live['cases'][self.recipe]={'case_directory':str(self.R),'manifest_sha256':self.manifest_sha,'samples':[r['sample'] for r in records],'cumulative_train_seconds':records[-1]['report']['cumulative_train_seconds'] if records else 0,'decision':decision if decision is not None else old.get('decision'),'retained_checkpoints':[r['target_step'] for r in records if not r['released']],'latest_source_admission':{'path':records[-1]['final_path'],'sha256':records[-1]['final_sha256']} if records else None};write(livepath,live)
 def validate_resume(self,records):
  self.guard();previous=None
  for record in records:
   self.check_record(record,previous);previous=record
  state=json.loads((self.R/'state.json').read_text()) if (self.R/'state.json').exists() else {}
  if state and state['manifest_sha256']!=self.manifest_sha:raise ValueError('resume state manifest differs')
  if state.get('diagnostic') is not None:self.check_record(state['diagnostic'],previous)
 def check_record(self,record,previous):
  if sha(record['final_path'])!=record['final_sha256'] or sha(record['report_snapshot'])!=record['report_sha256'] or json.loads(Path(record['report_snapshot']).read_text())!=record['report']:raise ValueError('resumed checkpoint identity changed')
  final=json.loads(Path(record['final_path']).read_text());target=record['target_step'];step=record['step'];root=Path(record['root']);refs=final['stage_receipts']
  if root!=self.output/f'update-{target:02d}' or final['output_directory']!=str(root) or final['step']!=step or final['manifest_sha256']!=self.manifest_sha or final['manifest_path']!=str(self.source/'manifest.json') or record['report']['requested_updates']!=target or set(refs)!={'train','audit','literal-loss','export','proposals','score','metrics-audit'}:raise ValueError('resumed final/producer/scope differs')
  stage_records={}
  for name,ref in refs.items():
   if sha(ref['path'])!=ref['sha256']:raise ValueError('resumed stage parent changed')
   value=json.loads(Path(ref['path']).read_text());self.check_stage(value,released_root=root if record['released'] else None)
   if value['stage']!=f'{name}-{step}' or value['requested_stage']!=f'{name}-{target}':raise ValueError('resumed stage actual/requested step differs')
   stage_records[name]=value
  train=stage_records['train']
  if train['artifacts'][str(root/'check.json')]!=record['report_sha256'] or train['artifacts'][str(root/'checkpoint.pt')]!=record['checkpoint_sha256']:raise ValueError('snapshot report/checkpoint does not match admitted producer')
  def report(name,filename):return json.loads((Path(stage_records[name]['output_directory'])/filename).read_text())
  sample=admit_sample(manifest=self.manifest,manifest_sha256=self.manifest_sha,producer=record['report'],producer_sha256=record['report_sha256'],replay=report('audit','replay.json'),transition=report('audit','transition.json'),previous_checkpoint_sha256=previous['checkpoint_sha256'] if previous else None,start_step=previous['step'] if previous else 0,loss=report('literal-loss','check.json'),proposals=report('proposals','check.json'),score=report('score','check.json'),metric=report('metrics-audit','check.json'))
  if sample!=record['sample']:raise ValueError('resumed native sample differs from actual admitted reports')
  if not record['released']:freeze_checkpoint_inventory(root,record['final_path'],record['final_sha256'])
  else:
   pub=record['publication'];release=json.loads(Path(pub['release_path']).read_text());publication=json.loads(Path(pub['publication_path']).read_text())
   if sha(pub['publication_path'])!=pub['publication_sha256'] or sha(pub['release_path'])!=pub['release_sha256'] or release['publication_receipt_sha256']!=pub['publication_sha256'] or publication['parent_receipts'].get(record['final_path'])!=record['final_sha256'] or publication['independent_admission']['exit_code']!=0 or publication['independent_admission']['validation']['whole_member_union_exact'] is not True or any(Path(e['local_path']).exists() for e in release['released']):raise ValueError('resumed retention/release changed')
 def publish_and_release(self,record):
  self.guard();before={p for p in (C/'insula').glob('hdfs-retention-*')};command=[sys.executable,str(P/'cohort/publish_sustained_checkpoint.py'),'--receipt',record['final_path'],'--receipt-sha256',record['final_sha256'],'--release','--lock-fd',str(self.lock.fileno())];log=self.R/f'retention-{record["step"]:02d}.log'
  with log.open('w') as stream:result=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,pass_fds=(self.lock.fileno(),),timeout=3600)
  if result.returncode:raise RuntimeError('checkpoint HDFS preservation failed; next training forbidden')
  new={p for p in (C/'insula').glob('hdfs-retention-*')}-before
  if len(new)!=1:raise ValueError('unique current checkpoint publication required')
  directory=new.pop();publication=directory/'verified-publication.json';release=directory/'release-completed.json';value=json.loads(publication.read_text());released=json.loads(release.read_text())
  if released['publication_receipt_sha256']!=sha(publication) or value['parent_receipts'].get(record['final_path'])!=record['final_sha256'] or value['independent_admission']['exit_code']!=0 or value['independent_admission']['validation']['whole_member_union_exact'] is not True or any(Path(e['local_path']).exists() for e in released['released']):raise ValueError('exact checkpoint release/independent union required')
  self.guard();return {'publication_path':str(publication),'publication_sha256':sha(publication),'release_path':str(release),'release_sha256':sha(release),'hdfs_manifest_uri':value['publication_manifest_hdfs_uri'],'command':command,'log_sha256':sha(log)}
