#!/usr/bin/env python3
"""Candidate-specific live mathematical geometry gate, following verified M0."""
from datetime import datetime,timezone
import json
from pathlib import Path
import resource
import subprocess
import tempfile
import time

HERE=Path(__file__).resolve().parents[1]
from evidence.source_snapshot import file_sha256
from insula.m0_receipt import validate_receipt
from insula.runtime_identity import verify_rootfs
ROOT=Path.home()/'.cache/waystone/waymo-perception/insula/rootfs-v2'
M0=ROOT.parent/'m0-live-20260930-c'


def main():
    destination=Path(sys.argv[1])
    if destination.exists():raise ValueError('existing output')
    validate_receipt(M0,ROOT,HERE)
    destination.parent.mkdir(parents=True,exist_ok=True)
    started=datetime.now(timezone.utc).isoformat();begin=time.monotonic()
    with tempfile.TemporaryDirectory(dir=destination.parent,prefix='.m2-') as tmp:
        stage=Path(tmp)
        command=[str(HERE/'enter.sh'),'--rootfs',str(ROOT),'--source',str(M0/'input'),'--output',str(stage),
                 '--offline','--','python','-m','unittest','discover','-s','/experiment/geometry','-p','geometry_foundation_test.py','-v']
        p=subprocess.run(command,capture_output=True,text=True)
        log=p.stdout+p.stderr
        (stage/'tests.log').write_text(log)
        # Independently enumerate actual fixture names; require each recorded test.
        import ast
        tree=ast.parse((HERE/'geometry/geometry_foundation_test.py').read_text())
        names={node.name for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name.startswith('test_')}
        assert p.returncode==0 and len(names)==11
        assert all(any(line.startswith(name+' ') and line.endswith(' ... ok') for line in log.splitlines()) for name in names)
        assert 'Ran 11 tests' in log and log.rstrip().endswith('OK')
        files=[HERE/'geometry/verify_geometry.py',HERE/'geometry/geometry_foundation.py',HERE/'geometry/geometry_foundation_test.py',HERE/'enter.sh',HERE/'insula/entry.py']
        hashes={str(f.relative_to(HERE)):file_sha256(f) for f in files}
        lock=json.loads(Path(str(ROOT)+'.lock.json').read_text());verify_rootfs(ROOT,lock['rootfs_sha256'])
        receipt={'schema_version':1,'milestone':'M2','command':command,'exit_code':p.returncode,'started_utc':started,
                 'ended_utc':datetime.now(timezone.utc).isoformat(),'code_hashes':hashes,'runtime_lock':lock,
                 'm0_receipt_sha256':file_sha256(M0/'receipt.json'),
                 'tests':sorted(names),'log_sha256':file_sha256(stage/'tests.log'),
                 'elapsed_seconds':time.monotonic()-begin,'child_peak_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss}
        (stage/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        stage.rename(destination)
    print('PASS independently checked live geometry fixtures:',destination)

if __name__=='__main__':main()
