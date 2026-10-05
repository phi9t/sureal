#!/usr/bin/env python3
"""Live structured semantic exporter integration with pinned native scorer."""
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import subprocess,sys,tempfile
HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE))
from pipeline.runtime_identity import verify_rootfs
from pipeline.insula_entry import launch_plan

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    cache=Path.home()/'.cache/waystone/waymo-perception';root=cache/'metrics-rootfs'
    lock=json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,lock['rootfs_sha256'])
    out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False)
    frames=[{'context_name':'semantic-export-fixture','frame_timestamp_micros':10,'returns':[list(range(1,23)),list(range(1,23))*2]}]
    (out/'structured-input.json').write_text(json.dumps(frames)+'\n')
    checks=[];started=datetime.now(timezone.utc).isoformat()
    with tempfile.TemporaryDirectory(dir=cache,prefix='semantic-export-') as tmp:
        source=Path(tmp);(source/'frames.json').write_bytes((out/'structured-input.json').read_bytes())
        commands=[('unit',['python','-m','unittest','discover','-s','/experiment/tests','-p','test_segmentation_export.py']),
                  ('export',['python','-m','pipeline.segmentation_export','/source/frames.json','/outputs/semantic.bin']),
                  ('native-score',['/metrics-build/compute_segmentation_metrics','/outputs/semantic.bin','/outputs/semantic.bin'])]
        for name,command in commands:
            plan=launch_plan(root,HERE,source,out,command);r=subprocess.run(plan,capture_output=True,text=True)
            (out/(name+'.stdout')).write_text(r.stdout);(out/(name+'.stderr')).write_text(r.stderr)
            assert r.returncode==0,r.stderr
            if name=='native-score':assert 'miou=1\n' in r.stdout and not r.stderr
            checks.append({'name':name,'command':plan,'exit_code':r.returncode})
    receipt={'stage':'structured-segmentation-export','runtime_lock':lock,'checks':checks,'started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),'candidate_hashes':{str(p.relative_to(HERE)):sha(p) for p in [Path(__file__),HERE/'pipeline/segmentation_export.py',HERE/'tests/test_segmentation_export.py']},'artifacts':{p.name:sha(p) for p in out.iterdir() if p.is_file()},'scope':'structured exporter analytic integration; real-source identity and export checks pending'}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print('PASS live semantic exporter integration')

if __name__=='__main__':main()
