"""Named, immutable architecture runs using the admitted live Insula harness."""
import argparse,datetime,fcntl,io,json,os,re,shutil,signal,subprocess,sys,tarfile,uuid
from pathlib import Path

HERE=Path(__file__).resolve().parent
PACKAGE=HERE.parents[1]
REPO=PACKAGE.parent
CACHE=Path.home()/'.cache/waystone/waymo-perception'
from evidence.source_snapshot import LocalSnapshotStore,file_sha256 as sha,require_regular_file,safe_member_name,snapshot_bazel_target,verify_receipt_sources

ARCHITECTURE_SOURCE_SNAPSHOT_TARGET='//autonomy:architecture_experiment_runner_snapshot'
ARCHITECTURE_STUDY_SPEC_SHA256='fef072b2737a4fda94a029944fb999d78be482669b1cd989af953d93b5e7ecf1'
SOURCE_SNAPSHOT_STORE_RELATIVE=Path('insula/source-snapshots-v1')

def registry(here=None):return json.loads(((HERE if here is None else Path(here))/'registry.json').read_text())
def run_label(name,run_id):
 if name not in registry():raise ValueError('Unknown experiment: '+name)
 if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}',run_id):raise ValueError('Run ID must be1–64 letters/digits/underscore/hyphen, starting with a letter or digit')
 return name+'--'+run_id

def contract_label(run_id):return 'run-'+run_id

def run_stage(command,cwd,env,stream,timeout=9000):
 process=subprocess.Popen(command,cwd=cwd,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
 try:
  process.wait(timeout=timeout)
 except BaseException:
  try:os.killpg(process.pid,signal.SIGTERM)
  except ProcessLookupError:pass
  try:process.wait(timeout=5)
  except subprocess.TimeoutExpired:pass
  try:os.killpg(process.pid,signal.SIGKILL)
  except ProcessLookupError:pass
  process.wait()
  raise
 return process

def stages_for(name):
 item=registry().get(name)
 if not item or item['status']!='runnable':raise ValueError('Experiment is planned, not implemented: '+name)
 if name in ['deep_pfn','context_pfn','residual_bev']:family='architecture'
 elif name in ['masked_pfn','window_bev','coarse_mlp']:family='followup'
 elif name=='retain64':family='retain64'
 else:family='all-pillars'
 train={'architecture':'run-architecture-learning-curve.py','followup':'run-followup-learning-curve.py','retain64':'run-retain64-learning-curve.py','all-pillars':'run-all-pillars-learning-curve.py'}[family]
 contract='run-architecture-followup-contract.py' if family=='followup' else 'run-architecture-contract.py'
 contract_receipt='architecture-followup-contract-verified.json' if family=='followup' else 'architecture-contract-verified.json'
 return [
  {'name':'contract','driver':contract,'receipt':contract_receipt,'contract':True},
  {'name':'weights','driver':'run-architecture-weight-contract.py','receipt':'architecture-weight-contract-verified.json','contract':True},
  {'name':'train','driver':train,'receipt':'execution'},
  {'name':'checkpoint','driver':'audit-'+family+'-checkpoint.py','receipt':'checkpoint-audit'},
  {'name':'loss','driver':'run-'+family+'-loss-audit.py','receipt':'loss-audit'},
  {'name':'score','driver':'score-'+family+'-score-first.py','receipt':'score-first'},
  {'name':'score_audit','driver':'audit-'+family+'-score-first.py','receipt':'score-first-audits'}]

def check_harness_closure(here=None,package=None):
 here=HERE if here is None else Path(here);package=PACKAGE if package is None else Path(package)
 files=json.loads((here/'harness/files.json').read_text());available=set(files)
 for name in files:
  p=here/'harness'/name
  try:require_regular_file(p)
  except ValueError as error:raise ValueError('Missing bundled harness file: '+name) from error
  for referenced in re.findall(r"['\"]([a-zA-Z0-9_-]+\.py)['\"]",p.read_text()):
   if referenced not in available and not any((package/area/referenced).exists() for area in ['detection','gpu']):
    raise ValueError(f'{name} references unbundled worker {referenced}')
 for name,item in registry(here).items():
  if item['status']=='runnable':
   for stage in stages_for(name):
    if stage['driver'] not in available:raise ValueError('Unbundled driver '+stage['driver'])
 return files

def parameterize_driver(source):
 source='import os\n'+source
 source=source.replace("variant=sys.argv[1];", "variant=sys.argv[1];run_label=variant+'--'+os.environ['WAYMO_ARCH_RUN_ID'];")
 source=source.replace("'+variant+'", "'+run_label+'")
 source=source.replace("'architecture_variant':variant", "'run_label':run_label,'architecture_variant':variant")
 source=source.replace("sha(Path('docs/superpowers/specs/2026-10-02-perception-architecture-study-design.md'))", repr(ARCHITECTURE_STUDY_SPEC_SHA256))
 source=source.replace("cache=Path.home()/'.cache/waystone/waymo-perception'", "cache=Path(os.environ['WAYMO_ARCH_CACHE_ROOT'])")
 # Rebind the frozen source package and /outputs by mount target, not an old checkout/cache pathname.
 source=source.replace("separator=command.index('--');command[separator:separator]=['--setenv'", "command[command.index('/experiment')-1]=str(code)\ncommand[command.index('/outputs')-1]=str(output)\nseparator=command.index('--');command[separator:separator]=['--setenv'")
 # Contract drivers use an old launch template too.
 if "label=sys.argv[1]" in source:
  source=source.replace("pins={", "command[command.index('/experiment')-1]=str(code)\ncommand[command.index('/outputs')-1]=str(output)\npins={",1)
 return source

def verify_receipt(receipt,package,snapshot_store=None):
 if snapshot_store is not None or 'source_snapshot_sha256' in receipt:
  if snapshot_store is None:raise ValueError('Snapshot store required for source-pinned receipt')
  verify_receipt_sources(receipt,snapshot_store)
 def check(path,digest):
  try:p=require_regular_file(Path(path))
  except ValueError as error:raise ValueError('Missing or changed evidence: '+str(path)) from error
  if sha(p)!=digest:raise ValueError('Missing or changed evidence: '+str(p))
 for p,h in receipt.get('artifacts',{}).items():check(p,h)
 for p,h in receipt.get('candidate_hashes',{}).items():check(package/p,h)
 for p,h in receipt.get('driver_hashes',{}).items():check(p,h)
 for p,h in receipt.get('worker_hashes',{}).items():
  path=Path(p) if Path(p).is_absolute() else package.parent/'.scratch'/p
  check(path,h)
 if 'manifest_sha256' in receipt:
  manifests=set()
  for row in receipt.get('checks',[]):
   command=row['command']
   for i,value in enumerate(command):
    if value=='/tmp/inputs' and i>=2 and command[i-2]=='--ro-bind':
     manifests.add(str(Path(command[i-1])/'manifest.json'))
  if len(manifests)!=1:raise ValueError('Cannot locate unique pinned manifest')
  check(next(iter(manifests)),receipt['manifest_sha256'])
 if 'worker_sha256' in receipt:
  # Worker digest is retained in the command's read-only binding.
  found=False
  for row in receipt.get('checks',[]):
   command=row['command']
   for i,value in enumerate(command):
    if value=='/tmp/worker.py' and i>=2 and command[i-2]=='--ro-bind':
     check(command[i-1],receipt['worker_sha256']);found=True
   # Legacy GPU receipts and current detection receipts both pin source workers.
   if not found:
    for value in command:
     if value.startswith(('/experiment/gpu/','/experiment/detection/')) and value.endswith('.py'):
      check(package/value.removeprefix('/experiment/'),receipt['worker_sha256']);found=True
  if not found:raise ValueError('Cannot locate pinned receipt worker')
 if any(row.get('exit_code')!=0 for row in receipt.get('checks',[])):raise ValueError('Receipt has failed checks')
 return receipt

def receipt_path(package,stage,label):
 return package/'research'/(stage['receipt'] if stage.get('contract') else 'architecture-'+label+'-'+stage['receipt']+'-verified.json')

def preflight(cache,name):
 required=['detector-gpu-live-a/receipt.json','gpu-rootfs','insula/rootfs-v2','metrics-rootfs','scientific-processing/overfit-native-cache-v1','scientific-processing/overfit-point-frames-v1','scientific-processing/overfit-box-targets-v1']
 for relative in required:
  if not (cache/relative).exists():raise ValueError('Missing admitted runtime/data prerequisite: '+str(cache/relative)+'; see studies/architecture/README.md')
 if not shutil.which('bwrap'):raise ValueError('bubblewrap (bwrap) is required for live Insula')
 if name in ['retain64','all_pillars']:
  record=PACKAGE/'research'/f'architecture-{name}-cache-verified.json'
  if not record.exists():raise ValueError('Missing independently admitted retention cache: '+str(record))
  verify_receipt(json.loads(record.read_text()),PACKAGE)
 working=cache/'scientific-processing';used=sum(p.stat().st_size for p in working.rglob('*') if p.is_file())
 if used+832*1024**2>15*1024**3:raise ValueError('Insufficient scientific storage budget for a fresh run (15GiB cap)')
 return used

def atomic_json(path,value):
 tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)

def source_snapshot_store(cache):
 return LocalSnapshotStore(Path(cache)/SOURCE_SNAPSHOT_STORE_RELATIVE)

def materialize_source_snapshot(store,digest,destination):
 destination=Path(destination)
 if destination.exists():raise ValueError('Run source directory already exists: '+str(destination))
 destination.mkdir(parents=True)
 archive=store.fetch(digest)
 seen=set()
 try:
  with tarfile.open(fileobj=io.BytesIO(archive),mode='r:') as reader:
   for member in reader:
    name=safe_member_name(member.name)
    if name in seen or not member.isfile() or member.linkname:raise ValueError('snapshot contains duplicate or nonregular member')
    seen.add(name);stream=reader.extractfile(member)
    if stream is None:raise ValueError('snapshot contains unreadable member')
    path=destination/name;path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('wb') as output:shutil.copyfileobj(stream,output)
 except (tarfile.TarError,OSError,EOFError) as error:
  raise ValueError('invalid source snapshot') from error
 if not seen:raise ValueError('source snapshot contains no files')

def prepare_harness_workspace(source,name,run_id):
 package=source/'autonomy';here=package/'studies/architecture'
 workers=source/'.scratch';workers.mkdir()
 for filename in check_harness_closure(here,package):
  text=(here/'harness'/filename).read_text()
  if (filename.startswith(('run-','audit-','score-')) and 'variant=sys.argv[1]' in text) or 'label=sys.argv[1]' in text:
   text=parameterize_driver(text)
  for worker in ['audit-architecture-learning-curve.py','audit-architecture-score-first-proposals.py','audit-architecture-score-first-native-metrics.py']:
   if filename==worker:text=text.replace("r['manifest']['architecture_variant']", "r['manifest'].get('run_label',r['manifest']['architecture_variant'])")
  (workers/filename).write_text(text)
 for stage in stages_for(name):
  if stage.get('contract'):receipt_path(package,stage,run_label(name,run_id)).unlink(missing_ok=True)
 return package

def snapshot_receipt_fields(meta):
 return {
  'source_snapshot_sha256':meta['source_snapshot_sha256'],
  'source_snapshot_target':meta['source_snapshot_target'],
  'source_pins':meta['source_pins'],
 }

def pin_receipt_to_source_snapshot(path,meta):
 receipt=json.loads(Path(path).read_text())
 receipt.update(snapshot_receipt_fields(meta))
 atomic_json(Path(path),receipt)
 return receipt

def make_snapshot(directory,name,run_id,cache):
 store=source_snapshot_store(cache)
 snapshot=snapshot_bazel_target(ARCHITECTURE_SOURCE_SNAPSHOT_TARGET,store,repo_root=REPO)
 if snapshot.archive_bytes>64*1024**2:raise ValueError('Source snapshot exceeds64MiB budget')
 source=directory/'source';materialize_source_snapshot(store,snapshot.digest,source)
 package=prepare_harness_workspace(source,name,run_id)
 atomic_json(directory/'run.json',{'experiment':name,'run_id':run_id,'label':run_label(name,run_id),'cache_root':str(cache),'source_snapshot_sha256':snapshot.digest,'source_snapshot_target':snapshot.target,'source_snapshot_bytes':snapshot.archive_bytes,'source_pins':snapshot.source_pins,'stages':stages_for(name),'scope':'fixed training-batch diagnostic, no whole-model/heldout acceptance'})
 return source,package

def check_snapshot(directory):
 meta=json.loads((directory/'run.json').read_text());source=directory/'source'
 if 'source_snapshot_sha256' not in meta:
  raise ValueError('Run predates source snapshots; re-run or re-admit with a source snapshot')
 verify_receipt_sources(meta,source_snapshot_store(Path(meta['cache_root'])))
 return meta

def summarize(package,name,label,snapshot_store=None):
 for stage in stages_for(name):
  if stage.get('contract'):
   path=receipt_path(package,stage,label)
   if not path.exists():raise ValueError('Stage not admitted: '+stage['name'])
   verify_receipt(json.loads(path.read_text()),package,snapshot_store=snapshot_store)
 values={}
 for suffix in ['execution','checkpoint-audit','loss-audit','score-first','score-first-audits']:
  p=package/'research'/f'architecture-{label}-{suffix}-verified.json'
  if not p.exists():raise ValueError('Stage not admitted: '+suffix)
  values[suffix]=verify_receipt(json.loads(p.read_text()),package,snapshot_store=snapshot_store)
 train=values['execution'];score=values['score-first'];audit=values['score-first-audits']
 if values['checkpoint-audit']['producer_evidence_sha256']!=sha(package/'research'/f'architecture-{label}-execution-verified.json'):raise ValueError('Checkpoint producer identity mismatch')
 if values['loss-audit']['producer_evidence_sha256']!=sha(package/'research'/f'architecture-{label}-execution-verified.json'):raise ValueError('Loss producer identity mismatch')
 if score['training_evidence_sha256']!=sha(package/'research'/f'architecture-{label}-execution-verified.json'):raise ValueError('Score producer identity mismatch')
 if audit['producer_evidence_sha256']!=sha(package/'research'/f'architecture-{label}-score-first-verified.json'):raise ValueError('Score audit producer identity mismatch')
 if len(score['validation']['curve'])!=11 or len(audit['validation'])!=11:raise ValueError('All11 checkpoint scores/audits required')
 final=score['validation']['curve'][-1]
 return {'experiment':name,'label':label,'live_stages_admitted':True,'checkpoints_audited':11,'final_mean_APH':final['mean_populated_class_APH'],'per_class':final['LEVEL2_per_class'],'parameters':train['validation']['parameters'],'train_seconds':train['validation']['cumulative_train_seconds'],'first_pass':score['validation']['first_observed_pass'],'whole_model_tier1_passed':False,'limitation':'Training-only fixture has no cyclists; per-class gates must pass independently. No heldout claim.'}

def execute(name,run_id,cache,resume=False):
 stages=stages_for(name);run_label(name,run_id)
 directory=cache/'insula/architecture-runs'/run_id
 directory.parent.mkdir(parents=True,exist_ok=True)
 lock=cache/'insula/architecture-experiments.lock';lock.parent.mkdir(parents=True,exist_ok=True)
 with lock.open('a') as handle:
  try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise ValueError('Another architecture experiment owns the GPU lock; retry after it finishes')
  if directory.exists():
   if not resume:raise ValueError('Run ID already exists; choose a new ID or use --resume')
   meta=check_snapshot(directory)
   if meta['experiment']!=name or meta['cache_root']!=str(cache):raise ValueError('Resume configuration does not match frozen run')
   source=directory/'source';package=source/'autonomy'
  else:
   if resume:raise ValueError('Cannot resume a nonexistent run ID')
   preflight(cache,name);directory.mkdir();source,package=make_snapshot(directory,name,run_id,cache)
  meta=check_snapshot(directory);store=source_snapshot_store(cache)
  env=dict(os.environ,WAYMO_ARCH_RUN_ID=run_id,WAYMO_ARCH_CACHE_ROOT=str(cache),PYTHONPATH=str(package));logs=directory/'logs';logs.mkdir(exist_ok=True)
  for stage in stages:
   check_snapshot(directory);path=receipt_path(package,stage,run_label(name,run_id))
   if path.exists():
    receipt=json.loads(path.read_text())
    if 'source_snapshot_sha256' not in receipt:receipt=pin_receipt_to_source_snapshot(path,meta)
    verify_receipt(receipt,package,snapshot_store=store);print('VERIFIED skip '+stage['name'],flush=True);continue
   log=logs/(stage['name']+'.log')
   if log.exists():raise ValueError('Incomplete stage '+stage['name']+' has retained outputs; choose a fresh run ID (no destructive retry)')
   print('RUN '+stage['name']+'; log '+str(log),flush=True)
   command=[sys.executable,str(source/'.scratch'/stage['driver']),contract_label(run_id) if stage.get('contract') else name]
   try:
    with log.open('w') as stream:result=run_stage(command,source,env,stream,timeout=9000)
   except subprocess.TimeoutExpired:
    atomic_json(directory/'failure.json',{'stage':stage['name'],'reason':'timeout; owned process group terminated','log':str(log)})
    raise
   if result.returncode:
    atomic_json(directory/'failure.json',{'stage':stage['name'],'exit_code':result.returncode,'log':str(log)})
    raise ValueError('Stage failed: '+stage['name']+'; retained log '+str(log))
   if not path.exists():raise ValueError('Stage produced no admission receipt: '+stage['name'])
   verify_receipt(pin_receipt_to_source_snapshot(path,meta),package,snapshot_store=store)
   print('ADMITTED '+stage['name'],flush=True)
  summary=summarize(package,name,run_label(name,run_id),snapshot_store=store);atomic_json(directory/'summary.json',summary);print(json.dumps(summary,indent=2))

def main(argv=None):
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--cache-root',type=Path,default=CACHE)
 sub=parser.add_subparsers(dest='command',required=True)
 sub.add_parser('list')
 show=sub.add_parser('show');show.add_argument('experiment',choices=list(registry()))
 run=sub.add_parser('run');run.add_argument('experiment',choices=list(registry()));run.add_argument('--run-id');run.add_argument('--resume',action='store_true');run.add_argument('--dry-run',action='store_true')
 verify=sub.add_parser('verify');verify.add_argument('experiment',choices=list(registry()));verify.add_argument('--run-id',required=True)
 args=parser.parse_args(argv)
 try:
  if args.command=='list':
   for name,item in registry().items():print(f"{name:24} {item['status']:9} {item['title']}")
  elif args.command=='show':print(json.dumps(registry()[args.experiment],indent=2))
  elif args.command=='run':
   if args.resume and not args.run_id:raise ValueError('--resume requires --run-id')
   run_id=args.run_id or datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
   run_label(args.experiment,run_id)
   if args.dry_run:print(json.dumps({'experiment':args.experiment,'run_id':run_id,'stages':stages_for(args.experiment),'output':str(args.cache_root.resolve()/'insula/architecture-runs'/run_id),'scope':'plan only; no files, GPU or runtime checks'},indent=2))
   else:execute(args.experiment,run_id,args.cache_root.resolve(),args.resume)
  else:
   directory=args.cache_root.resolve()/'insula/architecture-runs'/args.run_id;meta=check_snapshot(directory)
   if meta['experiment']!=args.experiment:raise ValueError('Run ID belongs to another experiment')
   print(json.dumps(summarize(directory/'source/autonomy',args.experiment,run_label(args.experiment,args.run_id),snapshot_store=source_snapshot_store(args.cache_root.resolve())),indent=2))
  return 0
 except (ValueError,FileNotFoundError,subprocess.TimeoutExpired) as error:
  print('ERROR: '+str(error),file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
