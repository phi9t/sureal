#!/usr/bin/env python3
"""Live default-metric boundary check, including upstream exit-zero failure."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from insula.entry import launch_plan
from insula.runtime_identity import verify_rootfs
from pipeline.native_detection_adapter import parse_result
CACHE=Path.home()/'.cache/waystone/waymo-perception'
ROOT=CACHE/'metrics-rootfs'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False)
    lock=json.loads(Path(str(ROOT)+'.lock.json').read_text())
    verify_rootfs(ROOT,lock['rootfs_sha256'])
    sourcefile=CACHE/'metrics-source/src/waymo_open_dataset/metrics/tools/compute_detection_metrics_main.cc'
    expected={m.group(1):(float(m.group(2)),float(m.group(3))) for m in re.finditer(r'^// (.+): \[mAP ([^\]]+)\] \[mAPH ([^\]]+)\]',sourcefile.read_text(),re.M)}
    assert len(expected)==32
    begin=time.monotonic();started=datetime.now(timezone.utc).isoformat();checks=[]
    with tempfile.TemporaryDirectory(dir=CACHE,prefix='adapter-input-') as tmp:
        source=Path(tmp);(source/'malformed.bin').write_bytes(b'not a protobuf\xff')
        base='/upstream/src/waymo_open_dataset/metrics/tools/'
        commands=[('fixtures',['python','-m','unittest','discover','-s','/experiment/tests','-p','test_native_detection_adapter.py']),
                  ('valid',['/metrics-build/compute_detection_metrics',base+'fake_predictions.bin',base+'fake_ground_truths.bin']),
                  ('malformed',['/metrics-build/compute_detection_metrics','/source/malformed.bin',base+'fake_ground_truths.bin'])]
        for name,command in commands:
            plan=launch_plan(ROOT,HERE,source,out,command)
            result=subprocess.run(plan,capture_output=True,text=True)
            (out/(name+'.stdout')).write_text(result.stdout);(out/(name+'.stderr')).write_text(result.stderr)
            checks.append({'name':name,'command':plan,'exit_code':result.returncode})
            if name=='fixtures':assert result.returncode==0,result.stderr
            elif name=='valid':
                parsed=parse_result(result.returncode,result.stdout,result.stderr,set(expected))
                for key,(ap,aph) in expected.items():
                    assert abs(parsed['metrics'][key]['AP']-ap)<=1e-6
                    assert abs(parsed['metrics'][key]['APH']-aph)<=1e-6
                (out/'validated-metrics.json').write_text(json.dumps(parsed,indent=2)+'\n')
            else:
                assert result.returncode==0 and 'Failed to parse predictions.' in result.stderr
                try:parse_result(result.returncode,result.stdout,result.stderr,set(expected))
                except ValueError:pass
                else:raise AssertionError('malformed protobuf promoted')
            print(name,'verified',flush=True)
    receipt={'stage':'default-detection-adapter','runtime_lock':lock,'started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),
             'elapsed_seconds':time.monotonic()-begin,'checks':checks,'expected_breakdowns':sorted(expected),
             'candidate_hashes':{str(p.relative_to(HERE)):sha(p) for p in [Path(__file__),HERE/'pipeline/native_detection_adapter.py',HERE/'tests/test_native_detection_adapter.py']},
             'reference_sha256':sha(sourcefile),'artifacts':{p.name:sha(p) for p in out.iterdir() if p.is_file()},
             'scope':'default native 3D CLI boundary only; broader ticket 09 remains open'}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')

if __name__=='__main__':main()
