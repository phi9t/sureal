#!/usr/bin/env python3
"""Locked offline execution of pinned upstream Motion metric regressions."""
import json,resource,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
from evidence.source_snapshot import file_sha256 as sha
from evidence.source_snapshot import is_regular_file
from insula.launch_plan import build_plan, load_runtime_lock, record_plan, render_plan
from insula.runtime_roots import current_motion_metrics_rootfs, default_lock
HERE=Path(__file__).resolve().parent
AUTONOMY=HERE.parent
CACHE=Path.home()/'.cache/waystone/waymo-perception'
ROOT=current_motion_metrics_rootfs(CACHE)
def load_motion_runtime(rootfs=ROOT):
 return load_runtime_lock(Path(rootfs),default_lock(Path(rootfs)))
def build_motion_plan(runtime,output,command):
 return build_plan(runtime,code=AUTONOMY,output=output,command=command)
def main():
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);args=parser.parse_args()
 runtime=load_motion_runtime(ROOT)
 out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);started=datetime.now(timezone.utc).isoformat();tick=time.monotonic();checks=[]
 commands=[(n,['/motion-build/'+n+'_test','--gtest_output=json:/outputs/'+n+'.json']) for n in ['motion_metrics','motion_metrics_utils']]
 commands.append(('dependencies',['python','-c',"import importlib.util,subprocess; assert importlib.util.find_spec('tensorflow') is None; [(lambda x: (print(x),exec(\"assert 'tensorflow' not in x.lower()\")))(subprocess.check_output(['ldd','/motion-build/'+n+'_test'],text=True)) for n in ['motion_metrics','motion_metrics_utils']]"]))
 for name,cmd in commands:
  plan=build_motion_plan(runtime,out,cmd);argv=render_plan(plan);r=subprocess.run(argv,capture_output=True,text=True);(out/(name+'.log')).write_text(r.stdout+r.stderr);checks.append({'name':name,'command':argv,'launch_plan':record_plan(plan),'exit_code':r.returncode})
  if r.returncode:raise RuntimeError(r.stderr)
  print('PASS',name,flush=True)
 for name in ['motion_metrics','motion_metrics_utils']:
  r=json.loads((out/(name+'.json')).read_text())
  if r['tests']<=0 or r['failures'] or r['disabled']:raise ValueError('upstream regression suite incomplete')
  for suite in r['testsuites']:
   for test in suite['testsuite']:
    if test['status']!='RUN' or test['result']!='COMPLETED' or test.get('failures'):raise ValueError('skipped/failed native regression')
 receipt={'status':'pinned upstream Motion regression suites passed live; ingestion/analytic parity remain open','started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-tick,'peak_child_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'checks':checks,'runtime_lock':runtime.data,'verifier_sha256':sha(Path(__file__)),'artifacts':{p.name:sha(p) for p in out.iterdir() if is_regular_file(p)}}
 (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print('PASS native Motion regression receipt',out,flush=True)
if __name__=='__main__':main()
