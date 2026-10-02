"""Separate source reconciliation; never trusts producer target/key flags."""
import hashlib
import json
import math
from pathlib import Path
import sys
import numpy as np
from .sensor_records import select_rows, OrderedLookup
from .tracer import _verify_sources


def raw(row,prefix):
    if row[prefix+'.values'] is None:return None
    return np.asarray(row[prefix+'.values']).reshape(row[prefix+'.shape'])


def check_coordinates(xyz,pixels,ri,cal,pixel_pose,frame_pose):
    """Scalar independent equations, sampled uniformly over retained identities."""
    errors=[];h,w=ri.shape[:2];ext=np.asarray(cal['extrinsic']).reshape(4,4)
    incl=cal.get('inclinations')
    for index in np.linspace(0,len(pixels)-1,min(17,len(pixels)),dtype=int):
        y,x=map(int,pixels[index]);r=float(ri[y,x,0])
        e=float(incl[h-1-y]) if incl is not None else cal['inclination_min']+(h-y-.5)/h*(cal['inclination_max']-cal['inclination_min'])
        a=((w-x-.5)/w*2-1)*math.pi-math.atan2(ext[1,0],ext[0,0])
        ray=np.array([r*math.cos(e)*math.cos(a),r*math.cos(e)*math.sin(a),r*math.sin(e),1.])
        v=ext@ray
        if pixel_pose is not None:
            roll,pitch,yaw,tx,ty,tz=pixel_pose[y,x]
            rx=np.array([[1,0,0],[0,math.cos(roll),-math.sin(roll)],[0,math.sin(roll),math.cos(roll)]])
            ry=np.array([[math.cos(pitch),0,math.sin(pitch)],[0,1,0],[-math.sin(pitch),0,math.cos(pitch)]])
            rz=np.array([[math.cos(yaw),-math.sin(yaw),0],[math.sin(yaw),math.cos(yaw),0],[0,0,1]])
            world=np.r_[rz@ry@rx@v[:3]+[tx,ty,tz],1.]
            v=np.linalg.solve(frame_pose,world)
        errors.append(float(np.max(np.abs(v[:3]-xyz[index]))))
    error=max(errors,default=0.)
    if not np.isfinite(error) or error>=1e-6:raise ValueError('independent coordinate mismatch')
    return error


def validate(source,out):
    receipt=json.loads((source/'slice.json').read_text());_verify_sources(source,receipt)
    report=json.loads((out/'report.json').read_text())
    if report['scope']!='full acquired cohort':raise ValueError('full source reconciliation requires full cohort')
    records={}
    for r in report['rows']:
        key=(r['context'],r['timestamp'],r['laser'],r['return'])
        if key in records:raise ValueError('duplicate emitted sensor key')
        expected=f'{key[0]}-{key[1]}-{key[2]}-{key[3]}.npz'
        if r['artifact']!=expected:raise ValueError('artifact identity mismatch')
        records[key]=r
    expected_keys=set();points=0;frames=set();max_error=0.
    for context in receipt['contexts']:
        paths={e['component']:source/e['relative_path'] for e in receipt['objects'] if e['context']==context}
        calibration={r['key.laser_name']:r for r in select_rows(paths['lidar_calibration'])}
        frameposes={r['key.frame_timestamp_micros']:np.asarray(r['[VehiclePoseComponent].world_from_vehicle.transform']).reshape(4,4) for r in select_rows(paths['vehicle_pose'])}
        poses=OrderedLookup(select_rows(paths['lidar_pose']))
        projections=OrderedLookup(select_rows(paths['lidar_camera_projection']))
        labels=OrderedLookup(select_rows(paths['lidar_segmentation']))
        for row in select_rows(paths['lidar']):
            stamp,laser=row['key.frame_timestamp_micros'],row['key.laser_name'];frames.add((context,stamp))
            poserow=poses.get((stamp,laser)) if laser==1 else None
            pose=raw(poserow,'[LiDARPoseComponent].range_image_return1') if poserow else None
            if laser==1 and pose is None:raise ValueError('missing TOP poses')
            c=calibration[laser];prefix='[LiDARCalibrationComponent]'
            cal={'extrinsic':c[prefix+'.extrinsic.transform'],'inclinations':c[prefix+'.beam_inclination.values'],'inclination_min':c[prefix+'.beam_inclination.min'],'inclination_max':c[prefix+'.beam_inclination.max']}
            pr=projections.get((stamp,laser));sr=labels.get((stamp,laser))
            for ret in (1,2):
                ri=raw(row,f'[LiDARComponent].range_image_return{ret}')
                if ri is None:continue
                key=(context,stamp,laser,ret);expected_keys.add(key)
                if key not in records:raise ValueError('missing sensor/return')
                r=records[key];path=out/r['artifact']
                if hashlib.sha256(path.read_bytes()).hexdigest()!=r['sha256']:raise ValueError('artifact digest')
                pixels=np.argwhere(np.isfinite(ri[...,0])&(ri[...,0]>0));y,x=pixels.T
                projection=raw(pr,f'[LiDARCameraProjectionComponent].range_image_return{ret}')
                seg=raw(sr,f'[LiDARSegmentationLabelComponent].range_image_return{ret}') if sr else None
                with np.load(path) as artifact:
                    if not np.array_equal(artifact['pixels'],pixels):raise ValueError('original pixels changed')
                    if not np.array_equal(artifact['physical_features'],ri[y,x,:3]):raise ValueError('physical features changed')
                    if not np.array_equal(artifact['nlz'],ri[y,x,3]):raise ValueError('NLZ metadata changed')
                    if not np.array_equal(artifact['camera_projection'],projection[y,x]):raise ValueError('projection order changed')
                    if (seg is not None)!=('segmentation' in artifact):raise ValueError('segmentation presence changed')
                    if seg is not None and not np.array_equal(artifact['segmentation'],seg[y,x]):raise ValueError('segmentation order changed')
                    if artifact['xyz'].shape!=(len(pixels),3) or not np.isfinite(artifact['xyz']).all():raise ValueError('invalid XYZ')
                    max_error=max(max_error,check_coordinates(artifact['xyz'],pixels,ri,cal,pose,frameposes[stamp] if laser==1 else None))
                if r['points']!=len(pixels) or r['segmentation_present']!=(seg is not None):raise ValueError('coverage mismatch')
                if r['motion']!=('compensated' if laser==1 else 'uncompensated'):raise ValueError('motion policy mismatch')
                points+=len(pixels)
        print('validated source identities/targets',context,flush=True)
    if expected_keys!=set(records) or points!=report['points']:raise ValueError('cohort cardinality mismatch')
    if {p.name for p in out.glob('*.npz')}!={r['artifact'] for r in records.values()}:raise ValueError('unexpected artifacts')
    return {'passed':True,'source_revalidated':True,'records':len(records),'frames':len(frames),'points':points,'scalar_max_error_m':max_error}

if __name__=='__main__':print(json.dumps(validate(Path(sys.argv[1]),Path(sys.argv[2]))))
