"""Bounded native camera rows with lossless binary payload retention."""
import hashlib,json
from pathlib import Path
import pyarrow.parquet as pq
SUPPORTED={'camera_image','camera_segmentation','camera_box'}
def materialize_camera_component(source,component,scene,output,remaining_bytes):
 source,output=Path(source),Path(output)
 if component not in SUPPORTED or type(remaining_bytes) is not int or remaining_bytes<=0:raise ValueError('declared camera contract and positive budget required')
 if output.exists():raise ValueError('existing output must be preserved')
 output.mkdir(parents=True);native=pq.ParquetFile(source);rows=[];seen=set();used=0
 def encode(value):return (json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode()
 def write(name,data):
  nonlocal used
  if used+len(data)>remaining_bytes:raise ValueError('camera sidecar budget exhausted')
  (output/name).write_bytes(data);used+=len(data);return hashlib.sha256(data).hexdigest()
 for index,batch in enumerate(native.iter_batches(batch_size=1)):
  row=batch.to_pylist()[0];keys={k:v for k,v in row.items() if k.startswith('key.')}
  if keys.get('key.segment_context_name')!=scene:raise ValueError('wrong native camera scene')
  if type(keys.get('key.frame_timestamp_micros')) is not int or keys['key.frame_timestamp_micros']<0 or type(keys.get('key.camera_name')) is not int or not 1<=keys['key.camera_name']<=5:raise ValueError('invalid native camera identity')
  identity=encode(keys)
  if identity in seen:raise ValueError('duplicate native camera identity')
  seen.add(identity);blobs={};fields={};aliases={}
  for name,value in row.items():
   if isinstance(value,bytes):
    artifact=f'{index:06d}-{len(blobs):03d}.bin';blobs[artifact]=value;aliases[name]={'artifact':artifact,'sha256':hashlib.sha256(value).hexdigest(),'size_bytes':len(value)}
   else:fields[name]=value
  metadata=encode({'fields':fields,'binary_fields':aliases});name=f'{index:06d}.json'
  if used+len(metadata)+sum(map(len,blobs.values()))>remaining_bytes:raise ValueError('camera row exceeds remaining capacity')
  for artifact,value in blobs.items():write(artifact,value)
  rows.append({'key':keys,'metadata':name,'metadata_sha256':write(name,metadata)})
 with source.open('rb') as stream:source_hash=hashlib.file_digest(stream,'sha256').hexdigest()
 report={'schema_version':1,'component':component,'scene':scene,'source_sha256':source_hash,'native_schema_sha256':hashlib.sha256(str(native.schema_arrow).encode()).hexdigest(),'rows':rows,'output_bytes':used,'scope':'native bytes/scalars retained; missing box rows do not establish annotated-empty camera coverage'}
 while True:
  data=encode(report);total=used+len(data)
  if report['output_bytes']==total:break
  report['output_bytes']=total
 write('manifest.json',data);return report
