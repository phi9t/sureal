#!/usr/bin/env python3
"""Run and independently reconcile native segmentation fixture evidence."""
from datetime import datetime,timezone
import json
from pathlib import Path
import sys,time
from evidence.source_snapshot import file_sha256 as sha, require_regular_file
from insula.launch_plan import build_plan, load_default_runtime_lock, record_plan, run_plan
from insula.runtime_roots import current_metrics_rootfs

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
    cache=Path.home()/'.cache/waystone/waymo-perception';runtime=load_default_runtime_lock(current_metrics_rootfs(cache));lock=runtime.data
    out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False)
    plan=build_plan(runtime,code=HERE,source=cache/'insula/m0-live-20260930-c/input',output=out,command=['python','/experiment/segmentation/segmentation-contract-fixtures.py'])
    started=datetime.now(timezone.utc).isoformat();begin=time.monotonic();r=run_plan(plan,capture_output=True,text=True)
    (out/'live.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
    expected={'perfect':1.,'undefined-predictions':0.,'wrong-class':0.,'ignored-groundtruth':1.,'absent-classes':1.}
    records=json.loads((out/'fixture-results.json').read_text());assert {r['fixture'] for r in records}==set(expected)
    for record in records:
        assert record['classes']==22 and record['exit_code']==0
        assert abs(record['observed_miou']-expected[record['fixture']])<1e-6
    candidates=[Path(__file__),HERE/HERE/'segmentation/segmentation-contract-fixtures.py',HERE/'segmentation/strict_metric_reader.py',HERE/'insula/launch_plan.py',HERE/'insula/runtime_roots.py']
    receipt={'stage':'native-segmentation-contract','launch_plan':record_plan(plan),'exit_code':r.returncode,'started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-begin,'runtime_lock':lock,'candidate_hashes':{str(p.relative_to(HERE)):sha(p) for p in candidates},'artifacts':artifact_hashes(out),'scope':'native semantic protobuf/zlib export fixtures; real source export adapter not yet verified'}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print('PASS native segmentation fixtures and independent manifest reconciliation')

if __name__=='__main__':main()
