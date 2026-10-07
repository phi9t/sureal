#!/usr/bin/env python3
"""Offline M4 entry with independently validated geometry mounted readonly."""
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime,timezone
import time

HERE=Path(__file__).resolve().parent
COMPONENT=HERE.parent
from evidence.source_snapshot import file_sha256
from insula.entry import launch_plan
from insula.m0_receipt import validate_receipt
ROOT=Path.home()/'.cache/waystone/waymo-perception/insula/rootfs-v2'
SOURCE=Path.home()/'.cache/waystone/waymo-perception/slices/validation-two-scenes-20260929'
GEOMETRY=ROOT.parent/'m3-live-b'

def main():
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
    validate_receipt(ROOT.parent/'m0-live-20260930-c',ROOT,COMPONENT)
    summary=json.loads((COMPONENT/'research/m3-verified.json').read_text())
    assert file_sha256(GEOMETRY/'receipt.json')==summary['receipt_sha256']
    prerequisite=json.loads((GEOMETRY/'receipt.json').read_text())
    for name,digest in prerequisite['code_hashes'].items():assert file_sha256(COMPONENT/name)==digest
    plan=launch_plan(ROOT,COMPONENT,SOURCE,out,['python','-m','inspection.inspection_views','/source','/opt/reconstruction','/outputs/views'])
    pos=plan.index('--');plan[pos:pos]=['--ro-bind',str(GEOMETRY),'/opt']
    files=['inspection/inspect_scene.py','inspection/inspection.py','inspection/inspection_views.py','inspection/inspection_validate.py','inspection/inspection_test.py']
    hashes={name:file_sha256(COMPONENT/name) for name in files}
    start=datetime.now(timezone.utc).isoformat();begin=time.monotonic();p=subprocess.run(plan,text=True,capture_output=True)
    (out/'producer.log').write_text(p.stdout+p.stderr)
    (out/'execution.json').write_text(json.dumps({'command':plan,'started_utc':start,'ended_utc':datetime.now(timezone.utc).isoformat(),'seconds':time.monotonic()-begin,'exit_code':p.returncode},indent=2)+'\n')
    print(p.stdout+p.stderr)
    if p.returncode:raise SystemExit(p.returncode)
    checks=[{'name':'producer','command':plan,'exit_code':p.returncode}]
    for name,command in [('validator',['python','-m','inspection.inspection_validate','/source','/opt/reconstruction','/outputs/views']),
                         ('fixtures',['python','-m','unittest','discover','-s','/experiment/inspection','-p','inspection_test.py','-v'])]:
        nextplan=launch_plan(ROOT,COMPONENT,SOURCE,out,command);i=nextplan.index('--');nextplan[i:i]=['--ro-bind',str(GEOMETRY),'/opt']
        result=subprocess.run(nextplan,text=True,capture_output=True)
        (out/(name+'.log')).write_text(result.stdout+result.stderr)
        checks.append({'name':name,'command':nextplan,'exit_code':result.returncode})
        print(result.stdout+result.stderr)
        if result.returncode:raise SystemExit(result.returncode)
    assert hashes=={name:file_sha256(COMPONENT/name) for name in files}
    report=json.loads((out/'views/report.json').read_text())
    receipt={'schema_version':1,'milestone':'M4','code_hashes':hashes,'checks':checks,'started_utc':start,
             'ended_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-begin,
             'runtime_lock':prerequisite['runtime_lock'],'m3_receipt_sha256':summary['receipt_sha256'],
             'source_receipt_sha256':file_sha256(SOURCE/'slice.json'),
             'artifacts':{str(p.relative_to(out)):file_sha256(p) for p in out.rglob('*') if p.is_file()}}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS M4 live candidate; pending independent receipt audit',out)


if __name__=='__main__':main()
