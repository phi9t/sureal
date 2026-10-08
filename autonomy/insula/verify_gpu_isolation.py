#!/usr/bin/env python3
"""Independent offline GPU entry checks and analytic artifact failure injections."""
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import subprocess
import sys

HERE=Path(__file__).resolve().parents[1]
from evidence.source_snapshot import file_sha256 as sha
from insula.runtime_identity import verify_rootfs
CACHE=Path.home()/'.cache/waystone/waymo-perception'

def main():
    candidate=CACHE/'gpu-live-d'
    receipt=json.loads((candidate/'receipt.json').read_text())
    assert receipt['exit_code']==0
    for name,h in receipt['candidate_hashes'].items():assert sha(HERE/name)==h
    for name,h in receipt['artifacts'].items():assert sha(candidate/name)==h
    verify_rootfs(CACHE/'gpu-rootfs',receipt['runtime_lock']['rootfs_sha256'])
    out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False)
    (out/'gpu-probe.json').write_bytes((candidate/'gpu-probe.json').read_bytes())
    plan=receipt['command'].copy();mount=plan.index('--bind');plan[mount+1]=str(out)
    listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(2);port=listener.getsockname()[1]
    # Positive control: the target is live and reachable in the host namespace.
    with socket.create_connection(('127.0.0.1',port),timeout=1):pass
    live,_=listener.accept();live.close()
    code=f'''
import os,json,socket,subprocess
from pathlib import Path
assert os.environ['HOME']=='/tmp/private-home'
assert not any(k in os.environ for k in ['GOOGLE_APPLICATION_CREDENTIALS','AWS_SECRET_ACCESS_KEY','INSULA_HOST_SECRET'])
assert not Path('/root/.config/gcloud').exists()
assert not Path('/dev/nvidia0').exists() and Path('/dev/nvidia1').exists()
for path in ['/source/forbidden-write','/experiment/forbidden-write','/etc/forbidden-write']:
    try:Path(path).write_text('unsafe')
    except OSError:pass
    else:raise AssertionError('readonly mount writable: '+path)
Path('/outputs/writable-check').write_text('ok')
s=socket.socket();s.settimeout(1)
try:s.connect(('127.0.0.1',{port}))
except OSError:pass
else:raise AssertionError('host network reachable')
finally:s.close()
validator=['/opt/waymo/bin/python','/experiment/insula/validate_gpu_probe.py']
p=subprocess.run(validator+['/outputs/gpu-probe.json','/outputs/numeric-verified.json'],capture_output=True,text=True)
assert p.returncode==0,p.stderr
original=json.loads(Path('/outputs/gpu-probe.json').read_text())
for field in ['y','input_gradient','weight_gradient']:
    value=json.loads(json.dumps(original));value['analytic'][field][0][0]+=1
    Path('/outputs/tampered.json').write_text(json.dumps(value))
    result=subprocess.run(validator+['/outputs/tampered.json','/outputs/never-promote.json'],capture_output=True,text=True)
    assert result.returncode!=0 and not Path('/outputs/never-promote.json').exists()
Path('/outputs/isolation.json').write_text(json.dumps({{'assertions':['host positive network control then offline rejection','private HOME and absent credentials','single physical GPU mount','source/experiment/root readonly','output writable','independent numeric checker','three numerical tamper failures']}}))
print('PASS isolation and numerical failure injections')
'''
    plan=plan[:plan.index('--')+1]+['/opt/waymo/bin/python','-c',code]
    started=datetime.now(timezone.utc).isoformat()
    try:result=subprocess.run(plan,capture_output=True,text=True,env={**__import__('os').environ,'INSULA_HOST_SECRET':'must-not-enter'})
    finally:listener.close()
    (out/'live.stdout').write_text(result.stdout);(out/'live.stderr').write_text(result.stderr)
    record={'stage':'gpu-independent-isolation','candidate_receipt_sha256':sha(candidate/'receipt.json'),
            'started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),'command':plan,'exit_code':result.returncode,
            'code_hashes':{str(p.relative_to(HERE)):sha(p) for p in [Path(__file__),HERE/'insula/validate_gpu_probe.py']},
            'runtime_lock':receipt['runtime_lock'],'artifacts':{p.name:sha(p) for p in out.iterdir() if p.is_file()}}
    (out/'receipt.json').write_text(json.dumps(record,indent=2)+'\n')
    print(result.stdout,result.stderr,flush=True)
    assert result.returncode==0,'isolation checks failed'

if __name__=='__main__':main()
