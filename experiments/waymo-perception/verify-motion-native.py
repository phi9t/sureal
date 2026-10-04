#!/usr/bin/env python3
"""Locked offline execution of pinned upstream Motion metric regressions."""
import hashlib,json,resource,subprocess,tempfile,time
from datetime import datetime,timezone
from pathlib import Path
from pipeline.runtime_identity import rootfs_identity,verify_rootfs
from pipeline.insula_entry import launch_plan
HERE=Path(__file__).resolve().parent
CACHE=Path.home()/'.cache/waystone/waymo-perception'
ROOT=CACHE/'motion-metrics-rootfs'
PARENT='sha256:c0018cf57e482c6a9e6623ea32f29c6039f22f5dafb0f3311bad6d411a7bb135'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);args=parser.parse_args()
 recipes={n:sha(HERE/'motion-evaluation'/n) for n in ['Dockerfile','CMakeLists.txt']}
 lockpath=Path(str(ROOT)+'.lock.json')
 if ROOT.exists():
  lock=json.loads(lockpath.read_text());verify_rootfs(ROOT,lock['rootfs_sha256'])
  if lock['recipe_hashes']!=recipes or lock['parent_image_id']!=PARENT:raise ValueError('locked Motion recipe identity differs')
 else:
  parent=json.loads((CACHE/'metrics-rootfs.lock.json').read_text())
  if parent['image_id']!=PARENT:raise ValueError('trusted parent differs')
  image=subprocess.check_output(['docker','image','inspect','sureal-waymo-motion-metrics:source-pinned','--format','{{.Id}}'],text=True).strip()
  with tempfile.TemporaryDirectory(dir=CACHE,prefix='.motion-rootfs-') as tmp:
   stage=Path(tmp);cid=subprocess.check_output(['docker','create',image,'/bin/true'],text=True).strip()
   try:
    export=subprocess.Popen(['docker','export',cid],stdout=subprocess.PIPE);result=subprocess.run(['tar','-C',str(stage),'-xf','-'],stdin=export.stdout);export.stdout.close()
    if export.wait() or result.returncode:raise RuntimeError('Motion export failed')
   finally:subprocess.run(['docker','rm',cid],check=True,capture_output=True)
   lock={'schema_version':1,'image_id':image,'parent_image_id':PARENT,'upstream_commit':parent['upstream_commit'],'rootfs_sha256':rootfs_identity(stage),'recipe_hashes':recipes};stage.rename(ROOT);lockpath.write_text(json.dumps(lock,indent=2)+'\n')
 out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);started=datetime.now(timezone.utc).isoformat();tick=time.monotonic();checks=[]
 commands=[(n,['/motion-build/'+n+'_test','--gtest_output=json:/outputs/'+n+'.json']) for n in ['motion_metrics','motion_metrics_utils']]
 commands.append(('dependencies',['python','-c',"import importlib.util,subprocess; assert importlib.util.find_spec('tensorflow') is None; [(lambda x: (print(x),exec(\"assert 'tensorflow' not in x.lower()\")))(subprocess.check_output(['ldd','/motion-build/'+n+'_test'],text=True)) for n in ['motion_metrics','motion_metrics_utils']]"]))
 for name,cmd in commands:
  plan=launch_plan(ROOT,HERE,HERE,out,cmd);r=subprocess.run(plan,capture_output=True,text=True);(out/(name+'.log')).write_text(r.stdout+r.stderr);checks.append({'name':name,'command':plan,'exit_code':r.returncode})
  if r.returncode:raise RuntimeError(r.stderr)
  print('PASS',name,flush=True)
 for name in ['motion_metrics','motion_metrics_utils']:
  r=json.loads((out/(name+'.json')).read_text())
  if r['tests']<=0 or r['failures'] or r['disabled']:raise ValueError('upstream regression suite incomplete')
  for suite in r['testsuites']:
   for test in suite['testsuite']:
    if test['status']!='RUN' or test['result']!='COMPLETED' or test.get('failures'):raise ValueError('skipped/failed native regression')
 for n,h in recipes.items():
  if sha(HERE/'motion-evaluation'/n)!=h:raise ValueError('Motion recipe changed')
 receipt={'status':'pinned upstream Motion regression suites passed live; ingestion/analytic parity remain open','started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-tick,'peak_child_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'checks':checks,'runtime_lock':lock,'verifier_sha256':sha(Path(__file__)),'artifacts':{p.name:sha(p) for p in out.iterdir() if p.is_file()}}
 (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print('PASS native Motion regression receipt',out,flush=True)
if __name__=='__main__':main()
