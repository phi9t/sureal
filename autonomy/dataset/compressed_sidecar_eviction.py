"""Remove only independently published decoded sidecar payloads."""
import json
from pathlib import Path
from evidence.source_snapshot import file_sha256 as digest

STAGES=['pack-live','hdfs-put','hdfs-download','independent-bundle-live','manifest-put-last','manifest-download']
def evict_sidecars(processing,publication,*,expected_publication_sha256,available_metadata_bytes):
 processing,publication=map(Path,(processing,publication));record=processing/'sidecar-eviction.json'
 if record.exists():raise ValueError('existing eviction evidence must be preserved')
 receipt=publication/'receipt.json'
 if digest(receipt)!=expected_publication_sha256:raise ValueError('trusted publication receipt differs')
 pub=json.loads(receipt.read_text())
 if pub.get('format')!='canonical-ustar-gzip-v1':raise ValueError('explicit compressed publication required')
 for key in ['format','uncompressed_bytes','uncompressed_sha256','archive_bytes','manifest_sha256','files']:
  if pub['archive'].get(key)!=pub['validation'].get(key):raise ValueError('compressed validation identity differs')
 if pub['archive']['format']!=pub['format'] or pub['archive']['sha256']!=pub['validation']['archive_sha256']:raise ValueError('compressed archive identity differs')
 if [c['stage'] for c in pub['checks']]!=STAGES or any(c['exit_code']!=0 for c in pub['checks']):raise ValueError('complete successful publication required')
 for name,h in pub['artifacts'].items():
  relative=Path(name)
  if relative.is_absolute() or '..' in relative.parts:raise ValueError('unsafe publication artifact')
  if digest(publication/relative)!=h:raise ValueError('publication artifact changed')
 trusted=json.loads((publication/'input/trusted.json').read_text());provenance=trusted['provenance']
 if provenance!=pub['validation']['provenance'] or provenance['scene']!=pub['scene'] or provenance['scene_receipt_sha256']!=pub['scene_receipt_sha256'] or provenance['source_receipt_hashes']!=pub['component_receipt_hashes']:raise ValueError('source lineage differs')
 if pub['validation']['files']!=len(trusted['files']):raise ValueError('bundle inventory differs')
 target=pub['archive_hdfs_uri']
 if not isinstance(target,str) or not target.startswith('hdfs://'):raise ValueError('HDFS recovery source required')
 source=processing/'sidecars';files=[];names=set()
 for name,h in trusted['files'].items():
  parts=Path(name).parts
  if len(parts)!=2 or any(x in ('','.', '..') for x in parts) or Path(name).is_absolute():raise ValueError('unsafe sidecar member')
  path=source/name
  if path.parent.is_symlink() or digest(path)!=h:raise ValueError('sidecar artifact changed')
  names.add(name);files.append({'path':str(path),'sha256':h,'size_bytes':path.stat().st_size,'recovery_member':name})
 if {str(p.relative_to(source)) for p in source.rglob('*') if p.is_file() or p.is_symlink()}!=names:raise ValueError('unexpected sidecar artifacts')
 archive=publication/'packed/sidecars.tar.gz'
 if digest(archive)!=pub['archive']['sha256']:raise ValueError('mirrored archive changed')
 files.append({'path':str(archive),'sha256':pub['archive']['sha256'],'size_bytes':archive.stat().st_size,'recovery_member':None})
 result={'archive_format':pub['format'],'uncompressed_sha256':pub['archive']['uncompressed_sha256'],'uncompressed_bytes':pub['archive']['uncompressed_bytes'],'status':'verified sidecar eviction admitted','scene':pub['scene'],'archive_hdfs_uri':target,'archive_sha256':pub['archive']['sha256'],'publication_receipt_sha256':expected_publication_sha256,'files':files,'bytes_evicted':sum(x['size_bytes'] for x in files)}
 encoded=json.dumps(result,indent=2)+'\n'
 if len(encoded.encode())+65536>available_metadata_bytes:raise ValueError('eviction metadata exceeds available capacity')
 with record.open('x') as f:f.write(encoded)
 for row in files:Path(row['path']).unlink()
 result['status']='verified sidecar eviction completed';record.write_text(json.dumps(result,indent=2)+'\n');return result
