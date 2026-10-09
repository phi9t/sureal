#!/usr/bin/env python3
"""Two independent scientific archive replays against verified native records."""
import argparse,json,resource,runpy,time
from datetime import datetime,timezone
from pathlib import Path
from evidence.source_snapshot import file_sha256 as sha
from insula.launch_plan import build_plan, load_default_runtime_lock, record_plan, render_plan, run_plan
from insula.runtime_roots import current_cpu_rootfs
HERE=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('processing',type=Path);parser.add_argument('publication',type=Path);parser.add_argument('output',type=Path);parser.add_argument('--expected-receipt-sha256',required=True);parser.add_argument('--usage',required=True);args=parser.parse_args()
    processing=args.processing.resolve();published=args.publication.resolve();base=args.output.resolve();rp=published/'receipt.json'
    if sha(rp)!=args.expected_receipt_sha256:raise ValueError('publication receipt changed')
    pubreceipt=json.loads(rp.read_text())
    for n,v in pubreceipt['candidate_hashes'].items():
        if sha(HERE/n)!=v:raise ValueError('publication candidate changed')
    for n,v in pubreceipt['artifacts'].items():
        if sha(published/n)!=v:raise ValueError('publication artifact changed')
    reference=processing/'points';reconstruction=processing/'evidence/reconstruction/receipt.json'
    if sha(reconstruction)!=pubreceipt['scene_receipt_sha256'] or sha(reference/'report.json')!=pubreceipt['archive']['report_sha256']:raise ValueError('native reconstruction reference changed')
    cache=Path.home()/'.cache/waystone/waymo-perception';runtime=load_default_runtime_lock(current_cpu_rootfs(cache));lock=runtime.data
    replay=runpy.run_path(str(HERE/'dataset/verify-archive-dataset.py'))['REPLAY'].replace("usage='engineering'",'usage='+repr(args.usage)).replace('PUBLICATION_HASH',repr(pubreceipt['publication_manifest_sha256']))
    names=['dataset/verify-scientific-replay.py','dataset/verify-archive-dataset.py','dataset/scientific_dataset.py','dataset/scene_archive_validate.py'];candidates={n:sha(HERE/n) for n in names}
    base.mkdir(parents=True,exist_ok=False);checks=[];results=[];started=datetime.now(timezone.utc).isoformat();tick=time.monotonic()
    for index in (1,2):
        out=base/f'replay-{index}';out.mkdir();plan=build_plan(runtime,code=HERE,source=published/'packed',output=out,command=['python','-c',replay],named_inputs={'/opt':reference});command=render_plan(plan);t=time.monotonic();r=run_plan(plan,capture_output=True,text=True);(base/f'replay-{index}.log').write_text(r.stdout+r.stderr);checks.append({'stage':f'replay-{index}','command':command,'launch_plan':record_plan(plan),'exit_code':r.returncode,'elapsed_seconds':time.monotonic()-t})
        if r.returncode:raise RuntimeError(r.stderr)
        results.append(json.loads((out/'replay.json').read_text()));print('PASS scientific replay',index,results[-1]['records'],results[-1]['points'],flush=True)
    if results[0]!=results[1]:raise ValueError('scientific replay results differ')
    for n,v in candidates.items():
        if sha(HERE/n)!=v:raise ValueError('replay candidate changed')
    if sha(rp)!=args.expected_receipt_sha256:raise ValueError('publication evidence changed during replay')
    result={'status':'two scientific native-record archive replays independently checked live','scene':pubreceipt['scene'],'usage':args.usage,'checks':checks,'started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-tick,'peak_child_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'runtime_lock':lock,'candidate_hashes':candidates,'publication_receipt_sha256':args.expected_receipt_sha256,'publication_manifest_sha256':pubreceipt['publication_manifest_sha256'],'validation':results[0],'artifacts':{str(p.relative_to(base)):sha(p) for p in base.rglob('*') if p.is_file()},'scope':'one scientific scene point records; camera/detector input assembly, remaining cohort and protocol acceptance remain open'}
    (base/'receipt.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS scientific replay receipt',flush=True)

if __name__=='__main__':main()
