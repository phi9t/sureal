"""Bounded verified camera replay, with observations and targets kept separate."""
import hashlib,json,re,tarfile
from pathlib import Path
from .component_archive_validate import validate_component_archive
COMPONENTS=['camera_image','camera_segmentation','camera_box']
def iter_camera_records(archive,publication,*,expected_publication_sha256,usage,max_record_bytes=128*1024**2):
 archive,publication=Path(archive),Path(publication)
 if not isinstance(expected_publication_sha256,str) or not re.fullmatch('[0-9a-f]{64}',expected_publication_sha256) or type(max_record_bytes) is not int or max_record_bytes<=0:raise ValueError('trusted publication and positive resident limit required')
 if publication.is_symlink() or not publication.is_file() or hashlib.sha256(publication.read_bytes()).hexdigest()!=expected_publication_sha256:raise ValueError('camera publication differs')
 pub=json.loads(publication.read_text());allowed=pub['research_splits'];official=pub['official_split'];legal={'train','development'} if official=='training' else {'validation','camera_validation'} if official=='validation' else set()
 if pub['schema_version']!=1 or pub['role']!='scientific-native-camera-components' or not isinstance(allowed,list) or not allowed or any(not isinstance(v,str) for v in allowed) or len(set(allowed))!=len(allowed) or usage not in allowed or not set(allowed)<=legal or {'train','development'}<=set(allowed):raise ValueError('camera scientific partition conflict')
 meta=pub['archive'];checked=validate_component_archive(archive,expected_archive_sha256=meta['sha256'],expected_manifest_sha256=meta['manifest_sha256'])
 if checked['provenance']!=pub['provenance'] or checked['files']!=meta['files'] or checked['archive_bytes']!=meta['archive_bytes']:raise ValueError('camera bundle identity differs')
 with tarfile.open(archive,'r:') as tar:
  def load(name,limit):
   member=tar.getmember(name)
   if member.size>limit:raise ValueError('camera resident member cap exceeded')
   return tar.extractfile(member).read()
  bundle=json.loads(load('bundle.json',16*1024**2));files=bundle['files'];seen=set();identities=set()
  def verified(name,limit):
   if name not in files or name in seen:raise ValueError('duplicate or undeclared camera member')
   data=load(name,limit)
   if hashlib.sha256(data).hexdigest()!=files[name]['sha256']:raise ValueError('camera member changed')
   seen.add(name);return data
  for component in COMPONENTS:
   manifest=json.loads(verified(component+'/manifest.json',16*1024**2))
   if manifest['schema_version']!=1 or manifest['component']!=component or manifest['scene']!=pub['scene']:raise ValueError('native camera manifest identity differs')
   for row in manifest['rows']:
    metadata_name=row['metadata']
    if not isinstance(metadata_name,str) or Path(metadata_name).name!=metadata_name:raise ValueError('unsafe camera metadata')
    data=verified(component+'/'+metadata_name,max_record_bytes)
    if hashlib.sha256(data).hexdigest()!=row['metadata_sha256']:raise ValueError('camera metadata identity differs')
    metadata=json.loads(data);fields=metadata['fields'];keys={k:v for k,v in fields.items() if k.startswith('key.')}
    if keys!=row['key'] or keys.get('key.segment_context_name')!=pub['scene']:raise ValueError('camera original keys differ')
    identity=(component,json.dumps(keys,sort_keys=True))
    if identity in identities:raise ValueError('duplicate camera row')
    identities.add(identity);resident=len(data)
    for field,blob in metadata['binary_fields'].items():
     name=blob['artifact']
     if Path(name).name!=name or field in fields:raise ValueError('unsafe or overlapping binary camera field')
     resident+=blob['size_bytes']
     if resident>max_record_bytes:raise ValueError('camera row exceeds resident cap')
     value=verified(component+'/'+name,max_record_bytes)
     if len(value)!=blob['size_bytes'] or hashlib.sha256(value).hexdigest()!=blob['sha256']:raise ValueError('camera original binary differs')
     fields[field]=value
    content={k:v for k,v in fields.items() if not k.startswith('key.')}
    yield {'component':component,'identity':keys,'observations':content if component=='camera_image' else {},'targets':content if component!='camera_image' else {},'provenance':{'source_sha256':manifest['source_sha256'],'publication_sha256':expected_publication_sha256}}
  if seen!=set(files):raise ValueError('unused camera bundle artifacts')
