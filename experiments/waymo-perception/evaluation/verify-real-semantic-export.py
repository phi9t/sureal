#!/usr/bin/env python3
"""Fresh live real-slice preparation, native export and independent wire check."""
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import resource,subprocess,sys,time
HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE))
from pipeline.runtime_identity import verify_rootfs
from pipeline.insula_entry import launch_plan

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    cache=Path.home()/'.cache/waystone/waymo-perception'
    base=Path(sys.argv[1]).resolve();base.mkdir(parents=True,exist_ok=False)
    prepared=base/'prepared';prepared.mkdir();scored=base/'scored';scored.mkdir()
    geometry=cache/'insula/m3-live-c/reconstruction'
    cpu=cache/'insula/rootfs-v2';metrics=cache/'metrics-rootfs'
    cpulock=json.loads(Path(str(cpu)+'.lock.json').read_text());metriclock=json.loads(Path(str(metrics)+'.lock.json').read_text())
    verify_rootfs(cpu,cpulock['rootfs_sha256']);verify_rootfs(metrics,metriclock['rootfs_sha256'])
    candidates=['evaluation/verify-real-semantic-export.py','evaluation/prepare-real-semantics.py','pipeline/segmentation_export.py','evaluation/validate-real-semantic-wire.py']
    hashes={name:sha(HERE/name) for name in candidates};checks=[];started=datetime.now(timezone.utc).isoformat();begin=time.monotonic()
    stages=[('prepare',cpu,geometry,prepared,['python','/experiment/evaluation/prepare-real-semantics.py']),
            ('export',metrics,prepared,scored,['python','-m','pipeline.segmentation_export','/source/real-semantics.json','/outputs/real-semantics.bin']),
            ('independent-wire',metrics,prepared,scored,['python','/experiment/evaluation/validate-real-semantic-wire.py'])]
    for name,root,source,out,command in stages:
        plan=launch_plan(root,HERE,source,out,command);stage_started=datetime.now(timezone.utc).isoformat();stage_begin=time.monotonic()
        result=subprocess.run(plan,capture_output=True,text=True)
        (base/(name+'.stdout')).write_text(result.stdout);(base/(name+'.stderr')).write_text(result.stderr)
        checks.append({'stage':name,'command':plan,'started_utc':stage_started,'ended_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-stage_begin,'exit_code':result.returncode})
        print(name,result.returncode,result.stdout.strip(),flush=True)
        if result.returncode:raise RuntimeError(result.stderr)
    report=json.loads((scored/'wire-validation.json').read_text());assert report['frames']==60 and report['returns']==120 and report['ordered_points']==9726038
    assert json.loads((prepared/'real-semantic-identities.json').read_text())['returns']==120
    for name,h in hashes.items():assert sha(HERE/name)==h,'candidate changed during run'
    receipt={'stage':'real-slice-native-semantic-export','checks':checks,'runtime_locks':{'cpu':cpulock,'metrics':metriclock},'source_reconstruction_manifest_sha256':sha(geometry/'report.json'),'candidate_hashes':hashes,'started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-begin,'children_peak_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'output_bytes':sum(p.stat().st_size for p in base.rglob('*') if p.is_file()),'artifacts':{str(p.relative_to(base)):sha(p) for p in base.rglob('*') if p.is_file()},'scope':'all engineering-slice labeled TOP points; label replay verifies evaluator only; no model-quality claim'}
    (base/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS full real semantic export receipt')

if __name__=='__main__':main()
