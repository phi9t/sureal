"""Native grouping producer and independent literal source-index reference."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
from advanced.packing import pack_case,ROI

job=json.loads(Path('/tmp/input/job.json').read_text());mode=sys.argv[1]
physical_file=Path('/source')/job['physical_filename']
with physical_file.open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==job['physical_sha256']
with np.load(physical_file,allow_pickle=False) as arrays:physical=arrays['physical_points']
name=job['case'];cell={'grid_fine':.125,'grid_coarse':.5,'ragged_pillars':.25}[name];nx=round(128/cell)
if mode=='producer':
 packed=pack_case(physical,name,seed=job['packing_seed']);np.savez_compressed('/outputs/observations.npz',**{k:packed[k] for k in ['points','counts','coordinates']});np.savez_compressed('/outputs/point-lineage.npz',source_indices=packed['source_indices']);report=packed['counts_report']
else:
 with np.load('/tmp/produced/observations.npz') as arrays:points=arrays['points'];counts=arrays['counts'];coords=arrays['coordinates']
 with np.load('/tmp/produced/point-lineage.npz') as arrays:indices=arrays['source_indices']
 groups={};outside=0
 for index,point in enumerate(physical):
  x,y,z=point[:3]
  if not (-64<=x<64 and -64<=y<64 and -4<=z<6):outside+=1;continue
  ix=min(int(np.floor((x+64)/cell)),nx-1);iy=min(int(np.floor((y+64)/cell)),nx-1);groups.setdefault(iy*nx+ix,[]).append(index)
 rng=np.random.default_rng(job['packing_seed']);keys=sorted(groups);selected=np.arange(len(keys))
 if len(keys)>20000:selected=np.sort(rng.choice(len(keys),20000,replace=False))
 assert len(counts)==len(selected);offset=0;point_drops=0;expected_pillar_points=0
 for row,chosen in enumerate(selected):
  key=keys[chosen];ids=np.asarray(groups[key]);expected_pillar_points+=len(ids)
  if name!='ragged_pillars' and len(ids)>32:point_drops+=len(ids)-32;ids=ids[np.sort(rng.choice(len(ids),32,replace=False))]
  n=len(ids);assert counts[row]==n;np.testing.assert_array_equal(coords[row],[0,0,key//nx,key%nx])
  if name=='ragged_pillars':np.testing.assert_array_equal(indices[offset:offset+n],ids);np.testing.assert_array_equal(points[offset:offset+n],physical[ids]);offset+=n
  else:np.testing.assert_array_equal(indices[row,:n],ids);np.testing.assert_array_equal(points[row,:n],physical[ids]);assert np.all(indices[row,n:]==-1) and np.all(points[row,n:]==0)
 retained=int(counts.sum());assert name!='ragged_pillars' or len(points)==offset==retained
 assert retained==expected_pillar_points-point_drops
 report={'input_points':len(physical),'eligible_points':len(physical)-outside,'outside_roi':outside,'eligible_pillars':len(keys),'retained_pillars':len(selected),'retained_points':retained,'pillar_limit_dropped_points':len(physical)-outside-expected_pillar_points,'point_limit_dropped_points':point_drops,'literal_every_source_index_and_point_exact':True}
 assert outside+report['pillar_limit_dropped_points']+point_drops+retained==len(physical)
 with Path('/tmp/targets/targets.npz').open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==job['targets_sha256']
 boxes=json.loads(Path('/tmp/labels/targets.json').read_text());frame=next(f for f in boxes['frames'] if f['timestamp_micros']==job['timestamp']);kept=indices[indices>=0];cloud=physical[kept,:3];support=[]
 for row in frame['rows']:
  x,y,z,l,w,h,yaw=row['box']
  if row['type'] not in range(1,5) or row['num_lidar_points_in_box']<=0 or not (-64<=x<64 and -64<=y<64 and -4<=z<6):continue
  c,s=np.cos(yaw),np.sin(yaw);d=cloud-[x,y,z];inside=(abs(c*d[:,0]+s*d[:,1])<=l/2)&(abs(-s*d[:,0]+c*d[:,1])<=w/2)&(abs(d[:,2])<=h/2);support.append({'object_id':row['object_id'],'type':row['type'],'retained_measured_points_in_box':int(inside.sum())})
 assert len(support)==73 and set(r['type'] for r in support)==set(range(1,5));report.update({'nativeGT_retained':73,'unchanged_targets_sha256':job['targets_sha256'],'object_point_support':support})
Path('/outputs/check.json').write_text(json.dumps({'case':name,'mode':mode,'packing':report,'input_grid':[nx,nx],'physical_head_spacing_m':.5},indent=2));print('PASS',name,mode)
