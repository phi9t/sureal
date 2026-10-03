"""Native range channels and independent retained-pixel gather reconciliation."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
from pipeline.sensor_records import select_rows,array_field
from advanced.packing import range_observations

job=json.loads(Path('/tmp/input/job.json').read_text());mode=sys.argv[1];source=Path('/source/source.parquet')
with source.open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==job['raw_sha256']
with Path('/tmp/physical.npz').open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==job['physical_sha256']
with np.load('/tmp/physical.npz',allow_pickle=False) as arrays:physical=arrays['physical_points'];identity=arrays['measurement_identity'];states=arrays['return_states'];assert states.shape==(10,4) and np.all(states[:,2]==1)
with np.load('/tmp/baseline/observations.npz',allow_pickle=False) as arrays:baseline={k:arrays[k] for k in ['points','counts','coordinates']}
with np.load('/tmp/baseline/point-lineage.npz',allow_pickle=False) as arrays:indices=arrays['source_indices']
rows=list(select_rows(source,timestamps={job['timestamp']}));assert len(rows)==5 and {row['key.laser_name'] for row in rows}==set(range(1,6));grids={}
for row in rows:
 assert row['key.segment_context_name']==job['scene']
 for ret in (1,2):grids[row['key.laser_name'],ret]=array_field(row,f'[LiDARComponent].range_image_return{ret}')
if mode=='producer':
 auxiliary=range_observations(grids,physical,identity,indices);np.savez_compressed('/outputs/observations.npz',**baseline,**auxiliary);np.savez_compressed('/outputs/point-lineage.npz',source_indices=indices)
else:
 with np.load('/tmp/produced/observations.npz',allow_pickle=False) as arrays:
  for k,v in baseline.items():np.testing.assert_array_equal(arrays[k],v)
  expected_keys={'points','counts','coordinates','range_pixels'}|{f'range_{kind}_{l}_{r}' for l in range(1,6) for r in (1,2) for kind in ['raw','valid']};assert set(arrays.files)==expected_keys
  total=0
  for l in range(1,6):
   for r in (1,2):
    raw=grids[l,r];assert raw is not None and raw.ndim==3 and raw.shape[2]==4;valid=raw[:,:,0]>0;mask=(identity[:,0]==l)&(identity[:,1]==r);native_pixels=identity[mask,2:];assert len(native_pixels)==int(valid.sum());assert len(set(map(tuple,native_pixels)))==int(valid.sum());assert np.all(valid[native_pixels[:,0],native_pixels[:,1]]);np.testing.assert_array_equal(raw[native_pixels[:,0],native_pixels[:,1],1],physical[mask,3]);expected=np.zeros((*raw.shape[:2],3),dtype=np.float32);expected[valid]=raw[:,:,:3][valid];np.testing.assert_array_equal(arrays[f'range_raw_{l}_{r}'],expected.transpose(2,0,1)[None]);np.testing.assert_array_equal(arrays[f'range_valid_{l}_{r}'],valid[None]);total+=int(valid.sum())
  assert total==len(physical)
  pixels=arrays['range_pixels'];assert pixels.shape==(*indices.shape,3)
  for i in range(len(indices)):
   n=int(baseline['counts'][i]);assert np.all(indices[i,n:]==-1) and np.all(pixels[i,n:]==-1)
   for slot in range(n):
    index=int(indices[i,slot]);l,r,y,x=map(int,identity[index]);np.testing.assert_array_equal(pixels[i,slot],[(l-1)*2+r-1,y,x]);np.testing.assert_array_equal(baseline['points'][i,slot],physical[index])
report={'mode':mode,'native_sensor_returns':10,'native_valid_points':len(physical),'retained_point_slots':int(baseline['counts'].sum()),'native_shapes':{f'{l}:{r}':list(v.shape) for (l,r),v in sorted(grids.items())},'unchanged_baseline_points_counts_coordinates':True,'only_range_intensity_elongation_and_observation_masks':True,'literal_pixel_gather_and_intensity_exact':mode=='reference'};Path('/outputs/check.json').write_text(json.dumps(report,indent=2));print('PASS native range fusion cache',mode)
