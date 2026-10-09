#!/usr/bin/env python3
"""Fresh live real-slice preparation, native export and independent wire check."""
from datetime import datetime,timezone
import json
from pathlib import Path
import resource,sys,time
from evidence.source_snapshot import file_sha256 as sha, require_regular_file
from insula.launch_plan import build_plan, load_default_runtime_lock, record_plan, run_plan
from insula.runtime_roots import current_cpu_rootfs, current_metrics_rootfs

HERE=Path(__file__).resolve().parents[1]

def artifact_report(root):
    root=Path(root);artifacts={};total=0
    for path in root.rglob('*'):
        if path.is_dir() and not path.is_symlink():
            continue
        file_path=require_regular_file(path)
        total+=file_path.stat().st_size
        artifacts[str(file_path.relative_to(root))]=sha(file_path)
    return total,artifacts

def main():
    cache=Path.home()/'.cache/waystone/waymo-perception'
    base=Path(sys.argv[1]).resolve();base.mkdir(parents=True,exist_ok=False)
    prepared=base/'prepared';prepared.mkdir();scored=base/'scored';scored.mkdir()
    geometry=cache/'insula/m3-live-c/reconstruction'
    cpu_runtime=load_default_runtime_lock(current_cpu_rootfs(cache));metrics_runtime=load_default_runtime_lock(current_metrics_rootfs(cache))
    cpulock=cpu_runtime.data;metriclock=metrics_runtime.data
    candidates=['segmentation/verify-real-semantic-export.py','segmentation/prepare-real-semantics.py','segmentation/segmentation_export.py','segmentation/validate-real-semantic-wire.py','segmentation/strict_metric_reader.py','insula/launch_plan.py','insula/runtime_roots.py']
    hashes={name:sha(HERE/name) for name in candidates};checks=[];started=datetime.now(timezone.utc).isoformat();begin=time.monotonic()
    stages=[('prepare',cpu_runtime,geometry,prepared,['python','/experiment/segmentation/prepare-real-semantics.py']),
            ('export',metrics_runtime,prepared,scored,['python','-m','segmentation.segmentation_export','/source/real-semantics.json','/outputs/real-semantics.bin']),
            ('independent-wire',metrics_runtime,prepared,scored,['python','/experiment/segmentation/validate-real-semantic-wire.py'])]
    for name,runtime,source,out,command in stages:
        plan=build_plan(runtime,code=HERE,source=source,output=out,command=command);stage_started=datetime.now(timezone.utc).isoformat();stage_begin=time.monotonic()
        result=run_plan(plan,capture_output=True,text=True)
        (base/(name+'.stdout')).write_text(result.stdout);(base/(name+'.stderr')).write_text(result.stderr)
        checks.append({'stage':name,'launch_plan':record_plan(plan),'started_utc':stage_started,'ended_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-stage_begin,'exit_code':result.returncode})
        print(name,result.returncode,result.stdout.strip(),flush=True)
        if result.returncode:raise RuntimeError(result.stderr)
    report=json.loads((scored/'wire-validation.json').read_text());assert report['frames']==60 and report['returns']==120 and report['ordered_points']==9726038
    assert json.loads((prepared/'real-semantic-identities.json').read_text())['returns']==120
    for name,h in hashes.items():assert sha(HERE/name)==h,'candidate changed during run'
    output_bytes,artifacts=artifact_report(base)
    receipt={'stage':'real-slice-native-semantic-export','checks':checks,'runtime_locks':{'cpu':cpulock,'metrics':metriclock},'source_reconstruction_manifest_sha256':sha(geometry/'report.json'),'candidate_hashes':hashes,'started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-begin,'children_peak_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'output_bytes':output_bytes,'artifacts':artifacts,'scope':'all engineering-slice labeled TOP points; label replay verifies evaluator only; no model-quality claim'}
    (base/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS full real semantic export receipt')

if __name__=='__main__':main()
