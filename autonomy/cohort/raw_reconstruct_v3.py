"""Small selected sensor slice from four immutable native components, TF-free."""
import base64,hashlib,json,resource,sys,time
from pathlib import Path
import numpy as np
from dataset.sensor_records import select_rows,array_field
from pipeline.geometry import range_to_points
from pipeline.reconstruction_validate import raw,check_coordinates
job=json.loads(Path('/tmp/input/job.json').read_text());mode=sys.argv[1];scene=job['scene'];timestamps=set(job['timestamps']);source=Path('/source');start=time.monotonic()
for component,record in job['sources'].items():
 path=source/(component+'.parquet');assert record['scene']==scene and record['official_split']=='training' and record['research_splits']==['train'];assert path.stat().st_size==int(record['source_metadata']['size'])
 with path.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==record['sha256']==record['hdfs_roundtrip_sha256']
 with path.open('rb') as f:assert base64.b64encode(hashlib.file_digest(f,'md5').digest()).decode()==record['source_metadata']['md5_hash']
calibration={r['key.laser_name']:r for r in select_rows(source/'lidar_calibration.parquet')};assert set(calibration)==set(range(1,6));poses={r['key.frame_timestamp_micros']:r for r in select_rows(source/'lidar_pose.parquet',timestamps=timestamps)};vehicle={r['key.frame_timestamp_micros']:np.asarray(r['[VehiclePoseComponent].world_from_vehicle.transform']).reshape(4,4) for r in select_rows(source/'vehicle_pose.parquet',timestamps=timestamps)};assert set(poses)==set(vehicle)==timestamps
parts={t:{} for t in timestamps};seen=set();max_error=0.;sampled=0
for row in select_rows(source/'lidar.parquet',timestamps=timestamps):
 t,laser=row['key.frame_timestamp_micros'],row['key.laser_name'];assert row['key.segment_context_name']==scene and (t,laser) not in seen;seen.add((t,laser));c=calibration[laser];P='[LiDARCalibrationComponent]';cal={'extrinsic':np.asarray(c[P+'.extrinsic.transform']).reshape(4,4),'inclinations':c[P+'.beam_inclination.values'],'inclination_min':c[P+'.beam_inclination.min'],'inclination_max':c[P+'.beam_inclination.max']};pose=array_field(poses[t],'[LiDARPoseComponent].range_image_return1') if laser==1 else None
 for ret in (1,2):
  ri=array_field(row,f'[LiDARComponent].range_image_return{ret}')
  if ri is None:values=np.empty((0,4));ids=np.empty((0,4),dtype=np.int64);flags=np.empty(0,dtype=np.int64)
  else:
   converted=range_to_points(ri,cal,pixel_pose=pose,frame_pose=vehicle[t] if laser==1 else None,return_index=ret,motion_policy='compensated' if laser==1 else 'uncompensated');values=np.column_stack((converted['xyz'],converted['physical_features'][:,1]));pixels=converted['pixels'];ids=np.column_stack((np.full(len(pixels),laser),np.full(len(pixels),ret),pixels));flags=ri[pixels[:,0],pixels[:,1],3].astype(np.int64)
  parts[t][(laser,ret)]=(values,ids,flags,[laser,ret,int(ri is not None),len(values)])
assert seen=={(t,l) for t in timestamps for l in range(1,6)}
results=[]
for t in sorted(timestamps):
 ordered=[parts[t][k] for k in sorted(parts[t])];arrays={'physical_points':np.concatenate([p[0] for p in ordered]),'measurement_identity':np.concatenate([p[1] for p in ordered]),'evaluation_nlz':np.concatenate([p[2] for p in ordered]),'return_states':np.asarray([p[3] for p in ordered],dtype=np.int64)};assert len(parts[t])==10 and np.isfinite(arrays['physical_points']).all() and np.isin(arrays['evaluation_nlz'],[-1,1]).all()
 if mode=='producer':np.savez(Path('/outputs')/f'{t}.npz',**arrays)
 elif mode=='reference':
  with np.load(Path('/tmp/produced')/f'{t}.npz',allow_pickle=False) as a:
   assert set(a.files)==set(arrays)
   for key,value in arrays.items():np.testing.assert_array_equal(a[key],value)
 else:raise ValueError('Producer/reference required')
 results.append({'identity':f'{scene}:{t}','points':len(arrays['physical_points']),'returns':arrays['return_states'].tolist()})
# Separate scalar geometry and literal measurement-identity reconciliation against native rays.
if mode=='reference':
 for row in select_rows(source/'lidar.parquet',timestamps=timestamps):
  t,laser=row['key.frame_timestamp_micros'],row['key.laser_name'];c=calibration[laser];P='[LiDARCalibrationComponent]';cal={'extrinsic':c[P+'.extrinsic.transform'],'inclinations':c[P+'.beam_inclination.values'],'inclination_min':c[P+'.beam_inclination.min'],'inclination_max':c[P+'.beam_inclination.max']};pose=raw(poses[t],'[LiDARPoseComponent].range_image_return1') if laser==1 else None
  with np.load(Path('/tmp/produced')/f'{t}.npz',allow_pickle=False) as a:physical=a['physical_points'];identities=a['measurement_identity'];nlz=a['evaluation_nlz'];states=a['return_states']
  for ret in (1,2):
   ri=raw(row,f'[LiDARComponent].range_image_return{ret}');mask=(identities[:,0]==laser)&(identities[:,1]==ret);state=states[(states[:,0]==laser)&(states[:,1]==ret)];assert len(state)==1 and state[0,2]==int(ri is not None)
   pixels=np.argwhere(np.isfinite(ri[...,0])&(ri[...,0]>0)) if ri is not None else np.empty((0,2),dtype=np.int64);np.testing.assert_array_equal(identities[mask,2:],pixels);assert state[0,3]==len(pixels)
   if len(pixels):
    np.testing.assert_array_equal(physical[mask,3],ri[pixels[:,0],pixels[:,1],1]);np.testing.assert_array_equal(nlz[mask],ri[pixels[:,0],pixels[:,1],3]);max_error=max(max_error,check_coordinates(physical[mask,:3],pixels,ri,cal,pose,vehicle[t] if laser==1 else None));sampled+=min(17,len(pixels))
assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss<=16*1024**2
Path('/outputs/check.json').write_text(json.dumps({'frames':results,'mode':mode,'scalar_coordinate_max_error_m':max_error,'independent_scalar_points_checked':sampled,'elapsed_seconds':time.monotonic()-start,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'scope':'selected native XYZ/intensity and exact measurement identity/NLZ; no projection, semantic or camera payload'},indent=2));print('PASS selected native reconstruction',mode,scene,len(results),flush=True)
