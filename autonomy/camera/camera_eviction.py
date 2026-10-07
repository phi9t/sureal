"""Evict independently mirrored and replayed native camera bytes only."""
import json
from pathlib import Path
from dataset.verified_eviction import digest
STAGES=['pack-live','hdfs-put','hdfs-download','independent-bundle-live','manifest-put-last','manifest-download']
def evict_camera(processing,publication,replay,*,expected_publication_sha256,expected_replay_sha256):
 processing,publication,replay=map(Path,(processing,publication,replay));record=processing/'camera-eviction.json'
 if record.exists():raise ValueError('preserve existing camera recovery evidence')
 pp=publication/'receipt.json';rp=replay/'receipt.json'
 if digest(pp)!=expected_publication_sha256 or digest(rp)!=expected_replay_sha256:raise ValueError('trusted camera receipts differ')
 pub=json.loads(pp.read_text());checked=json.loads(rp.read_text())
 if checked['scene']!=pub['scene'] or checked['publication_receipt_sha256']!=expected_publication_sha256:raise ValueError('camera replay/publication lineage differs')
 if [c['stage'] for c in pub['checks']]!=STAGES or any(c['exit_code'] for c in pub['checks']) or len(checked['checks'])!=2 or any(c['exit_code'] for c in checked['checks']):raise ValueError('complete successful live publication/replay required')
 for name,h in pub['artifacts'].items():
  p=Path(name)
  if p.is_absolute() or '..' in p.parts or digest(publication/p)!=h:raise ValueError('camera publication artifact changed')
 trusted=json.loads((publication/'input/trusted.json').read_text())
 if trusted['provenance']!=pub['validation']['provenance'] or pub['validation']['files']!=len(trusted['files']):raise ValueError('camera bundle provenance/inventory differs')
 target=pub['archive_hdfs_uri']
 if not isinstance(target,str) or not target.startswith('hdfs://'):raise ValueError('camera HDFS recovery required')
 source=processing/'sidecars'
 if source.is_symlink():raise ValueError('regular camera source tree required')
 files=[];names=set()
 for name,h in trusted['files'].items():
  parts=Path(name).parts
  if len(parts)!=2 or parts[0] not in ('camera_image','camera_segmentation','camera_box') or parts[1] in ('','.', '..') or Path(name).is_absolute():raise ValueError('unsafe camera recovery member')
  p=source/name
  if p.parent.is_symlink() or digest(p)!=h:raise ValueError('camera original artifact changed')
  names.add(name);files.append({'path':str(p),'sha256':h,'size_bytes':p.stat().st_size,'recovery_member':name})
 if {str(p.relative_to(source)) for p in source.rglob('*') if p.is_file() or p.is_symlink()}!=names:raise ValueError('unexpected camera payloads')
 archive=publication/'packed/camera.tar'
 if digest(archive)!=pub['archive']['sha256']:raise ValueError('mirrored camera archive changed')
 files.append({'path':str(archive),'sha256':pub['archive']['sha256'],'size_bytes':archive.stat().st_size,'recovery_member':None})
 result={'status':'verified camera eviction admitted','scene':pub['scene'],'archive_hdfs_uri':target,'archive_sha256':pub['archive']['sha256'],'publication_receipt_sha256':expected_publication_sha256,'replay_receipt_sha256':expected_replay_sha256,'files':files,'bytes_evicted':sum(f['size_bytes'] for f in files)}
 with record.open('x') as f:f.write(json.dumps(result,indent=2)+'\n')
 for f in files:Path(f['path']).unlink()
 result['status']='verified camera eviction completed';record.write_text(json.dumps(result,indent=2)+'\n');return result
