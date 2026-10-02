"""Independent Arrow reconciliation of original camera binary/scalar fields."""
import hashlib,json
from pathlib import Path
import pyarrow.parquet as pq

def validate_camera_component(source,output):
 source,output=Path(source),Path(output)
 def require(ok,message):
  if not ok:raise ValueError(message)
 def digest(p):
  require(p.is_file() and not p.is_symlink(),'regular artifact required')
  with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
 report=json.loads((output/'manifest.json').read_text());native=pq.ParquetFile(source)
 require(report['schema_version']==1 and report['source_sha256']==digest(source),'source identity differs')
 require(report['native_schema_sha256']==hashlib.sha256(str(native.schema_arrow).encode()).hexdigest(),'schema differs')
 require(len(report['rows'])==native.metadata.num_rows,'row count differs');files={'manifest.json'};count=0;binary_count=0;seen=set()
 for batch in native.iter_batches(batch_size=1):
  original=batch.to_pylist()[0];record=report['rows'][count];keys={k:v for k,v in original.items() if k.startswith('key.')}
  require(record['key']==keys and keys['key.segment_context_name']==report['scene'],'native keys differ')
  identity=json.dumps(keys,sort_keys=True);require(identity not in seen,'duplicate native keys');seen.add(identity)
  name=record['metadata'];require(Path(name).name==name and name not in files,'unsafe or duplicate metadata');files.add(name)
  require(digest(output/name)==record['metadata_sha256'],'metadata hash differs');metadata=json.loads((output/name).read_text())
  expected_binary={k:v for k,v in original.items() if isinstance(v,bytes)}
  require(metadata['fields']=={k:v for k,v in original.items() if not isinstance(v,bytes)},'scalar or nullable fields differ')
  require(set(metadata['binary_fields'])==set(expected_binary),'binary field inventory differs')
  for field,value in expected_binary.items():
   artifact=metadata['binary_fields'][field];name=artifact['artifact'];require(Path(name).name==name and name not in files,'unsafe or duplicate binary');files.add(name)
   require(digest(output/name)==artifact['sha256'] and (output/name).stat().st_size==artifact['size_bytes'],'binary hash/size differs')
   require((output/name).read_bytes()==value,'original binary differs');binary_count+=1
  count+=1
 require({p.name for p in output.iterdir()}==files,'unexpected camera artifacts')
 total=sum((output/name).stat().st_size for name in files);require(total==report['output_bytes'],'camera byte accounting differs')
 return {'status':'native camera keys/scalars/binary bytes independently reconciled','rows':count,'binary_fields':binary_count,'output_bytes':total,'source_sha256':report['source_sha256']}
