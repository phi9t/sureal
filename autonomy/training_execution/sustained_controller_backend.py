"""Source-frozen live native backend for the four-case sustained workflow."""
import json,os,re,shutil,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parents[1]
from blob_store.core import BlobStore,blob_adapter_from_descriptor
from insula.entry import launch_plan
from insula.runtime_identity import verify_rootfs
from insula.runtime_roots import current_cpu_rootfs, current_gpu_rootfs, current_metrics_rootfs
from retention.publication import audit as audit_publication
from resources.scientific_payload import sha,unique_payload_bytes
from resources.scientific_budget import reserve_write
from detection.sustained_contract import validate_contract
from training_execution.sustained_sources import cache_snapshot_for_runtime,snapshot_sources,source_pin,validate_sources
from training_execution.sustained_stage_inputs import freeze_inputs,bind_stage_paths
from resources.sustained_scoring_budget import stage_timeout
from retention.sustained_checkpoint_inventory import freeze_checkpoint_inventory
from training_execution.sustained_admission import admit_sample
from training_execution.sustained_controller_sources import freeze_host_sources,validate_host_sources
from retention.publication_sources import freeze_checkpoint_sources as freeze_checkpoint_publisher_sources,validate_checkpoint_sources as validate_checkpoint_publisher_sources
from evidence.source_snapshot import source_snapshot_package_root
C=Path.home()/'.cache/waystone/waymo-perception';W=C/'scientific-processing'
GPU_ROOT=current_gpu_rootfs(C);CPU_ROOT=current_cpu_rootfs(C);METRICS_ROOT=current_metrics_rootfs(C)
WORKER_ENTRIES={
 'train_sustained.py':'/experiment/training_execution/train_sustained.py',
 'audit_sustained_loss.py':'/experiment/training_execution/audit_sustained_loss.py',
 'prepare_sustained_v3.py':'/experiment/evaluation/prepare_sustained_v3.py',
 'audit_proposals_sustained_v3.py':'/experiment/evaluation/audit_proposals_sustained_v3.py',
 'metrics_sustained_v3.py':'/experiment/evaluation/metrics_sustained_v3.py',
 'audit_metrics_sustained_v3.py':'/experiment/evaluation/audit_metrics_sustained_v3.py',
}

def current_gpu_runtime_lock(_historical_receipt=None):
 lock=json.loads(Path(str(GPU_ROOT)+'.lock.json').read_text());verify_rootfs(GPU_ROOT,lock['rootfs_sha256']);return lock

def rebind_rootfs_mount(command,root):
 command=list(command)
 for index in range(len(command)-2):
  if command[index]=='--ro-bind' and command[index+2]=='/':
   command[index+1]=str(root);return command
 raise ValueError('rootfs mount required in native GPU command')

def _native_release_plan(publication,release=None):
 plan=publication.get('release_plan')
 if plan is None and release is not None:plan=release.get('released')
 if not isinstance(plan,list) or not plan:raise ValueError('complete native release plan required')
 return plan

def publication_matches_record(record,publication):
 try:return publication['parent_receipts'].get(record['final_path'])==record['final_sha256']
 except (KeyError,TypeError,AttributeError):return False

def _is_blob_publication(publication):
 return isinstance(publication,dict) and {'schema_version','store_descriptor','tool_sha256','verified_by_readback','blobs'}<=set(publication)

def _expected_release_members(record):
 try:
  root=Path(record['root']);final=json.loads(Path(record['final_path']).read_text())
  train_ref=final['stage_receipts']['train'];train=json.loads(Path(train_ref['path']).read_text())
  if sha(train_ref['path'])!=train_ref['sha256'] or train['stage']!=f'train-{record["step"]}':
   raise ValueError('train receipt changed')
  members={}
  for path,digest in train['artifacts'].items():
   path=Path(path)
   if path.is_relative_to(root):members[path.relative_to(root).as_posix()]=digest
  required={'checkpoint.pt':record['checkpoint_sha256'],'check.json':record['report_sha256'],'live.log':train['artifacts'][str(root/'live.log')]}
  required.update({'heads/'+name:digest for name,digest in record['report']['head_hashes'].items()})
  expected_names={'checkpoint.pt','check.json','live.log'}|{f'heads/heads-{i:02d}.npz' for i in range(16)}
  if set(required)!=expected_names:
   raise ValueError('complete native release member set required')
  if members!=required:raise ValueError('native release member digests differ from admitted train receipt')
  return members
 except (KeyError,TypeError,OSError,AttributeError,json.JSONDecodeError) as error:
  raise ValueError('complete admitted native release inventory required') from error

def _publication_release_members(publication,expected):
 try:
  if publication['source_sha256']!=expected:
   raise ValueError('native publication inventory differs from admitted train receipt')
  members={}
  for chunk in publication['chunks']:
   archive=chunk['archive_hdfs_uri']
   if not isinstance(archive,str) or not archive.startswith('hdfs://'):
    raise ValueError('native publication archive URI required')
   for member in chunk['manifest']['members']:
    name=member['path']
    if (name in members or expected.get(name)!=member['sha256'] or
        type(member.get('bytes')) is not int or member['bytes']<0):
     raise ValueError('native publication chunk inventory differs from admitted train receipt')
    members[name]={'path':name,'sha256':member['sha256'],'bytes':member['bytes'],'archive_hdfs_uri':archive}
  if set(members)!=set(expected):
   raise ValueError('native publication chunk inventory incomplete')
  return members
 except (KeyError,TypeError,AttributeError) as error:
  raise ValueError('complete native publication chunk inventory required') from error

def _blob_publication_release_members(publication,expected):
 try:
  store=BlobStore(blob_adapter_from_descriptor(publication['store_descriptor']))
  result=audit_publication(publication,store=store)
  inventory=result['inventory']
  if set(inventory)!=set(expected):
   raise ValueError('native publication inventory differs from admitted train receipt')
  published={}
  for chunk in result['chunk_inventories']:
   blob=chunk['blob']
   for name,member in chunk['inventory'].items():
    if name in published or expected.get(name)!=member['sha256']:
     raise ValueError('native publication chunk inventory differs from admitted train receipt')
    published[name]={'path':name,'sha256':member['sha256'],'bytes':member['bytes'],'archive_blob_key':blob['key']}
  if set(published)!=set(expected):
   raise ValueError('native publication chunk inventory incomplete')
  return published
 except (KeyError,TypeError,AttributeError) as error:
  raise ValueError('complete native blob publication receipt required') from error

def _derived_blob_release_plan(record,published):
 root=Path(record['root'])
 return [{**published[name],'local_path':str(root/name)} for name in sorted(published)]

def validate_native_publication_release(record,publication_path,release_path=None,*,completed):
 publication_path=Path(publication_path);release_path=Path(release_path) if release_path is not None else None
 try:
  if not publication_path.is_file() or publication_path.is_symlink():raise ValueError('regular native publication evidence required')
  publication=json.loads(publication_path.read_text())
  release=None
  if completed:
   if release_path is None or not release_path.is_file() or release_path.is_symlink():raise ValueError('regular native release completion evidence required')
   release=json.loads(release_path.read_text())
   if release['publication_receipt_sha256']!=sha(publication_path):raise ValueError('native release does not bind publication bytes')
  root=Path(record['root'])
  if root.is_symlink():raise ValueError('regular native release root required')
  expected=_expected_release_members(record)
  if _is_blob_publication(publication):
   published=_blob_publication_release_members(publication,expected)
   plan=release['released'] if completed else _derived_blob_release_plan(record,published)
   if not isinstance(plan,list) or not plan:raise ValueError('complete native release plan required')
  else:
   if not publication_matches_record(record,publication):raise ValueError('native publication parent differs')
   admission=publication['independent_admission']
   if admission['exit_code']!=0 or admission['validation']['whole_member_union_exact'] is not True:raise ValueError('independent native recovery admission required')
   plan=_native_release_plan(publication,release)
   if completed and release['released']!=plan:raise ValueError('native release plan changed')
   published=_publication_release_members(publication,expected)
  seen=set()
  for entry in plan:
   local=Path(entry['local_path'])
   if not local.is_absolute() or any(p.is_symlink() for p in [local,*local.parents]):raise ValueError('regular native release member path required')
   try:relative=local.relative_to(root).as_posix()
   except ValueError as error:raise ValueError('native release member outside checkpoint root') from error
   required=published.get(relative)
   if (entry.get('path',relative)!=relative or relative in seen or required is None or
       {key:entry.get(key) for key in required}!=required or
       re.fullmatch('[0-9a-f]{64}',entry['sha256']) is None):
    raise ValueError('exact native release member identity required')
   seen.add(relative)
   if completed:
    if local.exists():raise ValueError('released native payload member still exists')
   else:
    if not local.is_file() or local.is_symlink() or sha(local)!=entry['sha256']:raise ValueError('native release member changed before completion')
    if 'bytes' in entry and local.stat().st_size!=entry['bytes']:raise ValueError('native release member size changed')
  if seen!=set(expected):raise ValueError('complete native release inventory required')
  if completed and root.exists() and any(path.is_file() or path.is_symlink() for path in root.rglob('*')):
   raise ValueError('released native payload root retains files')
 except (KeyError,TypeError,OSError,AttributeError,json.JSONDecodeError) as error:
  raise ValueError('complete native publication/release evidence required') from error
 return publication,release,plan

def worker_entry(worker):
 try:return WORKER_ENTRIES[worker]
 except KeyError as error:raise ValueError('declared sustained worker required') from error

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
  self.old=json.loads((C/'detector-gpu-live-a/receipt.json').read_text());self.runtime=current_gpu_runtime_lock(self.old);self.cpu_runtime=json.loads(Path(str(CPU_ROOT)+'.lock.json').read_text());self.metric_runtime=json.loads(Path(str(METRICS_ROOT)+'.lock.json').read_text())
  verify_rootfs(CPU_ROOT,self.cpu_runtime['rootfs_sha256']);verify_rootfs(METRICS_ROOT,self.metric_runtime['rootfs_sha256'])
  for path,digest in self.old['driver_hashes'].items():
   if sha(path)!=digest:raise ValueError('original GPU driver changed')
  self.package=self.R/'code';self.source=self.R/'input';self.runtime_path=self.R/'runtime-lock.json';self.verifier=self.R/'verifier'
  if resume:
   run=json.loads((self.R/'run.json').read_text());self.package=Path(run.get('source_package_root',str(self.package)));self.host_pins=run['host_source_pins'];self.checkpoint_publisher_pins=run.get('checkpoint_publisher_source_pins',self.host_pins);self.pins=run['source_hashes'];self.manifest=json.loads((self.source/'manifest.json').read_text());self.manifest_sha=run['manifest_sha256'];self.anchor_sha=run['anchor_templates_sha256']
   if run['run_id']!=run_id or run['recipe']!=recipe or self.manifest['candidate']!=candidate or self.manifest['frames']!=frames or self.manifest['recipe']!=recipe or self.manifest['runtime_lock']!=self.runtime:raise ValueError('frozen resumed identity differs')
  else:
   reserve_write(W,2*1024**3);self.R.mkdir();self.output.mkdir();self.source.mkdir();self.verifier.mkdir();self.host_pins=freeze_host_sources(P,self.R/'host-source');self.checkpoint_publisher_pins=freeze_checkpoint_publisher_sources(P,self.R/'checkpoint-publisher-source')
   self.pins=snapshot_sources(P,destination=self.R/'code');self.package=Path(self.pins['source_snapshot_root'])/'autonomy';cache_snapshot_for_runtime(self.pins,self.R/'source-snapshots');self.manifest={'candidate':candidate,'frames':frames,'recipe':recipe,'source_hashes':self.pins,'runtime_lock':self.runtime};write(self.source/'manifest.json',self.manifest);self.manifest_sha=sha(self.source/'manifest.json');write(self.runtime_path,self.runtime)
   anchors=P/'research/training-anchor-templates.candidate.json';anchor_receipt=json.loads((P/'research/training-anchor-candidate-verified.json').read_text())
   if sha(anchors)!=anchor_receipt['expected']['candidate_sha256']:raise ValueError('admitted anchor templates changed')
   self.anchor_sha=anchor_receipt['expected']['candidate_sha256'];shutil.copyfile(anchors,self.source/'anchor-templates.json')
   for name in ['audit_sustained_transition.py','sustained_chunk_reference.py']:shutil.copyfile(self.package/'training_execution'/name,self.verifier/name)
   write(self.R/'run.json',{'run_id':run_id,'recipe':recipe,'manifest_sha256':self.manifest_sha,'source_hashes':self.pins,'host_source_pins':self.host_pins,'checkpoint_publisher_source_pins':self.checkpoint_publisher_pins,'source_package_root':str(self.package),'anchor_templates_sha256':self.anchor_sha,'scope':'training-only fixed16 one-factor case; no heldout promotion'})
  self.verifier_pins={str(p):sha(p) for p in self.verifier.iterdir()};self.guard()
 def guard(self):
  validate_host_sources(P,self.host_pins);validate_checkpoint_publisher_sources(P,self.checkpoint_publisher_pins);validate_sources(self.package,self.pins,self.runtime,self.runtime,materialize_missing=True)
  admitted_anchor=json.loads((P/'research/training-anchor-candidate-verified.json').read_text())['expected']['candidate_sha256']
  if self.anchor_sha!=admitted_anchor or sha(self.source/'anchor-templates.json')!=self.anchor_sha:raise ValueError('externally admitted decoder anchors changed')
  source_pins=self.pins['source_pins']
  if sha(self.source/'manifest.json')!=self.manifest_sha or json.loads(self.runtime_path.read_text())!=self.runtime or set(Path(p).name for p in self.verifier_pins)!={'audit_sustained_transition.py','sustained_chunk_reference.py'} or any(sha(p)!=h or h!=source_pin(self.pins,'training_execution/'+Path(p).name) for p,h in self.verifier_pins.items()):raise ValueError('frozen manifest/runtime/verifier changed')
  if unique_payload_bytes(W)>15*1024**3 or unique_payload_bytes(self.output)>2*1024**3:raise ValueError('scientific/case storage cap exceeded')
 def stage(self,name,worker,directory,extra,*,gpu=True,metrics=False,logical_step=None):
  from studies.architecture.experiment_runner import run_stage
  self.guard();receipt_path=self.R/(name+'-verified.json')
  if receipt_path.exists():
   receipt=json.loads(receipt_path.read_text());self.check_stage(receipt)
   if receipt['requested_stage']!=name or receipt['output_directory']!=str(directory):raise ValueError('completed stage identity differs')
   return receipt_path
  if directory.exists():raise RuntimeError('unfinished stage retained; automatic restart forbidden: '+str(directory))
  directory.mkdir();stage_source,input_hashes=freeze_inputs(self.source,self.R/(name+'-input'));command=self.old['checks'][0]['command'].copy()
  if gpu:
   command=rebind_rootfs_mount(command,GPU_ROOT)
   for target,path in [('/experiment',self.package),('/source',stage_source),('/outputs',directory)]:command[command.index(target)-1]=str(path)
   command[-1]='/tmp/verifier/audit_sustained_transition.py' if worker=='audit_sustained_transition.py' else worker_entry(worker)
  else:command=launch_plan(METRICS_ROOT if metrics else CPU_ROOT,self.package,stage_source,directory,['python',worker_entry(worker)])
  extra=bind_stage_paths(extra,self.source,stage_source);pythonpath=[] if 'PYTHONPATH' in command else ['--setenv','PYTHONPATH','/experiment'];index=command.index('--');command[index:index]=['--ro-bind',str(stage_source),'/tmp/inputs','--ro-bind',str(self.native),'/tmp/native','--ro-bind',str(W/'balanced16-physical-v2'),'/tmp/physical','--ro-bind',str(W/'balanced16-labels-v2'),'/tmp/boxes','--ro-bind',str(self.runtime_path),'/tmp/runtime-lock.json','--ro-bind',str(W),'/tmp/scientific','--ro-bind',str(self.R/'source-snapshots'),'/tmp/source-snapshots','--setenv','SUREAL_SOURCE_SNAPSHOT_STORE','/tmp/source-snapshots','--setenv','CUBLAS_WORKSPACE_CONFIG',':4096:8',*pythonpath,*extra]
  with (directory/'live.log').open('w') as log:result=run_stage(command,self.package,dict(os.environ),log,timeout=stage_timeout(metrics))
  if result.returncode:raise RuntimeError('failed native stage retained: '+name)
  self.guard();actual_step=json.loads((directory/'check.json').read_text())['updates'] if worker=='train_sustained.py' else logical_step
  semantic=name if actual_step is None else name.rsplit('-',1)[0]+'-'+str(actual_step)
  stage_runtime=self.metric_runtime if metrics else self.runtime if gpu else self.cpu_runtime
  receipt={'stage':semantic,'requested_stage':name,'command':command,'output_directory':str(directory),'exit_code':0,'source_hashes':self.pins,'runtime_lock':stage_runtime,'driver_hashes':self.old['driver_hashes'] if gpu else {},'verifier_source_pins':self.verifier_pins if worker=='audit_sustained_transition.py' else {},'manifest_sha256':self.manifest_sha,'input_hashes':input_hashes,'artifacts':{str(p):sha(p) for p in directory.rglob('*') if p.is_file()},'scope':'source-frozen live checkpoint stage; full downstream admission required'};self.check_stage(receipt);write(receipt_path,receipt);print('ADMITTED',self.recipe,name,flush=True);return receipt_path
 def check_stage(self,receipt,*,released_root=None):
  if type(receipt['exit_code']) is not int or receipt['exit_code']!=0 or receipt['manifest_sha256']!=self.manifest_sha or receipt['source_hashes']!=self.pins or not receipt['artifacts'] or not receipt['input_hashes']:raise ValueError('complete stage identity/input/output bindings required')
  stage=receipt['stage'].rsplit('-',1)[0];workers={'train':'train_sustained.py','audit':'audit_sustained_transition.py','literal-loss':'audit_sustained_loss.py','export':'prepare_sustained_v3.py','proposals':'audit_proposals_sustained_v3.py','score':'metrics_sustained_v3.py','metrics-audit':'audit_metrics_sustained_v3.py'}
  if stage not in workers:raise ValueError('unknown native stage')
  metric=stage in {'score','metrics-audit'};gpu=stage in {'train','audit'};command=receipt['command'];entry='/tmp/verifier/'+workers[stage] if stage=='audit' else worker_entry(workers[stage]);stage_runtime=self.metric_runtime if metric else self.runtime if gpu else self.cpu_runtime
  if command[-1]!=entry or receipt['runtime_lock']!=stage_runtime or receipt['driver_hashes']!=(self.old['driver_hashes'] if gpu else {}) or receipt['verifier_source_pins']!=(self.verifier_pins if stage=='audit' else {}):raise ValueError('native worker/runtime/driver/verifier differs')
  if gpu and rebind_rootfs_mount(command,GPU_ROOT)!=command:raise ValueError('native GPU rootfs mount differs')
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
   pub=record['publication']
   if sha(pub['publication_path'])!=pub['publication_sha256'] or sha(pub['release_path'])!=pub['release_sha256']:raise ValueError('resumed retention/release changed')
   validate_native_publication_release(record,pub['publication_path'],pub['release_path'],completed=True)
 def publish_and_release(self,record):
  self.guard();publisher_package=source_snapshot_package_root(self.checkpoint_publisher_pins);validate_checkpoint_publisher_sources(publisher_package,self.checkpoint_publisher_pins);publisher_receipt=self.R/'checkpoint-publisher-source-receipt.json';write(publisher_receipt,self.checkpoint_publisher_pins);before={p for p in (C/'insula').glob('hdfs-retention-*')};command=[sys.executable,'-m','retention.publish_sustained_checkpoint','--receipt',record['final_path'],'--receipt-sha256',record['final_sha256'],'--host-source-receipt',str(publisher_receipt),'--release','--lock-fd',str(self.lock.fileno())];log=self.R/f'retention-{record["step"]:02d}.log';env={k:v for k,v in os.environ.items() if k!='PYTHONPATH'}
  with log.open('w') as stream:result=subprocess.run(command,cwd=publisher_package,env=env,stdout=stream,stderr=subprocess.STDOUT,pass_fds=(self.lock.fileno(),),timeout=3600)
  if result.returncode:raise RuntimeError('checkpoint HDFS preservation failed; next training forbidden')
  new={p for p in (C/'insula').glob('hdfs-retention-*')}-before
  if len(new)!=1:raise ValueError('unique current checkpoint publication required')
  directory=new.pop();publication=directory/'verified-publication.json';release=directory/'release-completed.json';value,_,_=validate_native_publication_release(record,publication,release,completed=True)
  identity={'manifest_key':value['blobs']['manifest']['key']} if _is_blob_publication(value) else {'hdfs_manifest_uri':value['publication_manifest_hdfs_uri']}
  self.guard();return {'publication_path':str(publication),'publication_sha256':sha(publication),'release_path':str(release),'release_sha256':sha(release),**identity,'command':command,'log_sha256':sha(log)}
