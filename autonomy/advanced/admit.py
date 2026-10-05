"""Serial actual-frame CUDA gates after the original matrix's closure."""
import argparse,fcntl,json,os,shutil,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path[:0]=[str(P),str(P/'tier1'),str(P/'architecture')]
from advanced.catalog import catalog
from storage import sha,unique_payload_bytes
from insula.runtime_identity import verify_rootfs
from experiment_runner import run_stage
C=Path.home()/'.cache/waystone/waymo-perception';W=C/'scientific-processing'
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--wait',action='store_true');parser.add_argument('--version',default='v1');args=parser.parse_args();assert args.version.isalnum()
 if args.wait:
  while not (P/'research/tier1-closure-live-final-v4-verified.json').exists():time.sleep(10)
 lock=(C/'insula/architecture-experiments.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 fpath=P/'research/tier1-allclass-fixture-verified.json';gpath=P/'research/advanced-grouping-fixture-verified.json';rpath=P/'research/advanced-range-fixture-verified.json'
 fixture=json.loads(fpath.read_text());grouping=json.loads(gpath.read_text());ranges=json.loads(rpath.read_text())
 for key in ('targets','report','physical','boxes'):assert sha(fixture[key])==fixture[key+'_sha256']
 for receipt in (grouping,ranges):
  for path,digest in receipt['artifacts'].items():assert sha(path)==digest
 original=json.loads((C/'detector-gpu-live-a/receipt.json').read_text());root=C/'gpu-rootfs';verify_rootfs(root,original['runtime_lock']['rootfs_sha256'])
 R=C/'insula'/('advanced-native-admission-'+args.version);R.mkdir();source=R/'source';package=source/'experiment';package.mkdir(parents=True)
 for folder in ('advanced','pipeline','tier1','gpu'):shutil.copytree(P/folder,package/folder,ignore=shutil.ignore_patterns('__pycache__'))
 pins={str(p):sha(p) for p in source.rglob('*') if p.is_file()};checks={}
 for name,case in catalog().items():
  control=case['observation']
  observation=Path(grouping['controls'][control]['observations'] if control in grouping['controls'] else ranges['observations'] if control=='range_fusion' else fixture['controls']['baseline']['observations']).parent
  inputdir=R/name/'input';inputdir.mkdir(parents=True);(inputdir/'job.json').write_text(json.dumps({'case':case}))
  out=R/name/'output';out.mkdir();cmd=original['checks'][0]['command'].copy();cmd[cmd.index('/experiment')-1]=str(package);cmd[cmd.index('/outputs')-1]=str(out);cmd[-1]='/experiment/advanced/model_contract.py';index=cmd.index('--');cmd[index:index]=['--ro-bind',str(inputdir),'/tmp/inputs','--ro-bind',str(observation),'/tmp/fixture','--ro-bind',str(Path(fixture['targets']).parent),'/tmp/targets','--setenv','CUBLAS_WORKSPACE_CONFIG',':4096:8']
  print('RUN native CUDA gate',name,flush=True)
  with (out/'live.log').open('w') as log:result=run_stage(cmd,source,dict(os.environ),log,timeout=7200)
  assert result.returncode==0,str(out/'live.log')
  assert all(sha(path)==digest for path,digest in pins.items());assert unique_payload_bytes(W)<=15*1024**3
  checks[name]={'command':cmd,'exit_code':0,'input_job_sha256':sha(inputdir/'job.json'),'observations_sha256':sha(observation/'observations.npz'),'validation':json.loads((out/'check.json').read_text()),'artifacts':{str(p):sha(p) for p in out.iterdir() if p.is_file()}}
  (R/'admitted.json').write_text(json.dumps(checks,indent=2));print('ADMITTED native CUDA gate',name,flush=True)
 receipt={'source_pins':pins,'runtime_lock':original['runtime_lock'],'fixture_receipt_sha256':sha(fpath),'grouping_receipt_sha256':sha(gpath),'range_receipt_sha256':sha(rpath),'cases':checks,'scope':'CUDA architecture admission only; native sustained overfit and full replay remain required'}
 (P/'research/advanced-native-admission-verified.json').write_text(json.dumps(receipt,indent=2));print('PASS all eight actual-frame CUDA architecture gates',flush=True)
if __name__=='__main__':main()
