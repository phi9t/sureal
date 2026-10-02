"""Native all-class fixture packing with separate literal lineage reference."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
from pipeline.pillar_packing import pack_points
job=json.loads(Path('/tmp/input/job.json').read_text());mode=sys.argv[1]
with np.load(Path('/source')/job['physical_filename'],allow_pickle=False) as a:physical=a['physical_points']
with (Path('/source')/job['physical_filename']).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==job['physical_sha256']
roi=np.array(job['roi']);cap=job['max_points'];pillarcap=job['pillar_cap']
if mode=='producer':
 p=pack_points(physical,roi=job['roi'],cell_size=[.25,.25],max_pillars=pillarcap,max_points=cap,seed=job['packing_seed']);np.savez_compressed('/outputs/observations.npz',points=p['points'],counts=p['counts'],coordinates=p['coordinates']);np.savez_compressed('/outputs/point-lineage.npz',source_indices=p['source_indices']);report=p['counts_report']
else:
 with np.load('/tmp/produced/observations.npz') as a:points=a['points'];counts=a['counts'];coordinates=a['coordinates']
 with np.load('/tmp/produced/point-lineage.npz') as a:indices=a['source_indices']
 eligible=np.flatnonzero(np.all((physical[:,:3]>=roi[:3])&(physical[:,:3]<roi[3:]),axis=1));xy=np.minimum(np.floor((physical[eligible,:2]-roi[:2])/.25).astype(np.int64),511);groups={}
 for i,(x,y) in zip(eligible,xy):groups.setdefault(int(y*512+x),[]).append(int(i))
 rng=np.random.default_rng(job['packing_seed']);keys=sorted(groups);selected=np.arange(len(keys))
 if len(selected)>pillarcap:selected=np.sort(rng.choice(len(keys),pillarcap,replace=False))
 assert points.shape==(len(selected),cap,4) and indices.shape==(len(selected),cap)
 for row,k in enumerate(selected):
  key=keys[k];expected=np.asarray(groups[key],dtype=np.int64)
  if len(expected)>cap:expected=expected[np.sort(rng.choice(len(expected),cap,replace=False))]
  n=len(expected);assert counts[row]==n;np.testing.assert_array_equal(indices[row,:n],expected);np.testing.assert_array_equal(points[row,:n],physical[expected]);assert np.all(points[row,n:]==0) and np.all(indices[row,n:]==-1);np.testing.assert_array_equal(coordinates[row],[0,0,key//512,key%512])
 report={'retained_pillars':len(selected),'retained_points':int(counts.sum()),'literal_lineage_and_every_point_exact':True}
 if cap==32:
  with np.load('/tmp/baseline/observations.npz') as a:
   for key,value in [('points',points),('counts',counts),('coordinates',coordinates)]:np.testing.assert_array_equal(a[key],value)
  report['exact_baseline_observations']=True
boxes=json.loads(Path('/tmp/labels/targets.json').read_text());frame=next(f for f in boxes['frames'] if f['timestamp_micros']==job['timestamp']);support=[]
if mode=='reference':
 retained=indices[indices>=0];cloud=physical[retained,:3]
 for r in frame['rows']:
  x,y,z,l,w,h,yaw=r['box'];c,s=np.cos(yaw),np.sin(yaw)
  if r['type'] not in range(1,5) or r['num_lidar_points_in_box']<=0 or not (-64<=x<64 and -64<=y<64 and -4<=z<6):continue
  d=cloud-[x,y,z];inside=(np.abs(c*d[:,0]+s*d[:,1])<=l/2)&(np.abs(-s*d[:,0]+c*d[:,1])<=w/2)&(np.abs(d[:,2])<=h/2);support.append({'object_id':r['object_id'],'type':r['type'],'native_label_points':r['num_lidar_points_in_box'],'retained_measured_points_in_box':int(inside.sum())})
 assert len(support)==73
Path('/outputs/check.json').write_text(json.dumps({'packing':report,'support':support,'mode':mode},indent=2));print('PASS',mode,'native one-frame packing',cap,pillarcap)
