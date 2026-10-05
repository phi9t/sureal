#!/usr/bin/env python3
"""Publish verified decoded components without retaining complete scenes locally."""
import argparse,hashlib,json,subprocess,time,resource
from pathlib import Path
from datetime import datetime,timezone
from insula.entry import launch_plan
from insula.runtime_identity import verify_rootfs
HERE=Path(__file__).resolve().parent
WAYSTONE='/data02/home/philip.yang/workspace/waystone/scripts/waystone'
COMPONENTS=['lidar_calibration','camera_calibration','vehicle_pose','lidar_pose','lidar_camera_projection','lidar_segmentation','lidar_box']

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('processing',type=Path);parser.add_argument('output',type=Path);parser.add_argument('--expected-scene-receipt-sha256',required=True);args=parser.parse_args()
    processing=args.processing.resolve();base=args.output.resolve();scene_receipt=processing/'evidence/reconstruction/receipt.json'
    if sha(scene_receipt)!=args.expected_scene_receipt_sha256:raise ValueError('trusted native scene receipt differs')
    native=json.loads(scene_receipt.read_text());scene=native['scene'];expected={};receipt_hashes={};source_hashes={}
    for component in COMPONENTS:
        p=processing/'evidence'/component/'receipt.json';r=json.loads(p.read_text())
        if r['scene']!=scene or r['component']!=component or r['candidate_hashes']!=native['candidate_hashes'] or any(c['exit_code']!=0 for c in r['checks']):raise ValueError('component source/check identity differs')
        for n,v in r['candidate_hashes'].items():
            if sha(HERE/n)!=v:raise ValueError('processing candidate changed')
        for n,v in r['artifacts'].items():
            if sha(processing/n)!=v:raise ValueError('component artifact changed')
            if n.startswith('sidecars/'+component+'/'):expected[n[len('sidecars/'):]]=v
        receipt_hashes[component]=sha(p);source_hashes[component]={'sha256':r['source_sha256'],'generation':r['source_generation'],'source_record_sha256':r['source_record_sha256']}
    cache=Path.home()/'.cache/waystone/waymo-perception';root=cache/'insula/rootfs-v2';lock=json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,lock['rootfs_sha256'])
    base.mkdir(parents=True,exist_ok=False);inputs=base/'input';inputs.mkdir();packed=base/'packed';packed.mkdir();checked=base/'checked';checked.mkdir()
    provenance={'scene':scene,'official_split':native['official_split'],'research_splits':native['research_splits'],'scene_receipt_sha256':args.expected_scene_receipt_sha256,'source_receipt_hashes':receipt_hashes,'sources':source_hashes}
    (inputs/'trusted.json').write_text(json.dumps({'files':expected,'provenance':provenance},separators=(',',':'))+'\n')
    working_root=cache/'scientific-processing'
    def aggregate_bytes():
        return sum(p.stat().st_size for p in working_root.rglob('*') if p.is_file())
    sizes={n:(processing/'sidecars'/n).stat().st_size for n in expected}
    native_manifest=(json.dumps({'schema_version':1,'provenance':provenance,'files':{n:{'sha256':expected[n],'size_bytes':sizes[n]} for n in sorted(sizes)}},sort_keys=True,indent=2)+'\n').encode()
    logical=sum(512+((v+511)//512)*512 for v in [len(native_manifest),*sizes.values()])+1024
    exact_archive_bytes=((logical+10239)//10240)*10240
    preflight_peak=aggregate_bytes()+exact_archive_bytes+64*1024
    if preflight_peak>=15*1024**3:raise ValueError('bounded packing metadata reserve cannot fit aggregate cap')
    trusted_input_sha256=sha(inputs/'trusted.json')
    names=['publish-scientific-sidecars-bounded.py','pipeline/component_archive.py','pipeline/component_archive_validate.py'];candidates={n:sha(HERE/n) for n in names};checks=[];started=datetime.now(timezone.utc).isoformat();tick=time.monotonic()
    def call(stage,command):
        t=time.monotonic();r=subprocess.run(command,capture_output=True,text=True);log_data=(r.stdout+r.stderr).encode();(base/(stage+'.log')).write_bytes(log_data[:4096]);
        if len(log_data)>4096:raise ValueError('bounded stage log exceeds 4096 bytes')
        checks.append({'stage':stage,'command':command,'exit_code':r.returncode,'elapsed_seconds':time.monotonic()-t})
        if r.returncode:raise RuntimeError(r.stderr)
        print('PASS',stage,flush=True)
    sidecar_bytes=sum(p.stat().st_size for p in (processing/'sidecars').rglob('*') if p.is_file());processing_bytes=sum(p.stat().st_size for p in processing.rglob('*') if p.is_file());other=processing_bytes-sidecar_bytes+sum(p.stat().st_size for p in base.rglob('*') if p.is_file())
    code="import json; from pathlib import Path; from pipeline.component_archive import create_component_archive; d=json.loads(Path('/mnt/trusted.json').read_text()); r=create_component_archive('/source/sidecars','/outputs/sidecars.tar',expected_files=d['files'],provenance=d['provenance'],other_bytes="+str(other)+",budget_bytes=15*1024**3); Path('/outputs/archive.json').write_text(json.dumps(r)); print('PASS native decoded bundle',r['files'],r['archive_bytes'])"
    plan=launch_plan(root,HERE,processing,packed,['python','-c',code]);i=plan.index('--');plan[i:i]=['--ro-bind',str(inputs),'/mnt'];call('pack-live',plan)
    if aggregate_bytes()>15*1024**3:raise ValueError('aggregate packing cap exceeded')
    if sha(inputs/'trusted.json')!=trusted_input_sha256:raise ValueError('temporary trusted input changed')
    if json.loads((packed/'archive.json').read_text())['archive_bytes']!=exact_archive_bytes:raise ValueError('exact archive preflight differs')
    (inputs/'trusted.json').unlink()
    if aggregate_bytes()+1024**2>=15*1024**3:raise ValueError('post-pack receipt reserve cannot fit aggregate cap')
    meta=json.loads((packed/'archive.json').read_text());archive=packed/'sidecars.tar';target=json.loads((HERE/'dataset.lock.json').read_text())['hdfs_root']+'/derived/component-bundles-v1/scientific/'+scene+'/'+meta['sha256']+'.tar'
    call('hdfs-put',[WAYSTONE,'put','--mkdir-parents',str(archive),target]);archive.unlink();call('hdfs-download',[WAYSTONE,'get',target,str(archive)])
    if sha(archive)!=meta['sha256']:raise ValueError('sidecar mirror differs')
    code="import json; from pathlib import Path; from pipeline.component_archive_validate import validate_component_archive; r=validate_component_archive('/source/sidecars.tar',expected_archive_sha256="+repr(meta['sha256'])+",expected_manifest_sha256="+repr(meta['manifest_sha256'])+"); Path('/outputs/bundle-check.json').write_text(json.dumps(r)); print('PASS independent native sidecar bundle',r['files'])"
    call('independent-bundle-live',launch_plan(root,HERE,packed,checked,['python','-c',code]));validation=json.loads((checked/'bundle-check.json').read_text())
    if validation['provenance']!=provenance or validation['files']!=len(expected):raise ValueError('bundle source lineage differs')
    publication={'schema_version':1,'role':'scientific-decoded-components','scene':scene,'official_split':native['official_split'],'research_splits':native['research_splits'],'archive_hdfs_uri':target,'archive':meta,'provenance':provenance}
    p=packed/'publication.json';p.write_text(json.dumps(publication,indent=2)+'\n');manifest_sha=sha(p);call('manifest-put-last',[WAYSTONE,'put',str(p),target+'.json']);mirror=checked/'publication.json';call('manifest-download',[WAYSTONE,'get',target+'.json',str(mirror)])
    if sha(mirror)!=manifest_sha:raise ValueError('sidecar publication mirror differs')
    for n,v in candidates.items():
        if sha(HERE/n)!=v:raise ValueError('publication candidate changed')
    working=processing_bytes+sum(p.stat().st_size for p in base.rglob('*') if p.is_file())
    if aggregate_bytes()>15*1024**3 or working>15*1024**3:raise ValueError('sidecar publication exceeds working cap')
    receipt={'status':'scientific native decoded components independently mirrored live','scene':scene,'checks':checks,'started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-tick,'peak_child_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'runtime_lock':lock,'candidate_hashes':candidates,'scene_receipt_sha256':args.expected_scene_receipt_sha256,'component_receipt_hashes':receipt_hashes,'archive':meta,'archive_hdfs_uri':target,'publication_manifest_sha256':manifest_sha,'validation':validation,'working_set_bytes':working,'artifacts':{str(p.relative_to(base)):sha(p) for p in base.rglob('*') if p.is_file()},'bounded_recovery':{'packing_preflight_peak_bytes':preflight_peak,'packing_metadata_reserve_bytes':64*1024,'post_pack_metadata_reserve_bytes':1024**2,'temporary_trusted_input_sha256':trusted_input_sha256,'aggregate_end_bytes':aggregate_bytes()},'scope':'seven decoded native sidecar families; verified eviction and remaining cohort/task inputs remain open'}
    (base/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    if aggregate_bytes()>15*1024**3:raise ValueError('final aggregate receipt cap exceeded')
    print('PASS immutable native sidecar publication',scene,flush=True)

if __name__=='__main__':main()
