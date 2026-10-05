"""Bounded, source-frozen 16-frame fitting study in live Insula."""
import argparse,fcntl,hashlib,json,os,shutil,sys,time
from pathlib import Path
PACKAGE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(PACKAGE));sys.path.insert(0,str(PACKAGE/'architecture'))
from pipeline.insula_entry import launch_plan
from pipeline.runtime_identity import verify_rootfs
from experiment_runner import run_stage
from protocol import validate_cohort
from balanced_gate import validate_balanced_fixture
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
CACHE=Path.home()/'.cache/waystone/waymo-perception';WORK=CACHE/'scientific-processing'
def bytes_used(path):return sum(p.stat().st_size for p in path.rglob('*') if p.is_file())
def main():
 parser=argparse.ArgumentParser();parser.add_argument('variant',choices=['baseline','residual_bev']);parser.add_argument('--run-id',required=True);args=parser.parse_args()
 if not args.run_id.isalnum():raise ValueError('Alphanumeric run ID required')
 lock=(CACHE/'insula/architecture-experiments.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 run=CACHE/'insula'/f'cohort16-{args.variant}-{args.run_id}';run.mkdir();source=run/'source';source.mkdir();package=source/'autonomy';package.mkdir(parents=True)
 for folder in ['pipeline','gpu','research','cohort']:shutil.copytree(PACKAGE/folder,package/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 pins={str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()};assert bytes_used(source)<64*1024**2
 native=WORK/'balanced16-native-v2';physical=WORK/'balanced16-physical-v2';boxes=WORK/'balanced16-labels-v2';progress=json.loads((package/'research/balanced16-native-progress.json').read_text());protocol=json.loads((package/'research/pointpillars-scientific-protocol.candidate.json').read_text());frames=[]
 for identity,item in progress['frame_evidence'].items():
  assert sha(item['receipt'])==item['sha256'];scene,timestamp=identity.split(':');assert scene in protocol['cohorts']['train'];base=native/scene/timestamp;receipt=json.loads((base/'receipt.json').read_text())
  for name,h in receipt['artifacts'].items():assert sha(base/name)==h
  frames.append({'identity':identity,'split':'training','relative_directory':f'{scene}/{timestamp}/producer','sha256':{n:sha(base/'producer'/n) for n in ['observations.npz','targets.npz','report.json']},'physical_sha256':sha(physical/scene/'producer'/f'{timestamp}.npz'),'boxes_sha256':sha(boxes/scene/'producer/targets.json'),'positive_anchors':item['validation']['positive_anchor_counts_by_class']})
 validate_cohort(frames)
 validate_balanced_fixture(frames,json.loads((package/"research/balanced16-selection.candidate.json").read_text()),json.loads((package/"research/balanced16-labels-and-anchor-coverage-v3-verified.json").read_text()))
 manifest={'architecture_variant':args.variant,'frames':frames,'seed':17,'execution':{'updates':2000,'seed':17,'checkpoint_grid':[0,1000,2000]},'scope':'16 frozen training frames; no heldout data; all-class gates required'}
 inputs=run/'inputs';inputs.mkdir();(inputs/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');metadata={'manifest':manifest,'source_sha256':pins,'manifest_sha256':sha(inputs/'manifest.json'),'run_id':args.run_id,'variant':args.variant};(run/'run.json').write_text(json.dumps(metadata,indent=2)+'\n')
 output=WORK/f'cohort16-{args.variant}-{args.run_id}';output.mkdir();assert bytes_used(WORK)+1400*1024**2<=15*1024**3
 roots={'cpu':CACHE/'insula/rootfs-v2','gpu':CACHE/'gpu-rootfs','metrics':CACHE/'metrics-rootfs'};locks={}
 old=json.loads((CACHE/'detector-gpu-live-a/receipt.json').read_text())
 for name,root in roots.items():
  locks[name]=old['runtime_lock'] if name=='gpu' else json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,locks[name]['rootfs_sha256'])
 for path,h in old['driver_hashes'].items():assert sha(path)==h
 def execute(stage,worker,out,gpu=False,args_worker=None,src=None,extra=None):
  out.mkdir(exist_ok=True)
  if gpu:
   command=old['checks'][0]['command'].copy();command[command.index('/experiment')-1]=str(package);command[command.index('/outputs')-1]=str(out);command[-1]='/tmp/workers/'+worker
  else:command=launch_plan(roots['cpu'],package,src or source,out,args_worker or ['python','/tmp/workers/'+worker])
  i=command.index('--');command[i:i]=['--ro-bind',str(package/'cohort'),'/tmp/workers','--ro-bind',str(inputs),'/tmp/inputs','--ro-bind',str(native),'/tmp/native','--ro-bind',str(physical),'/tmp/physical','--ro-bind',str(boxes),'/tmp/boxes','--setenv','CUBLAS_WORKSPACE_CONFIG',':4096:8',*(extra or [])]
  started=time.monotonic();print('RUN',stage,str(out),flush=True)
  with (out/'live.log').open('w') as log:result=run_stage(command,source,dict(os.environ),log,timeout=7200)
  if result.returncode:raise RuntimeError(stage+' failed; '+str(out/'live.log'))
  assert all(sha(source/p)==h for p,h in pins.items());assert bytes_used(WORK)<=15*1024**3
  evidence={'stage':stage,'checks':[{'command':command,'exit_code':0}],'runtime_locks':locks,'driver_hashes':old['driver_hashes'],'source_sha256':pins,'manifest_sha256':metadata['manifest_sha256'],'manifest':manifest,'elapsed_seconds':time.monotonic()-started,'artifacts':{str(p):sha(p) for p in out.rglob('*') if p.is_file()}}
  if (out/'check.json').exists():evidence['validation']=json.loads((out/'check.json').read_text())
  (run/(stage+'-verified.json')).write_text(json.dumps(evidence,indent=2)+'\n');print('ADMITTED',stage,flush=True)
 execute('protocol','',run/'protocol',args_worker=['python','-m','unittest','discover','-s','/experiment/cohort','-p','test_*.py'])
 execute('coverage','coverage.py',run/'coverage')
 execute('train','train_balanced.py',output,gpu=True);assert bytes_used(output)<=1400*1024**2
 execute('checkpoint','checkpoint.py',run/'checkpoint',gpu=True,extra=['--ro-bind',str(output),'/tmp/retained'])
 execute('loss','loss_balanced.py',run/'loss',src=output)
 (PACKAGE/'research'/f'cohort16-{args.variant}-{args.run_id}-execution.json').write_text(json.dumps({'run_directory':str(run),'output_directory':str(output),'metadata_sha256':sha(run/'run.json'),'stage_receipts':{p.name:sha(p) for p in run.glob('*-verified.json')},'scope':'execution/replay/loss; native scores still required'},indent=2)+'\n')
 print('READY FOR NATIVE SCORING',run,flush=True)
if __name__=='__main__':main()
