#!/usr/bin/env python3
"""Publish independently verified decoded points; manifest follows mirror checking."""
import argparse,json,time,resource
from pathlib import Path
from datetime import datetime,timezone
from evidence.source_snapshot import file_sha256 as sha
from insula.launch_plan import build_plan, load_default_runtime_lock, record_plan, render_plan, run_plan
from insula.runtime_roots import current_cpu_rootfs
from dataset.blob_storage import blob_transfer_check, default_blob_store, default_store_descriptor, put_blob, scene_archive_blob_key, scene_manifest_blob_key
from dataset.scientific_admission import admit_scene
from dataset.scientific_publication import publication_manifest
from resources.scientific_budget import SCIENTIFIC_WORKING_CAP_BYTES, check_working

HERE=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('processing',type=Path);parser.add_argument('output',type=Path);parser.add_argument('--expected-receipt-sha256',required=True);args=parser.parse_args()
    processing=args.processing.resolve();base=args.output.resolve();rp=processing/'evidence/reconstruction/receipt.json'
    if sha(rp)!=args.expected_receipt_sha256:raise ValueError('independent scene receipt identity differs')
    receipt=json.loads(rp.read_text());scene=receipt['scene'];cache=Path.home()/'.cache/waystone/waymo-perception'
    for p in processing.glob('evidence/*/receipt.json'):
        r=json.loads(p.read_text())
        if r['candidate_hashes']!=receipt['candidate_hashes'] or any(c['exit_code']!=0 for c in r['checks']):raise ValueError('component verification differs')
        for n,v in r['candidate_hashes'].items():
            if sha(HERE/n)!=v:raise ValueError('processing code changed')
        for n,v in r['artifacts'].items():
            if sha(processing/n)!=v:raise ValueError('processing evidence changed')
    m=json.loads((HERE/'dataset/scientific-acquisition.candidate.json').read_text());m['excluded_engineering_segments']=json.loads((HERE/'dataset/scientific-cohort.candidate.json').read_text())['excluded_engineering_segments'];group=m['scenes'][scene]
    sources={c:json.loads((cache/'scientific-source-audit'/f"{group['official_split']}-{c}-{scene}.json").read_text()) for c in m['components']};admitted=admit_scene(m,sources,scene)
    runtime=load_default_runtime_lock(current_cpu_rootfs(cache));lock=runtime.data
    base.mkdir(parents=True,exist_ok=False);packed=base/'packed';packed.mkdir();checked=base/'checked';checked.mkdir();checks=[];started=datetime.now(timezone.utc).isoformat();tick=time.monotonic()
    blob_store=default_blob_store();store_descriptor=default_store_descriptor()
    candidates={n:sha(HERE/n) for n in ['dataset/publish-scientific-scene.py','dataset/scene_archive.py','dataset/scene_archive_validate.py','dataset/scientific_publication.py','resources/scientific_budget.py']}
    def call(name,plan):
        command=render_plan(plan);t=time.monotonic();r=run_plan(plan,capture_output=True,text=True);(base/(name+'.log')).write_text(r.stdout+r.stderr);checks.append({'stage':name,'command':command,'launch_plan':record_plan(plan),'exit_code':r.returncode,'elapsed_seconds':time.monotonic()-t})
        if r.returncode:raise RuntimeError(r.stderr)
        print('PASS',name,flush=True)
    used=sum(p.stat().st_size for p in processing.rglob('*') if p.is_file());pointbytes=sum(p.stat().st_size for p in (processing/'points').iterdir());trusted=receipt['validation']['report_sha256']
    cmd=['python','-c',"import json; from pathlib import Path; from dataset.scene_archive import create_scene_archive; from resources.scientific_budget import SCIENTIFIC_WORKING_CAP_BYTES; r=create_scene_archive('/source/points','/outputs/scene.tar',expected_report_sha256="+repr(trusted)+",sidecar_bytes="+str(used-pointbytes)+",budget_bytes=SCIENTIFIC_WORKING_CAP_BYTES); Path('/outputs/archive.json').write_text(json.dumps(r)); print('PASS deterministic scientific archive',r['archive_bytes'])"]
    call('pack-live',build_plan(runtime,code=HERE,source=processing,output=packed,command=cmd));meta=json.loads((packed/'archive.json').read_text());archive=packed/'scene.tar';target=scene_archive_blob_key(scene)
    archive_blob=put_blob(blob_store,target,archive);checks.append(blob_transfer_check('archive-blob-put',archive_blob));archive.unlink()
    blob_store.get(archive_blob['key'],archive,archive_blob['sha256'],expected_bytes=archive_blob['bytes']);checks.append(blob_transfer_check('archive-blob-fetch',archive_blob))
    if sha(archive)!=meta['sha256']:raise ValueError('archive mirror SHA differs')
    cmd=['python','-c',"import json; from pathlib import Path; from dataset.scene_archive_validate import validate_archive; r=validate_archive('/source/scene.tar',expected_report_sha256="+repr(trusted)+",expected_archive_sha256="+repr(meta['sha256'])+"); Path('/outputs/archive-check.json').write_text(json.dumps(r)); print('PASS independent mirrored archive',r['members'])"]
    call('independent-archive-live',build_plan(runtime,code=HERE,source=packed,output=checked,command=cmd));validation=json.loads((checked/'archive-check.json').read_text())
    pub=publication_manifest(admitted,receipt,meta,validation,mirror_sha256=sha(archive),scene_receipt_sha256=args.expected_receipt_sha256,archive_blob=archive_blob,store_descriptor=store_descriptor)
    if pub['archive_blob']['key']!=target:raise ValueError('publication destination differs')
    p=packed/'publication.json';p.write_text(json.dumps(pub,indent=2)+'\n');expected=sha(p)
    manifest_blob=put_blob(blob_store,scene_manifest_blob_key(scene),p);checks.append(blob_transfer_check('manifest-blob-put-last',manifest_blob));mirror=checked/'publication.json';blob_store.get(manifest_blob['key'],mirror,manifest_blob['sha256'],expected_bytes=manifest_blob['bytes']);checks.append(blob_transfer_check('manifest-blob-fetch',manifest_blob))
    if sha(mirror)!=expected:raise ValueError('publication mirror differs')
    for n,v in candidates.items():
        if sha(HERE/n)!=v:raise ValueError('publication code changed')
    base_bytes=sum(p.stat().st_size for p in base.rglob('*') if p.is_file())
    working=used+base_bytes
    cap_record=check_working(used,base_bytes,where='dataset.publish_scientific_scene.final_working',limit=SCIENTIFIC_WORKING_CAP_BYTES)
    result={'status':'scientific scene archive and manifest independently mirrored; replay remains open','scene':scene,'checks':checks,'started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-tick,'peak_child_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'working_set_bytes':working,'scientific_working_cap':cap_record,'scientific_working_cap_checks':[meta['scientific_working_cap'],cap_record],'runtime_lock':lock,'candidate_hashes':candidates,'scene_receipt_sha256':args.expected_receipt_sha256,'publication_manifest_sha256':expected,'store_descriptor':store_descriptor,'archive_blob':archive_blob,'publication_manifest_blob':manifest_blob,'archive':meta,'archive_validation':validation,'artifacts':{str(p.relative_to(base)):sha(p) for p in base.rglob('*') if p.is_file()},'scope':'decoded point records only; camera images/native detector box assembly and full cohort acceptance remain open'}
    (base/'receipt.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS scientific immutable publication',scene,flush=True)

if __name__=='__main__':main()
