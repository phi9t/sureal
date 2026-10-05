#!/usr/bin/env python3
"""Resource-measured current native detection export and independent wire replay."""
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import resource,subprocess,sys,time
HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE))
from insula.runtime_identity import verify_rootfs
from insula.entry import launch_plan

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    cache=Path.home()/'.cache/waystone/waymo-perception';root=cache/'metrics-rootfs'
    lock=json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,lock['rootfs_sha256'])
    out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False)
    names=['pipeline/detection_export.py','pipeline/segmentation_export.py','evaluation/real-detection-export-check.py','evaluation/verify-real-detection-export.py']
    hashes={name:sha(HERE/name) for name in names};started=datetime.now(timezone.utc).isoformat();begin=time.monotonic()
    plan=launch_plan(root,HERE,cache/'real-box-preparation-a',out,['python','/experiment/evaluation/real-detection-export-check.py'])
    result=subprocess.run(plan,capture_output=True,text=True);(out/'live.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError(result.stderr)
    validation=json.loads((out/'real-detection-validation.json').read_text());assert validation['source_objects']==38363 and validation['evaluable_predictions']==34630
    nlz=json.loads((cache/'real-nlz-live-a/nlz-flags.json').read_text());assert len(nlz)==38363 and not any(r['overlap_with_nlz'] for r in nlz)
    for name,h in hashes.items():assert sha(HERE/name)==h
    receipt={'stage':'resource-measured-real-detection-export','command':plan,'exit_code':result.returncode,'started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-begin,'children_peak_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'output_bytes':sum(p.stat().st_size for p in out.iterdir() if p.is_file()),'runtime_lock':lock,'candidate_hashes':hashes,'source_hashes':{'real-boxes.json':sha(cache/'real-box-preparation-a/real-boxes.json'),'nlz-flags.json':sha(cache/'real-nlz-live-a/nlz-flags.json')},'artifacts':{p.name:sha(p) for p in out.iterdir() if p.is_file()},'scope':'native box self-replay; all false fixture NLZ flags separately match independently verified real-scene overlap flags; no model quality claim'}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(result.stdout,flush=True)

if __name__=='__main__':main()
