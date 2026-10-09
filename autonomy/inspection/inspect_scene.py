#!/usr/bin/env python3
"""Offline M4 entry with independently validated geometry mounted readonly."""
import json
from pathlib import Path
import sys
from datetime import datetime,timezone
import time

HERE=Path(__file__).resolve().parent
COMPONENT=HERE.parent
if str(COMPONENT) not in sys.path: sys.path.insert(0,str(COMPONENT))
from evidence.source_snapshot import file_sha256
from insula.launch_plan import build_plan, load_default_runtime_lock, record_plan, run_plan
from insula.runtime_roots import current_cpu_rootfs
from insula.m0_receipt import validate_receipt
from insula.runtime_roots import waymo_cache

def main():
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
    cache=waymo_cache();runtime=load_default_runtime_lock(current_cpu_rootfs(cache));source=cache/'slices/validation-two-scenes-20260929';geometry=runtime.rootfs.parent/'m3-live-b'
    validate_receipt(runtime.rootfs.parent/'m0-live-20260930-c',runtime.rootfs,COMPONENT)
    summary=json.loads((COMPONENT/'research/m3-verified.json').read_text())
    assert file_sha256(geometry/'receipt.json')==summary['receipt_sha256']
    prerequisite=json.loads((geometry/'receipt.json').read_text())
    for name,digest in prerequisite['code_hashes'].items():assert file_sha256(COMPONENT/name)==digest
    plan=build_plan(runtime,code=COMPONENT,source=source,output=out,command=['python','-m','inspection.inspection_views','/source','/opt/reconstruction','/outputs/views'],named_inputs={'/opt':geometry})
    files=['inspection/inspect_scene.py','inspection/inspection.py','inspection/inspection_views.py','inspection/inspection_validate.py','inspection/inspection_test.py','insula/launch_plan.py','insula/runtime_roots.py']
    hashes={name:file_sha256(COMPONENT/name) for name in files}
    start=datetime.now(timezone.utc).isoformat();begin=time.monotonic();p=run_plan(plan,text=True,capture_output=True)
    (out/'producer.log').write_text(p.stdout+p.stderr)
    (out/'execution.json').write_text(json.dumps({'launch_plan':record_plan(plan),'started_utc':start,'ended_utc':datetime.now(timezone.utc).isoformat(),'seconds':time.monotonic()-begin,'exit_code':p.returncode},indent=2)+'\n')
    print(p.stdout+p.stderr)
    if p.returncode:raise SystemExit(p.returncode)
    checks=[{'name':'producer','launch_plan':record_plan(plan),'exit_code':p.returncode}]
    for name,command in [('validator',['python','-m','inspection.inspection_validate','/source','/opt/reconstruction','/outputs/views']),
                         ('fixtures',['python','-m','unittest','discover','-s','/experiment/inspection','-p','inspection_test.py','-v'])]:
        nextplan=build_plan(runtime,code=COMPONENT,source=source,output=out,command=command,named_inputs={'/opt':geometry})
        result=run_plan(nextplan,text=True,capture_output=True)
        (out/(name+'.log')).write_text(result.stdout+result.stderr)
        checks.append({'name':name,'launch_plan':record_plan(nextplan),'exit_code':result.returncode})
        print(result.stdout+result.stderr)
        if result.returncode:raise SystemExit(result.returncode)
    assert hashes=={name:file_sha256(COMPONENT/name) for name in files}
    report=json.loads((out/'views/report.json').read_text())
    receipt={'schema_version':1,'milestone':'M4','code_hashes':hashes,'checks':checks,'started_utc':start,
             'ended_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-begin,
             'runtime_lock':prerequisite['runtime_lock'],'m3_receipt_sha256':summary['receipt_sha256'],
             'source_receipt_sha256':file_sha256(source/'slice.json'),
             'artifacts':{str(p.relative_to(out)):file_sha256(p) for p in out.rglob('*') if p.is_file()}}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS M4 live candidate; pending independent receipt audit',out)


if __name__=='__main__':main()
