"""Reconstruct native measurements using bounded, verified decoded sidecars."""
import hashlib
import io
import json
from pathlib import Path
import numpy as np
from .geometry import range_to_points
from .scientific_sidecar_reader import iter_sidecar_rows
from .sensor_records import OrderedLookup, array_field, align_point_targets, select_rows

REQUIRED = {'lidar_calibration', 'vehicle_pose', 'lidar_pose',
            'lidar_camera_projection', 'lidar_segmentation'}


def reconstruct_scene(lidar_source, sidecars, output, budget_bytes, *, verified_manifest_hashes):
    lidar_source, sidecars, output = map(Path, (lidar_source, sidecars, output))
    if type(budget_bytes) is not int or budget_bytes <= 0 or output.exists():
        raise ValueError('invalid derived budget or existing output')
    if not REQUIRED <= set(verified_manifest_hashes):
        raise ValueError('missing verified sidecar component')
    manifests = {}
    for component, expected in verified_manifest_hashes.items():
        if not isinstance(component, str) or Path(component).name != component:
            raise ValueError('unsafe component identity')
        path = sidecars/component/'manifest.json'
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('sidecar provenance changed')
        manifests[component] = json.loads(path.read_text())
        if manifests[component]['component'] != component:
            raise ValueError('sidecar component differs')
    scenes = {r['scene'] for r in manifests.values()}
    if len(scenes) != 1:
        raise ValueError('mixed source scenes')
    scene = scenes.pop()
    sidecar_bytes = sum(p.stat().st_size for p in sidecars.rglob('*') if p.is_file())
    if sidecar_bytes >= budget_bytes:
        raise ValueError('sidecars already exhaust derived capacity')
    def decoded(component):
        return iter_sidecar_rows(sidecars/component, expected_manifest_sha256=verified_manifest_hashes[component])
    calibration = {r['key.laser_name']: r for r in decoded('lidar_calibration')}
    if set(calibration) != set(range(1,6)):
        raise ValueError('complete five-LiDAR calibration required')
    frames = {r['key.frame_timestamp_micros']: np.asarray(r['[VehiclePoseComponent].world_from_vehicle.transform']).reshape(4,4)
              for r in decoded('vehicle_pose')}
    if not frames:
        raise ValueError('no native frame poses')
    expected_keys = {(stamp, laser) for stamp in frames for laser in range(1,6)}
    def declared_keys(component):
        return {(r['key']['key.frame_timestamp_micros'],r['key']['key.laser_name']) for r in manifests[component]['rows']}
    if declared_keys('lidar_camera_projection') != expected_keys:
        raise ValueError('projection frame/sensor coverage differs')
    if declared_keys('lidar_pose') != {(stamp,1) for stamp in frames}:
        raise ValueError('missing or orphan TOP pixel poses')
    if not declared_keys('lidar_segmentation') <= {(stamp,1) for stamp in frames}:
        raise ValueError('orphan or non-TOP semantic labels')
    poses = OrderedLookup(decoded('lidar_pose'))
    projections = OrderedLookup(decoded('lidar_camera_projection'))
    labels = OrderedLookup(decoded('lidar_segmentation'))
    output.mkdir(parents=True); rows = []; used = 0; seen = set(); previous = None
    for row in select_rows(lidar_source):
        if row['key.segment_context_name'] != scene:
            raise ValueError('wrong native LiDAR scene')
        stamp, laser = row['key.frame_timestamp_micros'], row['key.laser_name']; key = (stamp,laser)
        if key not in expected_keys or key in seen or (previous is not None and key <= previous):
            raise ValueError('missing, duplicate or unordered LiDAR identity')
        seen.add(key); previous = key
        c = calibration[laser]; prefix = '[LiDARCalibrationComponent]'
        cal = {'extrinsic': np.asarray(c[prefix+'.extrinsic.transform']).reshape(4,4),
               'inclinations': c[prefix+'.beam_inclination.values'],
               'inclination_min': c[prefix+'.beam_inclination.min'], 'inclination_max': c[prefix+'.beam_inclination.max']}
        poserow = poses.get(key) if laser == 1 else None
        pose = array_field(poserow,'[LiDARPoseComponent].range_image_return1') if poserow else None
        if laser == 1 and pose is None:
            raise ValueError('TOP reconstruction requires native pixel pose')
        projectionrow, labelrow = projections.get(key), labels.get(key)
        if projectionrow is None:
            raise ValueError('missing native projection')
        for ret in (1,2):
            ri = array_field(row,f'[LiDARComponent].range_image_return{ret}')
            seg = array_field(labelrow,f'[LiDARSegmentationLabelComponent].range_image_return{ret}') if labelrow else None
            record = {'context': scene, 'timestamp': stamp, 'laser': laser, 'return': ret,
                      'return_present': ri is not None, 'motion': 'compensated' if laser == 1 else 'uncompensated',
                      'segmentation_present': seg is not None, 'points': 0, 'artifact': None, 'sha256': None}
            if ri is not None:
                point = range_to_points(ri,cal,pixel_pose=pose if laser == 1 else None,
                                        frame_pose=frames[stamp] if laser == 1 else None,
                                        return_index=ret,motion_policy=record['motion'])
                projection = array_field(projectionrow,f'[LiDARCameraProjectionComponent].range_image_return{ret}')
                if projection is None:
                    raise ValueError('present return requires native projection payload')
                targets = align_point_targets(point['pixels'],ri.shape[:2],projection,seg)
                pixels = point['pixels']; payload = {'xyz':point['xyz'],'pixels':pixels,
                       'physical_features':point['physical_features'],'nlz':ri[pixels[:,0],pixels[:,1],3]}
                payload.update({name: value for name,value in targets.items() if value is not None})
                buffer = io.BytesIO(); np.savez(buffer,**payload); data = buffer.getvalue()
                if sidecar_bytes + used + len(data) > budget_bytes:
                    raise ValueError('reconstruction exceeds combined derived working set')
                name = f'{scene}-{stamp}-{laser}-{ret}.npz'; (output/name).write_bytes(data); used += len(data)
                record.update(points=len(pixels),artifact=name,sha256=hashlib.sha256(data).hexdigest())
            rows.append(record)
    if seen != expected_keys:
        raise ValueError('incomplete native frame/sensor coverage')
    # Exhaust every native cursor so terminal artifact/inventory checks execute.
    for lookup in (poses,projections,labels):
        while lookup.current is not None:lookup._advance()
    with lidar_source.open('rb') as stream:source_sha = hashlib.file_digest(stream,'sha256').hexdigest()
    report = {'schema_version':1,'scene':scene,'rows':rows,'points':sum(r['points'] for r in rows),
              'source_lidar_sha256':source_sha,'sidecar_manifest_hashes':verified_manifest_hashes,
              'sidecar_bytes':sidecar_bytes,'output_bytes':used,'working_set_bytes':sidecar_bytes+used}
    while True:
        data = (json.dumps(report,sort_keys=True,indent=2)+'\n').encode(); total = used+len(data)
        if report['output_bytes'] == total:break
        report['output_bytes'] = total; report['working_set_bytes'] = sidecar_bytes+total
    if report['working_set_bytes'] > budget_bytes:
        raise ValueError('manifest exceeds combined derived working set')
    (output/'report.json').write_bytes(data)
    return report
