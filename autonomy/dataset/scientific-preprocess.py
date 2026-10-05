#!/usr/bin/env python3
"""Resumable scientific native sidecar processing; no model training or promotion."""
import argparse
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import resource,subprocess,time
from insula.entry import launch_plan
from insula.runtime_identity import verify_rootfs
from pipeline.scientific_admission import admit_scene
from pipeline.staged_source import staged_source
from insula.staging_lease import staging_lease
from pipeline.scientific_preparation import verified_sidecar_hashes

HERE=Path(__file__).resolve().parent
COMPONENTS=['lidar_calibration','camera_calibration','vehicle_pose','lidar_pose','lidar_camera_projection','lidar_segmentation','lidar_box']
CANDIDATES=['scientific-preprocess.py','pipeline/scientific_component.py','pipeline/scientific_sidecars.py','pipeline/scientific_sidecar_validate.py','pipeline/scientific_admission.py','pipeline/staged_source.py','evidence/source_integrity.py','insula/staging_lease.py','pipeline/sensor_records.py','pipeline/scientific_preparation.py','pipeline/scientific_scene_command.py','pipeline/scientific_scene_validate.py','pipeline/scientific_reconstruction.py','pipeline/scientific_sidecar_reader.py','pipeline/reconstruction_validate.py','pipeline/geometry.py','pipeline/geometry_foundation.py']


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--scene',required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--component',choices=COMPONENTS,action='append')
    parser.add_argument('--reconstruct',action='store_true');args=parser.parse_args()
    if args.reconstruct and args.component:parser.error('--reconstruct requires the full default sidecar set')
    cache=Path.home()/'.cache/waystone/waymo-perception'
    manifest=json.loads((HERE/'scientific-acquisition.candidate.json').read_text())
    manifest['excluded_engineering_segments']=json.loads((HERE/'scientific-cohort.candidate.json').read_text())['excluded_engineering_segments']
    group=manifest['scenes'][args.scene];paths={c:cache/'scientific-source-audit'/f"{group['official_split']}-{c}-{args.scene}.json" for c in manifest['components']}
    records={c:json.loads(path.read_text()) for c,path in paths.items()};admitted=admit_scene(manifest,records,args.scene)
    # Refuse the live owner before creating a partial scene directory. Individual
    # transfers reacquire this same lease for their entire processing lifetime.
    with staging_lease(cache/'raw-staging.lock'):pass
    root=cache/'insula/rootfs-v2';lock=json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,lock['rootfs_sha256'])
    retained=sum(o['size_bytes'] for o in json.loads((HERE/'dataset.lock.json').read_text())['objects'])
    destination=args.output.resolve();destination.mkdir(parents=True,exist_ok=True)
    candidate={name:sha(HERE/name) for name in CANDIDATES};components=args.component or COMPONENTS
    if len(set(components))!=len(components):raise ValueError('duplicate requested component')
    limit=15*1024**3
    for component in components:
        base=destination/'evidence'/component;receipt_path=base/'receipt.json';record=admitted['components'][component]
        if receipt_path.exists():
            previous=json.loads(receipt_path.read_text())
            if previous['candidate_hashes']!=candidate or previous['source_record_sha256']!=sha(paths[component]) or previous['runtime_lock']!=lock:
                raise ValueError('resume identities differ; preserve this candidate and use a new output directory')
            for name,digest in previous['artifacts'].items():
                if sha(destination/name)!=digest:raise ValueError('resume artifact changed')
            print('verified resume',component,flush=True);continue
        if base.exists() or (destination/'sidecars'/component).exists():raise ValueError('unpromoted partial component exists; preserve evidence and use a new output directory')
        used=sum(p.stat().st_size for p in destination.rglob('*') if p.is_file())
        if used>=limit:raise ValueError('scientific sidecar working set exhausted')
        base.mkdir(parents=True);prepared=destination/'sidecars';prepared.mkdir(exist_ok=True);checked=base/'checked';checked.mkdir()
        started=datetime.now(timezone.utc).isoformat();tick=time.monotonic();checks=[]
        with staged_source(record,cache,retained_bytes=retained,limit_bytes=manifest['local_staging_limit_bytes']) as (source,transfer):
            stages=[('decode',prepared,['python','-m','pipeline.scientific_component','decode','/source/source.parquet',component,args.scene,'/outputs/'+component,str(limit-used)]),
                    ('independent-check',checked,['python','-m','pipeline.scientific_component','validate','/source/source.parquet','/opt/'+component,'/outputs/check.json'])]
            for name,out,command in stages:
                plan=launch_plan(root,HERE,source.parent,out,command)
                if name=='independent-check':
                    i=plan.index('--');plan[i:i]=['--ro-bind',str(prepared),'/opt']
                t=time.monotonic();result=subprocess.run(plan,capture_output=True,text=True)
                (base/(name+'.log')).write_text(result.stdout+result.stderr)
                checks.append({'stage':name,'command':plan,'exit_code':result.returncode,'elapsed_seconds':time.monotonic()-t})
                if result.returncode:raise RuntimeError(result.stderr)
            validation=json.loads((checked/'check.json').read_text())
            if validation['source_sha256']!=record['sha256']:raise ValueError('independent source identity differs')
        for name,digest in candidate.items():
            if sha(HERE/name)!=digest:raise ValueError('candidate changed during processing')
        receipt={'status':'scientific native component independently checked live','scene':args.scene,'component':component,'official_split':group['official_split'],'research_splits':group['research_splits'],'source_record_sha256':sha(paths[component]),'source_sha256':record['sha256'],'source_generation':record['source_metadata']['generation'],'transfer':transfer,'checks':checks,'validation':validation,'candidate_hashes':candidate,'runtime_lock':lock,'started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-tick,'peak_child_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'artifacts':{str(p.relative_to(destination)):sha(p) for folder in (base,prepared/component) for p in folder.rglob('*') if p.is_file()},'scope':'scientific component processing only; full scene reconstruction/publication and protocol freeze remain open'}
        encoded=(json.dumps(receipt,indent=2)+'\n').encode()
        if sum(p.stat().st_size for p in destination.rglob('*') if p.is_file())+len(encoded)>limit:raise ValueError('receipt exceeds derived working-set cap')
        receipt_path.write_bytes(encoded);print('verified scientific component',component,validation['rows'],flush=True)
    if args.reconstruct:
        reconstruct(admitted,paths,args.scene,destination,candidate,cache,root,lock,retained,manifest['local_staging_limit_bytes'],limit)


def reconstruct(admitted,paths,scene,destination,candidate,cache,root,lock,retained,raw_limit,derived_limit):
    hashes=verified_sidecar_hashes(destination,COMPONENTS,scene,candidate)
    base=destination/'evidence/reconstruction';receipt_path=base/'receipt.json';record=admitted['components']['lidar']
    if receipt_path.exists():
        previous=json.loads(receipt_path.read_text())
        if previous['candidate_hashes']!=candidate or previous['runtime_lock']!=lock or previous['source_record_sha256']!=sha(paths['lidar']) or previous['sidecar_manifest_hashes']!=hashes:
            raise ValueError('reconstruction resume identities differ')
        for name,digest in previous['artifacts'].items():
            if sha(destination/name)!=digest:raise ValueError('reconstruction resume artifact changed')
        print('verified reconstruction resume',scene,flush=True);return
    if base.exists() or (destination/'points').exists():raise ValueError('unpromoted reconstruction exists; preserve evidence and use a new output directory')
    base.mkdir(parents=True);checked=base/'checked';checked.mkdir()
    (base/'trusted-sidecar-hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
    prepared=destination/'sidecars';sidecar_bytes=sum(p.stat().st_size for p in prepared.rglob('*') if p.is_file())
    used=sum(p.stat().st_size for p in destination.rglob('*') if p.is_file());budget=derived_limit-used+sidecar_bytes
    if budget<=sidecar_bytes:raise ValueError('no remaining reconstruction capacity')
    started=datetime.now(timezone.utc).isoformat();tick=time.monotonic();checks=[]
    with staged_source(record,cache,retained_bytes=retained,limit_bytes=raw_limit) as (source,transfer):
        stages=[('reconstruct',destination,['python','-m','pipeline.scientific_scene_command','reconstruct','/source/source.parquet','/opt','/mnt/trusted-sidecar-hashes.json','/outputs/points',str(budget)]),
                ('independent-scene-check',checked,['python','-m','pipeline.scientific_scene_command','validate','/source/source.parquet','/opt','/mnt/trusted-sidecar-hashes.json','/srv','/outputs/check.json'])]
        for name,out,command in stages:
            plan=launch_plan(root,HERE,source.parent,out,command);i=plan.index('--')
            extra=['--ro-bind',str(prepared),'/opt','--ro-bind',str(base),'/mnt']
            if name=='independent-scene-check':extra+=['--ro-bind',str(destination/'points'),'/srv']
            plan[i:i]=extra;t=time.monotonic();result=subprocess.run(plan,capture_output=True,text=True)
            (base/(name+'.log')).write_text(result.stdout+result.stderr);checks.append({'stage':name,'command':plan,'exit_code':result.returncode,'elapsed_seconds':time.monotonic()-t})
            if result.returncode:raise RuntimeError(result.stderr)
        validation=json.loads((checked/'check.json').read_text())
        if validation['source_lidar_sha256']!=record['sha256'] or validation['scene']!=scene or validation['sidecar_manifest_hashes']!=hashes:raise ValueError('independent scene source differs')
    for name,digest in candidate.items():
        if sha(HERE/name)!=digest:raise ValueError('candidate changed during reconstruction')
    receipt={'status':'scientific native scene independently checked live','scene':scene,'official_split':admitted['official_split'],'research_splits':admitted['research_splits'],'source_record_sha256':sha(paths['lidar']),'source_sha256':record['sha256'],'source_generation':record['source_metadata']['generation'],'sidecar_manifest_hashes':hashes,'candidate_hashes':candidate,'runtime_lock':lock,'transfer':transfer,'checks':checks,'validation':validation,'started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-tick,'peak_child_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'artifacts':{str(p.relative_to(destination)):sha(p) for folder in (base,destination/'points') for p in folder.rglob('*') if p.is_file()},'scope':'scientific source reconstruction only; immutable publication/replay and protocol freeze remain open'}
    encoded=(json.dumps(receipt,indent=2)+'\n').encode()
    if sum(p.stat().st_size for p in destination.rglob('*') if p.is_file())+len(encoded)>derived_limit:raise ValueError('reconstruction evidence exceeds derived capacity')
    receipt_path.write_bytes(encoded);print('verified scientific scene',scene,validation['records'],validation['points'],flush=True)


if __name__=='__main__':main()
