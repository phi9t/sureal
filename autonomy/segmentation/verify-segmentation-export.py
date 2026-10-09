#!/usr/bin/env python3
"""Live structured semantic exporter integration with pinned native scorer."""
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess,sys,tempfile
from evidence.source_snapshot import file_sha256 as sha, require_regular_file
from insula.runtime_identity import verify_rootfs
from insula.entry import launch_plan
from insula.runtime_roots import current_metrics_rootfs
from segmentation.strict_metric_reader import require_perfect_self_score

HERE=Path(__file__).resolve().parents[1]

def artifact_hashes(root):
    artifacts={}
    for path in Path(root).iterdir():
        if path.is_dir() and not path.is_symlink():
            continue
        file_path=require_regular_file(path)
        artifacts[file_path.name]=sha(file_path)
    return artifacts

def main():
    cache=Path.home()/'.cache/waystone/waymo-perception';root=current_metrics_rootfs(cache)
    lock=json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,lock['rootfs_sha256'])
    out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False)
    frames=[{'context_name':'semantic-export-fixture','frame_timestamp_micros':10,'returns':[list(range(1,23)),list(range(1,23))*2]}]
    (out/'structured-input.json').write_text(json.dumps(frames)+'\n')
    checks=[];started=datetime.now(timezone.utc).isoformat()
    with tempfile.TemporaryDirectory(dir=cache,prefix='semantic-export-') as tmp:
        source=Path(tmp);(source/'frames.json').write_bytes((out/'structured-input.json').read_bytes())
        commands=[('unit',['python','-m','unittest','discover','-s','/experiment/segmentation','-p','segmentation_export_test.py']),
                  ('export',['python','-m','segmentation.segmentation_export','/source/frames.json','/outputs/semantic.bin']),
                  ('native-score',['/metrics-build/compute_segmentation_metrics','/outputs/semantic.bin','/outputs/semantic.bin'])]
        for name,command in commands:
            plan=launch_plan(root,HERE,source,out,command);r=subprocess.run(plan,capture_output=True,text=True)
            (out/(name+'.stdout')).write_text(r.stdout);(out/(name+'.stderr')).write_text(r.stderr)
            assert r.returncode==0,r.stderr
            if name=='native-score':
                assert not r.stderr
                require_perfect_self_score(r.stdout)
            checks.append({'name':name,'command':plan,'exit_code':r.returncode})
    candidates=[Path(__file__),HERE/'segmentation/segmentation_export.py',HERE/'segmentation/segmentation_export_test.py',HERE/'segmentation/strict_metric_reader.py']
    receipt={'stage':'structured-segmentation-export','runtime_lock':lock,'checks':checks,'started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),'candidate_hashes':{str(p.relative_to(HERE)):sha(p) for p in candidates},'artifacts':artifact_hashes(out),'scope':'structured exporter analytic integration; real-source identity and export checks pending'}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print('PASS live semantic exporter integration')

if __name__=='__main__':main()
