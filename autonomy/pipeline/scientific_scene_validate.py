"""Independent reconciliation against staged native LiDAR and verified sidecars."""
import hashlib,json
from pathlib import Path
import numpy as np
from dataset.sensor_records import select_rows,OrderedLookup
from dataset.scientific_sidecar_reader import iter_sidecar_rows
from .reconstruction_validate import raw,check_coordinates


def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def validate_scene(lidar_source,sidecars,records,*,verified_manifest_hashes):
    lidar_source,sidecars,records=map(Path,(lidar_source,sidecars,records))
    required={'lidar_calibration','vehicle_pose','lidar_pose','lidar_camera_projection','lidar_segmentation'}
    if not required<=set(verified_manifest_hashes):raise ValueError('missing independent sidecar provenance')
    manifests={}
    for component,expected in verified_manifest_hashes.items():
        if not isinstance(component,str) or Path(component).name!=component or component in ('.','..'):raise ValueError('unsafe component')
        p=sidecars/component/'manifest.json'
        if digest(p)!=expected:raise ValueError('sidecar provenance changed')
        m=json.loads(p.read_text())
        if m['component']!=component:raise ValueError('component identity differs')
        manifests[component]=m
    scenes={m['scene'] for m in manifests.values()}
    if len(scenes)!=1:raise ValueError('mixed scene provenance')
    scene=scenes.pop();report=json.loads((records/'report.json').read_text())
    if report['schema_version']!=1 or report['scene']!=scene or report['source_lidar_sha256']!=digest(lidar_source) or report['sidecar_manifest_hashes']!=verified_manifest_hashes:raise ValueError('reconstruction source provenance differs')
    def decoded(c):return iter_sidecar_rows(sidecars/c,expected_manifest_sha256=verified_manifest_hashes[c])
    calibration={r['key.laser_name']:r for r in decoded('lidar_calibration')}
    frames={r['key.frame_timestamp_micros']:np.asarray(r['[VehiclePoseComponent].world_from_vehicle.transform']).reshape(4,4) for r in decoded('vehicle_pose')}
    if set(calibration)!=set(range(1,6)) or not frames:raise ValueError('incomplete native geometry')
    def declared_keys(component):
        keys=[(r['key']['key.frame_timestamp_micros'],r['key']['key.laser_name']) for r in manifests[component]['rows']]
        if len(keys)!=len(set(keys)):raise ValueError('duplicate sidecar sensor identity')
        return set(keys)
    top={(t,1) for t in frames}
    if declared_keys('lidar_pose')!=top:raise ValueError('missing or orphan TOP poses')
    if declared_keys('lidar_camera_projection')!={(t,l) for t in frames for l in range(1,6)}:raise ValueError('missing or orphan projection identities')
    if not declared_keys('lidar_segmentation')<=top:raise ValueError('orphan or non-TOP segmentation identities')
    expected={(stamp,laser,ret) for stamp in frames for laser in range(1,6) for ret in (1,2)};emitted={}
    for r in report['rows']:
        k=(r['timestamp'],r['laser'],r['return'])
        if r['context']!=scene or k not in expected or k in emitted:raise ValueError('incorrect emitted identity')
        if any(type(v) is not int for v in k) or type(r['points']) is not int or r['points']<0:raise ValueError('invalid identity or count types')
        if type(r['return_present']) is not bool or type(r['segmentation_present']) is not bool:raise ValueError('invalid presence type')
        emitted[k]=r
    if set(emitted)!=expected:raise ValueError('incomplete emitted inventory')
    poses=OrderedLookup(decoded('lidar_pose'));projections=OrderedLookup(decoded('lidar_camera_projection'));labels=OrderedLookup(decoded('lidar_segmentation'))
    seen=set();artifacts=set();points=0;max_error=0.
    for row in select_rows(lidar_source):
        stamp,laser=row['key.frame_timestamp_micros'],row['key.laser_name'];key=(stamp,laser)
        if row['key.segment_context_name']!=scene or key in seen or stamp not in frames or laser not in calibration:raise ValueError('incorrect native source identity')
        seen.add(key);poserow=poses.get(key) if laser==1 else None
        pose=raw(poserow,'[LiDARPoseComponent].range_image_return1') if poserow else None
        if laser==1 and pose is None:raise ValueError('missing TOP pixel pose')
        pr=projections.get(key);sr=labels.get(key)
        if pr is None:raise ValueError('missing native projection')
        c=calibration[laser];p='[LiDARCalibrationComponent]';cal={'extrinsic':c[p+'.extrinsic.transform'],'inclinations':c[p+'.beam_inclination.values'],'inclination_min':c[p+'.beam_inclination.min'],'inclination_max':c[p+'.beam_inclination.max']}
        for ret in (1,2):
            r=emitted[(stamp,laser,ret)];ri=raw(row,f'[LiDARComponent].range_image_return{ret}');seg=raw(sr,f'[LiDARSegmentationLabelComponent].range_image_return{ret}') if sr else None
            if r['motion']!=('compensated' if laser==1 else 'uncompensated') or r['return_present']!=(ri is not None) or r['segmentation_present']!=(seg is not None):raise ValueError('motion or presence changed')
            if ri is None:
                if r['artifact'] is not None or r['sha256'] is not None or r['points']!=0:raise ValueError('absent return has invented payload')
                continue
            name=f'{scene}-{stamp}-{laser}-{ret}.npz'
            if r['artifact']!=name or digest(records/name)!=r['sha256']:raise ValueError('artifact identity or digest changed')
            artifacts.add(name);pixels=np.argwhere(np.isfinite(ri[...,0])&(ri[...,0]>0));y,x=pixels.T
            projection=raw(pr,f'[LiDARCameraProjectionComponent].range_image_return{ret}')
            if projection is None or projection.shape[:2]!=ri.shape[:2] or (seg is not None and seg.shape[:2]!=ri.shape[:2]):raise ValueError('native target shape differs')
            target={'pixels':pixels,'physical_features':ri[y,x,:3].astype(np.float64),'nlz':ri[y,x,3],'camera_projection':projection[y,x]}
            if seg is not None:target['segmentation']=seg[y,x]
            with np.load(records/name,allow_pickle=False) as a:
                if set(a.files)!=set(target)|{'xyz'}:raise ValueError('invented or missing payload field')
                for field,value in target.items():
                    if a[field].dtype!=value.dtype or not np.array_equal(a[field],value,equal_nan=True):raise ValueError('native '+field+' differs')
                xyz=a['xyz']
                if xyz.shape!=(len(pixels),3) or not np.isfinite(xyz).all():raise ValueError('invalid XYZ')
                max_error=max(max_error,check_coordinates(xyz,pixels,ri,cal,pose,frames[stamp] if laser==1 else None))
            if r['points']!=len(pixels):raise ValueError('point count differs')
            points+=len(pixels)
    if seen!={(t,l) for t in frames for l in range(1,6)} or points!=report['points']:raise ValueError('native inventory or total count differs')
    for lookup in (poses,projections,labels):
        while lookup.current is not None:lookup._advance()
    # Exhaust other supplied sidecars too, ensuring their full artifact checks run.
    for c in set(manifests)-required:
        for _ in decoded(c):pass
    if {p.name for p in records.iterdir()}!=artifacts|{'report.json'}:raise ValueError('unexpected scene artifacts')
    return {'passed':True,'scene':scene,'records':len(emitted),'frames':len(frames),'points':points,'source_lidar_sha256':report['source_lidar_sha256'],'report_sha256':digest(records/'report.json'),'sidecar_manifest_hashes':verified_manifest_hashes,'scalar_max_error_m':max_error,'scope':'all native point identities/features/targets exact; physical features losslessly promoted to float64, target dtypes preserved; up to 17 independent scalar coordinate checks per nonempty record'}
