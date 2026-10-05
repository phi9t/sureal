#!/usr/bin/env python3
"""M3 live full-cohort reconstruction and independent validation receipt."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from insula.m0_receipt import validate_receipt
ROOT=Path.home()/'.cache/waystone/waymo-perception/insula/rootfs-v2'
M0=ROOT.parent/'m0-live-20260930-c'
SOURCE=Path.home()/'.cache/waystone/waymo-perception/slices/validation-two-scenes-20260929'
FILES=['verify-reconstruction.py','enter.sh','insula/entry.py','insula/runtime_identity.py',
       'pipeline/geometry.py','pipeline/geometry_foundation.py','dataset/sensor_records.py',
       'pipeline/reconstruction_probe.py','pipeline/reconstruction_validate.py','pipeline/tracer.py',
       'pipeline/tracer_contracts.py','tests/test_geometry.py','dataset/sensor_records_test.py','tests/test_reconstruction_validation.py']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

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
        commands=[('producer',['-m','pipeline.reconstruction_probe','/source','/outputs/reconstruction','--full']),
                  ('validator',['-m','pipeline.reconstruction_validate','/source','/outputs/reconstruction'])]
        commands +=[(name,['-m','unittest','discover','-s','/experiment/tests','-p',file,'-v']) for name,file in
                     [('ray-fixtures','test_geometry.py'),('identity-fixtures','test_sensor_records.py'),('validation-fixtures','test_reconstruction_validation.py')]]
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
