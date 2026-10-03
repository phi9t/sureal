import sys,json,hashlib,base64,math,time,resource,importlib.util
from pathlib import Path
import pyarrow.parquet as pq
sys.path.insert(0,'/tmp/workers')
assert importlib.util.find_spec('tensorflow') is None
job=json.loads(Path('/tmp/input/job.json').read_text());source=Path('/source/source.parquet');record=job['source'];start=time.monotonic()
assert source.stat().st_size==int(record['source_metadata']['size'])
with source.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==record['sha256']==record['hdfs_roundtrip_sha256']
with source.open('rb') as f:assert base64.b64encode(hashlib.file_digest(f,'md5').digest()).decode()==record['source_metadata']['md5_hash']
parquet=pq.ParquetFile(source)
def rows():
 for batch in parquet.iter_batches(batch_size=1024):yield from batch.to_pylist()
if sys.argv[1]=='producer':
 from overfit_box_targets import select_targets
 result=select_targets(rows(),scene=job['scene'],timestamps=job['timestamps'],expected_rows=record['inventory']['rows'])
elif sys.argv[1]=='reference':
 expected=json.loads(Path('/tmp/produced/targets.json').read_text());frames={t:[] for t in job['timestamps']};seen=set();count=0;P='[LiDARBoxComponent].'
 for row in rows():
  count+=1;context=row['key.segment_context_name'];t=row['key.frame_timestamp_micros'];obj=row['key.laser_object_id'];typ=row[P+'type'];box=[row[P+'box.'+k] for k in ('center.x','center.y','center.z','size.x','size.y','size.z','heading')];points=row[P+'num_lidar_points_in_box'];difficulty=row[P+'difficulty_level.detection']
  assert context==job['scene'] and type(t) is int and 0<=t<2**63 and isinstance(obj,str) and obj and type(typ) is int and 0<=typ<2**31
  assert all(type(x) in (int,float) and math.isfinite(x) for x in box) and min(box[3:6])>0
  assert (t,obj) not in seen;seen.add((t,obj));assert type(points) is int and points>=0 and (difficulty is None or type(difficulty) is int and difficulty in (0,1,2))
  if t in frames:frames[t].append({'context_name':context,'frame_timestamp_micros':t,'object_id':obj,'type':typ,'box':box,'num_lidar_points_in_box':points,'detection_difficulty':difficulty})
 assert count==record['inventory']['rows']
 literal={'scene':job['scene'],'native_rows':count,'frames':[{'timestamp_micros':t,'annotation_state':'native_box_rows_present' if frames[t] else 'no_native_box_rows_coverage_unresolved','rows':sorted(frames[t],key=lambda x:x['object_id'])} for t in sorted(frames)],'scope':'native target/evaluation fields only; no observation features; no empty-label coverage inferred'}
 assert expected==literal;result=literal
else:raise ValueError('producer/reference required')
assert len(result['frames'])==len(job['timestamps']);Path('/outputs/targets.json').write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n');Path('/outputs/resources.json').write_text(json.dumps({'elapsed_seconds':time.monotonic()-start,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}));print('PASS full native box source',sys.argv[1],job['scene'],len(result['frames']),sum(len(f['rows']) for f in result['frames']))
