#!/usr/bin/env python3
"""Live native replay, independent source reconciliation, and M1 receipt."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
from insula.m0_receipt import validate_receipt
ROOT=Path.home()/'.cache/waystone/waymo-perception/insula/rootfs-v2'
M0=ROOT.parent/'m0-live-20260930-c'
SOURCE=Path.home()/'.cache/waystone/waymo-perception/slices/validation-two-scenes-20260929'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
    validate_receipt(M0,ROOT,HERE)
    start=datetime.now(timezone.utc).isoformat();begin=time.monotonic();checks=[]
    base=[str(HERE/'enter.sh'),'--source',str(SOURCE),'--output',str(out),'--offline','--','python']
    for name,tail in [('inspect',['-m','dataset.tracer','inspect','--sample','/source','--output','/outputs/native']),
                      ('validate',['-m','dataset.tracer','validate','--sample','/source','--output','/outputs/native']),
                      ('adversarial-tests',['-m','unittest','discover','-s','/experiment/dataset','-p','tracer_test.py','-v'])]:
        command=base+tail;p=subprocess.run(command,text=True,capture_output=True)
        (out/(name+'.log')).write_text(p.stdout+p.stderr)
        print(name,p.returncode,flush=True)
        checks.append({'name':name,'command':command,'exit_code':p.returncode})
        if p.returncode:raise RuntimeError('live check failed; unpromoted failure evidence retained')
    assert sha(out/'native/manifest.jsonl')=='70190074c7d443632523a5c3273d5ead74f4fcddea653addee3a2fa2efa01bcf'
    result=json.loads((out/'native/result.json').read_text())
    for file,digest in result['implementation_hashes'].items():assert sha(HERE/file)==digest
    receipt={'schema_version':1,'milestone':'M1','started_utc':start,'ended_utc':datetime.now(timezone.utc).isoformat(),
             'runtime_lock':json.loads(Path(str(ROOT)+'.lock.json').read_text()),'m0_receipt_sha256':sha(M0/'receipt.json'),
             'checks':checks,'source_receipt_sha256':sha(SOURCE/'slice.json'),
             'code_hashes':{str(p.relative_to(HERE)):sha(p) for p in [HERE/'verify-native.py',HERE/'enter.sh',HERE/'insula/entry.py',HERE/'dataset/tracer_test.py']},
             'artifacts':{str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()},
             'elapsed_seconds':time.monotonic()-begin,'child_peak_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS M1 live recipe',out,flush=True)

if __name__=='__main__':main()
