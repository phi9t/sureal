"""Independently read hash-pinned native training metadata in offline Insula."""
import base64,hashlib,json,math
from pathlib import Path
import pyarrow.parquet as pq
source=Path('/source/source.parquet');record=json.loads(Path('/tmp/input/source.json').read_text());assert record['official_split']=='training' and record['research_splits']==['train'];assert source.stat().st_size==int(record['source_metadata']['size'])
raw=source.read_bytes();assert hashlib.sha256(raw).hexdigest()==record['sha256']==record['hdfs_roundtrip_sha256'] and base64.b64encode(hashlib.md5(raw).digest()).decode()==record['source_metadata']['md5_hash']
P='[LiDARBoxComponent].';columns=['key.segment_context_name','key.frame_timestamp_micros','key.laser_object_id',P+'type',P+'num_lidar_points_in_box',*[P+'box.'+x for x in ('center.x','center.y','center.z','size.x','size.y','size.z','heading')]];frames={};seen=set();counts=0
for batch in pq.ParquetFile(source).iter_batches(batch_size=1024,columns=columns):
 for row in batch.to_pylist():
  counts+=1;scene=row['key.segment_context_name'];t=row['key.frame_timestamp_micros'];obj=row['key.laser_object_id'];typ=row[P+'type'];points=row[P+'num_lidar_points_in_box'];b=[row[P+'box.'+x] for x in ('center.x','center.y','center.z','size.x','size.y','size.z','heading')]
  assert scene==record['scene'] and (t,obj) not in seen and all(math.isfinite(x) for x in b) and min(b[3:6])>0;seen.add((t,obj));frame=frames.setdefault(t,{'identity':f'{scene}:{t}','objects':{str(c):[] for c in range(1,5)}})
  if typ in range(1,5) and points>0 and -64<=b[0]<64 and -64<=b[1]<64 and -4<=b[2]<6:frame['objects'][str(typ)].append(obj)
assert counts==record['inventory']['rows']
result={'scene':record['scene'],'native_rows':counts,'source_sha256':record['sha256'],'frames':[dict(f,objects={c:sorted(ids) for c,ids in f['objects'].items()}) for _,f in sorted(frames.items())]}
Path('/outputs/frames.json').write_text(json.dumps(result,sort_keys=True,separators=(',',':')));print('PASS native training coverage scan',record['scene'],counts,len(frames))
