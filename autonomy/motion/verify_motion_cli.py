#!/usr/bin/env python3
"""Locked offline execution of pinned upstream Motion metric regressions."""
import json,resource,subprocess,tempfile,time
from datetime import datetime,timezone
from pathlib import Path
from evidence.source_snapshot import file_sha256 as sha
from evidence.source_snapshot import require_regular_file
from insula.runtime_identity import rootfs_identity,verify_rootfs
from insula.entry import launch_plan
HERE=Path(__file__).resolve().parent
AUTONOMY=HERE.parent
CACHE=Path.home()/'.cache/waystone/waymo-perception'
ROOT=CACHE/'motion-cli-rootfs'
PARENT='sha256:84fb83dd874d0cfff8e9ee3df0759d89f9ad85e9538c0071c9eb606a13d8c233'
def regular_children(path):
 for candidate in path.iterdir():
  try:yield require_regular_file(candidate)
  except ValueError:pass
def main():
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);args=parser.parse_args()
 recipes={n:sha(HERE/'cli'/n) for n in ['Dockerfile','CMakeLists.txt','motion_metrics_main.cc']}
 lockpath=Path(str(ROOT)+'.lock.json')
 if ROOT.exists():
  lock=json.loads(lockpath.read_text());verify_rootfs(ROOT,lock['rootfs_sha256'])
  if lock['recipe_hashes']!=recipes or lock['parent_image_id']!=PARENT:raise ValueError('locked Motion recipe identity differs')
 else:
  parent=json.loads((CACHE/'motion-metrics-rootfs.lock.json').read_text())
  if parent['image_id']!=PARENT:raise ValueError('trusted parent differs')
  image=subprocess.check_output(['docker','image','inspect','sureal-waymo-motion-cli:source-pinned','--format','{{.Id}}'],text=True).strip()
  with tempfile.TemporaryDirectory(dir=CACHE,prefix='.motion-rootfs-') as tmp:
   stage=Path(tmp);cid=subprocess.check_output(['docker','create',image,'/bin/true'],text=True).strip()
   try:
    export=subprocess.Popen(['docker','export',cid],stdout=subprocess.PIPE);result=subprocess.run(['tar','-C',str(stage),'-xf','-'],stdin=export.stdout);export.stdout.close()
    if export.wait() or result.returncode:raise RuntimeError('Motion export failed')
   finally:subprocess.run(['docker','rm',cid],check=True,capture_output=True)
   lock={'schema_version':1,'image_id':image,'parent_image_id':PARENT,'upstream_commit':parent['upstream_commit'],'rootfs_sha256':rootfs_identity(stage),'recipe_hashes':recipes};stage.rename(ROOT);lockpath.write_text(json.dumps(lock,indent=2)+'\n')
 out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);started=datetime.now(timezone.utc).isoformat();tick=time.monotonic();checks=[]
 commands=[('analytic-fixtures',['python','-m','unittest','discover','-s','motion/cli','-p','motion_native_cli_test.py','-v']),('dependencies',['python','-c',"import importlib.util,subprocess; assert importlib.util.find_spec('tensorflow') is None; x=subprocess.check_output(['ldd','/motion-cli-build/compute_motion_metrics'],text=True); assert 'tensorflow' not in x.lower(); print(x)"])]
 for name,cmd in commands:
  plan=launch_plan(ROOT,AUTONOMY,AUTONOMY,out,cmd);r=subprocess.run(plan,capture_output=True,text=True);(out/(name+'.log')).write_text(r.stdout+r.stderr);checks.append({'name':name,'command':plan,'exit_code':r.returncode})
  if r.returncode:raise RuntimeError(r.stderr)
  print('PASS',name,flush=True)
 for n,h in recipes.items():
  if sha(HERE/'cli'/n)!=h:raise ValueError('Motion recipe changed')
 receipt={'status':'native Motion CLI initial analytic fixtures passed live; full parity and ingestion remain open','started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-tick,'peak_child_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'checks':checks,'runtime_lock':lock,'verifier_sha256':sha(Path(__file__)),'test_sha256':sha(HERE/'cli/motion_native_cli_test.py'),'artifacts':{p.name:sha(p) for p in regular_children(out)}}
 (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print('PASS native Motion regression receipt',out,flush=True)
if __name__=='__main__':main()
