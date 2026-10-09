#!/usr/bin/env python3
"""Live native replay, independent source reconciliation, and M1 receipt."""
from datetime import datetime, timezone
import json
from pathlib import Path
import resource
import sys
import time

HERE=Path(__file__).resolve().parents[1]
from dataset.launches import build_dataset_plan, load_pinned_dataset_runtime, plan_receipt, rendered_command, run_dataset_plan
from evidence.source_snapshot import file_sha256 as sha
from insula.m0_receipt import receipt_fixture_paths, validate_receipt
ROOT,M0=receipt_fixture_paths()
SOURCE=Path.home()/'.cache/waystone/waymo-perception/slices/validation-two-scenes-20260929'
def main():
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
    m0_receipt=validate_receipt(M0,ROOT,HERE)
    runtime=load_pinned_dataset_runtime(ROOT,m0_receipt['runtime_lock'])
    start=datetime.now(timezone.utc).isoformat();begin=time.monotonic();checks=[]
    for name,tail in [('inspect',['-m','dataset.tracer','inspect','--sample','/source','--output','/outputs/native']),
                      ('validate',['-m','dataset.tracer','validate','--sample','/source','--output','/outputs/native']),
                      ('adversarial-tests',['-m','unittest','discover','-s','/experiment/dataset','-p','tracer_test.py','-v'])]:
        plan=build_dataset_plan(runtime,code_root=HERE,source=SOURCE,output=out,command=['python',*tail])
        command=rendered_command(plan);p=run_dataset_plan(plan,text=True,capture_output=True)
        (out/(name+'.log')).write_text(p.stdout+p.stderr)
        print(name,p.returncode,flush=True)
        checks.append({'name':name,'command':command,'launch_plan':plan_receipt(plan),'exit_code':p.returncode})
        if p.returncode:raise RuntimeError('live check failed; unpromoted failure evidence retained')
    assert sha(out/'native/manifest.jsonl')=='70190074c7d443632523a5c3273d5ead74f4fcddea653addee3a2fa2efa01bcf'
    result=json.loads((out/'native/result.json').read_text())
    for file,digest in result['implementation_hashes'].items():assert sha(HERE/file)==digest
    receipt={'schema_version':1,'milestone':'M1','started_utc':start,'ended_utc':datetime.now(timezone.utc).isoformat(),
             'runtime_lock':runtime.data,'m0_receipt_sha256':sha(M0/'receipt.json'),
             'checks':checks,'source_receipt_sha256':sha(SOURCE/'slice.json'),
             'code_hashes':{str(p.relative_to(HERE)):sha(p) for p in [HERE/'dataset/verify_native.py',HERE/'dataset/launches.py',HERE/'insula/launch_plan.py',HERE/'insula/runtime_roots.py',HERE/'insula/m0_receipt.py',HERE/'dataset/tracer_test.py']},
             'artifacts':{str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()},
             'elapsed_seconds':time.monotonic()-begin,'child_peak_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS M1 live recipe',out,flush=True)

if __name__=='__main__':main()
