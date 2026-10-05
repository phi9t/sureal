"""Real-frame reconstruction pilot; independent scalar rays verify outputs."""
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import resource
import numpy as np
from dataset.sensor_records import array_field,align_point_targets,select_rows,OrderedLookup
from geometry.geometry import range_to_points


def main():
    source,out=map(Path,sys.argv[1:3]);out.mkdir(exist_ok=False)
    full='--full' in sys.argv[3:]
    receipt=json.loads((source/'slice.json').read_text());rows=[];started=time.monotonic();total_bytes=0;expected_records=0
    for context in receipt['contexts']:
        paths={e['component']:source/e['relative_path'] for e in receipt['objects'] if e['context']==context}
        segkeys=[r['key.frame_timestamp_micros'] for r in select_rows(paths['lidar_segmentation'])]
        alltimes=[r['key.frame_timestamp_micros'] for r in select_rows(paths['vehicle_pose'])]
        chosen=set(alltimes) if full else {segkeys[0],next(t for t in alltimes if t not in segkeys)}
        calibration={r['key.laser_name']:r for r in select_rows(paths['lidar_calibration'])}
        expected_records+=len(chosen)*len(calibration)*2
        frameposes={r['key.frame_timestamp_micros']:np.array(r['[VehiclePoseComponent].world_from_vehicle.transform']).reshape(4,4) for r in select_rows(paths['vehicle_pose'],timestamps=chosen)}
        poses=OrderedLookup(select_rows(paths['lidar_pose'],timestamps=chosen))
        projections=OrderedLookup(select_rows(paths['lidar_camera_projection'],timestamps=chosen))
        labels=OrderedLookup(select_rows(paths['lidar_segmentation'],timestamps=chosen))
        for row in select_rows(paths['lidar'],timestamps=chosen):
            stamp,laser=row['key.frame_timestamp_micros'],row['key.laser_name'];c=calibration[laser];prefix='[LiDARCalibrationComponent]'
            cal={'extrinsic':np.array(c[prefix+'.extrinsic.transform']).reshape(4,4),'inclinations':c[prefix+'.beam_inclination.values'],
                 'inclination_min':c[prefix+'.beam_inclination.min'],'inclination_max':c[prefix+'.beam_inclination.max']}
            key=(stamp,laser)
            poserow=poses.get(key) if laser==1 else None
            pose=array_field(poserow,'[LiDARPoseComponent].range_image_return1') if poserow else None
            projectionrow=projections.get(key);labelrow=labels.get(key)
            if projectionrow is None:raise ValueError('missing projection row')
            for ret in [1,2]:
                ri=array_field(row,f'[LiDARComponent].range_image_return{ret}')
                if ri is None:continue
                motion='compensated' if laser==1 else 'uncompensated'
                point=range_to_points(ri,cal,pixel_pose=pose if laser==1 else None,
                      frame_pose=frameposes[stamp] if laser==1 else None,return_index=ret,motion_policy=motion)
                projection=array_field(projectionrow,f'[LiDARCameraProjectionComponent].range_image_return{ret}')
                seg=array_field(labelrow,f'[LiDARSegmentationLabelComponent].range_image_return{ret}') if labelrow else None
                targets=align_point_targets(point['pixels'],ri.shape[:2],projection,seg)
                pix=point['pixels'];assert np.array_equal(pix,np.argwhere(np.isfinite(ri[...,0])&(ri[...,0]>0)))
                # Independent scalar ray equations for up to 17 distributed valid pixels.
                errors=[];h,w=ri.shape[:2];incl=cal['inclinations'];ext=cal['extrinsic']
                for idx in np.linspace(0,len(pix)-1,min(17,len(pix)),dtype=int):
                    y,x=map(int,pix[idx]);distance=float(ri[y,x,0])
                    elevation=float(incl[h-1-y]) if incl is not None else cal['inclination_min']+(h-y-.5)/h*(cal['inclination_max']-cal['inclination_min'])
                    az=((w-x-.5)/w*2-1)*math.pi-math.atan2(ext[1,0],ext[0,0])
                    v=ext[:3,:3]@np.array([distance*math.cos(elevation)*math.cos(az),distance*math.cos(elevation)*math.sin(az),distance*math.sin(elevation)])+ext[:3,3]
                    if laser==1:
                        roll,pitch,yaw,tx,ty,tz=pose[y,x]
                        rx=np.array([[1,0,0],[0,math.cos(roll),-math.sin(roll)],[0,math.sin(roll),math.cos(roll)]])
                        ry=np.array([[math.cos(pitch),0,math.sin(pitch)],[0,1,0],[-math.sin(pitch),0,math.cos(pitch)]])
                        rz=np.array([[math.cos(yaw),-math.sin(yaw),0],[math.sin(yaw),math.cos(yaw),0],[0,0,1]])
                        world=rz@ry@rx@v+np.array([tx,ty,tz]);frame=frameposes[stamp]
                        v=frame[:3,:3].T@(world-frame[:3,3])
                    errors.append(float(np.max(np.abs(v-point['xyz'][idx]))))
                assert max(errors,default=0)<1e-6
                name=f'{context}-{stamp}-{laser}-{ret}.npz'
                payload={'xyz':point['xyz'],'pixels':pix,'physical_features':point['physical_features'],'nlz':ri[pix[:,0],pix[:,1],3]}
                for k,v in targets.items():
                    if v is not None:payload[k]=v
                np.savez(out/name,**payload)
                total_bytes+=(out/name).stat().st_size
                if total_bytes>16*1024**3:raise ValueError('reconstruction exceeds 16 GiB output budget')
                with np.load(out/name) as stored:
                    assert np.array_equal(stored['pixels'],pix)
                    for k,v in targets.items():
                        if v is not None:assert np.array_equal(stored[k],v)
                rows.append({'context':context,'timestamp':stamp,'laser':laser,'return':ret,'motion':motion,'points':len(pix),'segmentation_present':seg is not None,
                             'scalar_max_error_m':max(errors,default=0),'artifact':name,'sha256':hashlib.sha256((out/name).read_bytes()).hexdigest()})
        print('reconstructed',context,len(chosen),'frames',flush=True)
    assert len(rows)==expected_records
    report={'schema_version':1,'rows':rows,'points':sum(r['points'] for r in rows),'elapsed_seconds':time.monotonic()-started,
            'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'output_bytes':total_bytes,'scope':'full acquired cohort' if full else 'pilot: two frames per scene, not full M3 closure'}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS native reconstruction pilot',report['points'],'points',flush=True)

if __name__=='__main__':main()
