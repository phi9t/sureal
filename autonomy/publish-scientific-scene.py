#!/usr/bin/env python3
"""Publish independently verified decoded points; manifest follows mirror checking."""
import argparse,hashlib,json,subprocess,time,resource
from pathlib import Path
from datetime import datetime,timezone
from pipeline.insula_entry import launch_plan
from pipeline.runtime_identity import verify_rootfs
from pipeline.scientific_admission import admit_scene
from pipeline.scientific_publication import publication_manifest

HERE=Path(__file__).resolve().parent
WAYSTONE='/data02/home/philip.yang/workspace/waystone/scripts/waystone'

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

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
    m=json.loads((HERE/'scientific-acquisition.candidate.json').read_text());m['excluded_engineering_segments']=json.loads((HERE/'scientific-cohort.candidate.json').read_text())['excluded_engineering_segments'];group=m['scenes'][scene]
    sources={c:json.loads((cache/'scientific-source-audit'/f"{group['official_split']}-{c}-{scene}.json").read_text()) for c in m['components']};admitted=admit_scene(m,sources,scene)
    root=cache/'insula/rootfs-v2';lock=json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,lock['rootfs_sha256'])
    base.mkdir(parents=True,exist_ok=False);packed=base/'packed';packed.mkdir();checked=base/'checked';checked.mkdir();checks=[];started=datetime.now(timezone.utc).isoformat();tick=time.monotonic()
    candidates={n:sha(HERE/n) for n in ['publish-scientific-scene.py','pipeline/scene_archive.py','pipeline/scene_archive_validate.py','pipeline/scientific_publication.py']}
    def call(name,cmd):
        t=time.monotonic();r=subprocess.run(cmd,capture_output=True,text=True);(base/(name+'.log')).write_text(r.stdout+r.stderr);checks.append({'stage':name,'command':cmd,'exit_code':r.returncode,'elapsed_seconds':time.monotonic()-t})
        if r.returncode:raise RuntimeError(r.stderr)
        print('PASS',name,flush=True)
    used=sum(p.stat().st_size for p in processing.rglob('*') if p.is_file());pointbytes=sum(p.stat().st_size for p in (processing/'points').iterdir());trusted=receipt['validation']['report_sha256']
    cmd=['python','-c',"import json; from pathlib import Path; from pipeline.scene_archive import create_scene_archive; r=create_scene_archive('/source/points','/outputs/scene.tar',expected_report_sha256="+repr(trusted)+",sidecar_bytes="+str(used-pointbytes)+",budget_bytes=15*1024**3); Path('/outputs/archive.json').write_text(json.dumps(r)); print('PASS deterministic scientific archive',r['archive_bytes'])"]
    call('pack-live',launch_plan(root,HERE,processing,packed,cmd));meta=json.loads((packed/'archive.json').read_text());archive=packed/'scene.tar';target=json.loads((HERE/'dataset.lock.json').read_text())['hdfs_root']+'/derived/scene-records-v1/scientific/'+scene+'/'+meta['sha256']+'.tar'
    call('hdfs-put',[WAYSTONE,'put','--mkdir-parents',str(archive),target]);archive.unlink()
    call('hdfs-download',[WAYSTONE,'get',target,str(archive)])
    if sha(archive)!=meta['sha256']:raise ValueError('archive mirror SHA differs')
    cmd=['python','-c',"import json; from pathlib import Path; from pipeline.scene_archive_validate import validate_archive; r=validate_archive('/source/scene.tar',expected_report_sha256="+repr(trusted)+",expected_archive_sha256="+repr(meta['sha256'])+"); Path('/outputs/archive-check.json').write_text(json.dumps(r)); print('PASS independent mirrored archive',r['members'])"]
    call('independent-archive-live',launch_plan(root,HERE,packed,checked,cmd));validation=json.loads((checked/'archive-check.json').read_text())
    root_uri=json.loads((HERE/'dataset.lock.json').read_text())['hdfs_root']+'/derived/scene-records-v1'
    pub=publication_manifest(admitted,receipt,meta,validation,mirror_sha256=sha(archive),scene_receipt_sha256=args.expected_receipt_sha256,hdfs_root=root_uri)
    if pub['archive_hdfs_uri']!=target:raise ValueError('publication destination differs')
    p=packed/'publication.json';p.write_text(json.dumps(pub,indent=2)+'\n');expected=sha(p)
    call('manifest-put-last',[WAYSTONE,'put',str(p),target+'.json']);mirror=checked/'publication.json';call('manifest-download',[WAYSTONE,'get',target+'.json',str(mirror)])
    if sha(mirror)!=expected:raise ValueError('publication mirror differs')
    for n,v in candidates.items():
        if sha(HERE/n)!=v:raise ValueError('publication code changed')
    working=used+sum(p.stat().st_size for p in base.rglob('*') if p.is_file())
    if working>15*1024**3:raise ValueError('publication working set exceeds cap')
    result={'status':'scientific scene archive and manifest independently mirrored; replay remains open','scene':scene,'checks':checks,'started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-tick,'peak_child_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'working_set_bytes':working,'runtime_lock':lock,'candidate_hashes':candidates,'scene_receipt_sha256':args.expected_receipt_sha256,'publication_manifest_sha256':expected,'archive_hdfs_uri':target,'archive':meta,'archive_validation':validation,'artifacts':{str(p.relative_to(base)):sha(p) for p in base.rglob('*') if p.is_file()},'scope':'decoded point records only; camera images/native detector box assembly and full cohort acceptance remain open'}
    (base/'receipt.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS scientific immutable publication',scene,flush=True)

if __name__=='__main__':main()
