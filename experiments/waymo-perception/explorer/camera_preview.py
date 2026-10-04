"""Native FRONT imagery for inspection; no projection or model-input claims."""
import base64,hashlib,io,json,sys
from pathlib import Path
import pyarrow.parquet as pq
from PIL import Image
job=json.loads(Path('/tmp/input/job.json').read_text());record=job['source'];source=Path('/source/camera_image.parquet');assert source.stat().st_size==int(record['source_metadata']['size'])
with source.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==record['sha256']==record['hdfs_roundtrip_sha256']
with source.open('rb') as f:assert base64.b64encode(hashlib.file_digest(f,'md5').digest()).decode()==record['source_metadata']['md5_hash']
assert record['official_split']=='training' and record['research_splits']==['train'];timestamps=set(job['timestamps']);seen=set();report=[]
columns=['key.segment_context_name','key.frame_timestamp_micros','key.camera_name','[CameraImageComponent].image']
for batch in pq.ParquetFile(source).iter_batches(batch_size=1,columns=columns):
 row=batch.to_pylist()[0];timestamp=row['key.frame_timestamp_micros'];camera=row['key.camera_name']
 if timestamp not in timestamps or camera!=1:continue
 assert row['key.segment_context_name']==job['scene'] and timestamp not in seen;seen.add(timestamp);encoded=row['[CameraImageComponent].image'];digest=hashlib.sha256(encoded).hexdigest()
 if sys.argv[1]=='producer':
  (Path('/outputs')/f'{timestamp}-front.jpg').write_bytes(encoded)
  with Image.open(io.BytesIO(encoded)) as image:
   size=list(image.size);image=image.convert('RGB');image.thumbnail((360,240));image.save(Path('/outputs')/f'{timestamp}-thumbnail.jpg',format='JPEG',quality=65)
 else:
  path=Path('/tmp/produced')/f'{timestamp}-front.jpg';assert path.read_bytes()==encoded
  with Image.open(io.BytesIO(encoded)) as image:size=list(image.size)
  with Image.open(Path('/tmp/produced')/f'{timestamp}-thumbnail.jpg') as preview:assert preview.width<=360 and preview.height<=240 and preview.mode=='RGB'
 report.append({'identity':f"{job['scene']}:{timestamp}",'camera':1,'native_image_sha256':digest,'native_size':size,'scope':'native FRONT preview; no camera/LiDAR projection performed'})
assert seen==timestamps;Path('/outputs/check.json').write_text(json.dumps({'frames':report,'source_sha256':record['sha256'],'mode':sys.argv[1]},indent=2));print('PASS native FRONT previews',sys.argv[1],job['scene'],len(report))
