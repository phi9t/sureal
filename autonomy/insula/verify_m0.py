#!/usr/bin/env python3
"""Run and record live M0 checks; promote receipt only after every check passes."""
import sys
import json
import os
from pathlib import Path
import resource
import socket
import subprocess
import tempfile
import time
from datetime import datetime,timezone

HERE=Path(__file__).resolve().parents[1]
from evidence.source_snapshot import file_sha256 as sha
from insula.m0_receipt import candidate_files, validate_receipt
ROOT=Path(os.environ.get('WAYMO_INSULA_ROOT',str(Path.home()/'.cache/waystone/waymo-perception/insula/rootfs-v2')))
CACHE=ROOT.parent

def main():
    destination=Path(sys.argv[1])
    if destination.exists():raise ValueError('refusing existing run')
    destination.parent.mkdir(parents=True,exist_ok=True)
    started=datetime.now(timezone.utc).isoformat()
    began=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='.m0-stage-',dir=destination.parent) as tmp:
        stage=Path(tmp); source=stage/'input';source.mkdir()
        (source/'sentinel').write_text('readonly input\n')
        records=[]
        def run(name,command,expected=0):
            before=time.monotonic()
            p=subprocess.run(command,text=True,capture_output=True)
            (stage/(name+'.log')).write_text(p.stdout+p.stderr)
            records.append({'name':name,'command':command,'exit_code':p.returncode,'expected':expected,'seconds':time.monotonic()-before})
            assert (p.returncode==0 if expected==0 else p.returncode!=0),(name,p.stdout,p.stderr)
        def cmd(out,*tail,root=ROOT,lock=None):
            args=[str(HERE/'enter.sh'),'--rootfs',str(root),'--source',str(source),'--output',str(out),'--offline']
            if lock:args+=['--lock',str(lock)]
            return args+['--',*tail]
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));listener.listen(16)
            port=listener.getsockname()[1]
            with socket.create_connection(('127.0.0.1',port),timeout=1):pass
            records.append({'name':'host_listener_positive_control','port':port,'passed':True})
            for number in range(2):
                out=stage/f'run-{number}';out.mkdir()
                run(f'producer-{number}',cmd(out,'python','-m','insula.m0_probe',str(port)))
                run(f'validator-{number}',cmd(out,'python','-m','insula.m0_validate'))
        out=stage/'failed';out.mkdir()
        bad=stage/'wrong.lock.json';lock=json.loads(Path(str(ROOT)+'.lock.json').read_text());lock['rootfs_sha256']='0'*64;bad.write_text(json.dumps(lock))
        run('wrong-lock',cmd(out,'python','-c','pass',lock=bad),1)
        run('missing-rootfs',cmd(out,'python','-c','pass',root=stage/'missing'),1)
        run('failed-assertion',cmd(out,'python','-c','assert False, "injected check failure"'),1)
        run('failed-command',cmd(out,'python','-c','raise SystemExit(17)'),1)
        assert list(out.iterdir())==[]
        artifacts={}
        for number in range(2):
            artifacts[str(number)]={p.name:sha(p) for p in (stage/f'run-{number}').iterdir()}
        assert artifacts['0']==artifacts['1']
        receipt={'schema_version':1,'milestone':'M0','started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),
                 'runtime_lock':json.loads(Path(str(ROOT)+'.lock.json').read_text()),
                 'code_hashes':{str(p.relative_to(HERE)):sha(p) for p in candidate_files(HERE)},
                 'log_hashes':{p.name:sha(p) for p in stage.glob('*.log')},
                 'checks':records,'artifacts':artifacts,'elapsed_seconds':time.monotonic()-began,
                 'child_peak_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss}
        (stage/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        # Validate closure independently from child-reported flags.
        assert len(records)==9
        assert len(artifacts['0'])==4
        validate_receipt(stage,ROOT,HERE)
        destination.mkdir()
        import shutil
        for p in stage.iterdir():
            if p.name not in {'wrong.lock.json','failed'}:
                if p.is_dir():shutil.copytree(p,destination/p.name)
                else:shutil.copy2(p,destination/p.name)
    print('PASS M0 live checks:',destination/'receipt.json')

if __name__=='__main__':main()
