#!/usr/bin/env python3
"""M3 live full-cohort reconstruction and independent validation receipt."""
from datetime import datetime,timezone
import json
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time

HERE=Path(__file__).resolve().parents[1]
from evidence.source_snapshot import file_sha256 as sha
from insula.m0_receipt import validate_receipt
ROOT=Path.home()/'.cache/waystone/waymo-perception/insula/rootfs-v2'
M0=ROOT.parent/'m0-live-20260930-c'
SOURCE=Path.home()/'.cache/waystone/waymo-perception/slices/validation-two-scenes-20260929'
FILES=['geometry/verify_reconstruction.py','enter.sh','insula/entry.py','insula/runtime_identity.py',
       'geometry/geometry.py','geometry/geometry_foundation.py','dataset/sensor_records.py',
       'geometry/reconstruction_probe.py','geometry/reconstruction_validate.py','dataset/tracer.py',
       'dataset/tracer_contracts.py','geometry/geometry_test.py','dataset/sensor_records_test.py','geometry/reconstruction_validate_test.py']

def main():
    destination=Path(sys.argv[1])
    if destination.exists():raise ValueError('existing destination')
    validate_receipt(M0,ROOT,HERE)
    for milestone in ['m1','m2']:
        summary=json.loads((HERE/f'research/{milestone}-verified.json').read_text())
        assert summary['status']=='verified-complete'
        assert sha(Path(summary['receipt_path']))==summary['receipt_sha256']
    destination.parent.mkdir(parents=True,exist_ok=True)
    hashes={name:sha(HERE/name) for name in FILES};start=datetime.now(timezone.utc).isoformat();begin=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='.m3-stage-',dir=destination.parent) as tmp:
        stage=Path(tmp);records=[]
        base=[str(HERE/'enter.sh'),'--source',str(SOURCE),'--output',str(stage),'--offline','--','python']
        commands=[('producer',['-m','geometry.reconstruction_probe','/source','/outputs/reconstruction','--full']),
                  ('validator',['-m','geometry.reconstruction_validate','/source','/outputs/reconstruction'])]
        commands +=[
            ('ray-fixtures',['-m','unittest','discover','-s','/experiment/geometry','-p','geometry_test.py','-v']),
            ('identity-fixtures',['-m','unittest','discover','-s','/experiment/dataset','-p','sensor_records_test.py','-v']),
            ('validation-fixtures',['-m','unittest','discover','-s','/experiment/geometry','-p','reconstruction_validate_test.py','-v']),
        ]
        for name,tail in commands:
            command=base+tail;p=subprocess.run(command,text=True,capture_output=True)
            (stage/(name+'.log')).write_text(p.stdout+p.stderr)
            records.append({'name':name,'command':command,'exit_code':p.returncode})
            print(name,p.returncode,flush=True)
            if p.returncode:
                failure=destination.with_name(destination.name+'-failed')
                stage.rename(failure)
                raise RuntimeError(f'failed check; evidence retained at {failure}')
        assert hashes=={name:sha(HERE/name) for name in FILES}
        r=json.loads((stage/'reconstruction/report.json').read_text())
        v=json.loads((stage/'validator.log').read_text().strip().splitlines()[-1])
        assert v['passed'] and v['source_revalidated'] and v['records']==len(r['rows']) and v['points']==r['points']
        assert v['scalar_max_error_m']<1e-6
        receipt={'schema_version':1,'milestone':'M3','started_utc':start,'ended_utc':datetime.now(timezone.utc).isoformat(),
                 'runtime_lock':json.loads(Path(str(ROOT)+'.lock.json').read_text()),'source_receipt_sha256':sha(SOURCE/'slice.json'),
                 'code_hashes':hashes,'checks':records,'validation':v,'elapsed_seconds':time.monotonic()-begin,
                 'child_peak_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                 'artifacts':{str(p.relative_to(stage)):sha(p) for p in stage.rglob('*') if p.is_file()}}
        (stage/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        stage.rename(destination)
    print('PASS live M3 candidate; pending independent receipt audit:',destination,flush=True)

if __name__=='__main__':main()
