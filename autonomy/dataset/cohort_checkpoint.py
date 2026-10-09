"""Independently audit trusted retained lifecycle evidence after explicit eviction."""
import json
from pathlib import Path
from dataset.blob_storage import publication_archive_reference
from evidence.source_snapshot import file_sha256 as digest

def verify_checkpoint(path,*,expected_checkpoint_sha256,code_root,expected_runtime_lock,expected_manifest_sha256,expected_source_hashes,path_remap=None):
 path=Path(path);code_root=Path(code_root)
 def relocated(name):
  p=Path(name)
  if '..' in p.parts:raise ValueError('unsafe retained path')
  for original,target in sorted((path_remap or {}).items(),key=lambda item:len(item[0]),reverse=True):
   original=Path(original)
   if p==original or original in p.parents:return Path(target)/p.relative_to(original)
  return p
 if digest(path)!=expected_checkpoint_sha256:raise ValueError('trusted checkpoint differs')
 cp=json.loads(path.read_text())
 if cp['manifest_sha256']!=expected_manifest_sha256 or cp['source_record_hashes']!=expected_source_hashes or cp['runtime_lock']!=expected_runtime_lock:raise ValueError('checkpoint admission/runtime differs')
 if not cp['checks'] or any(c['exit_code'] for c in cp['checks']):raise ValueError('successful lifecycle required')
 documents={};retained=cp['retained_evidence_hashes']
 for name,h in retained.items():
  p=relocated(name)
  if digest(p)!=h:raise ValueError('retained evidence changed')
  if p.suffix=='.json':documents[p]=json.loads(p.read_text())
 def recovery_key(document):
  value=publication_archive_reference(document)
  if isinstance(value,dict):return value['key']
  return value
 publications={recovery_key(d):(p,d) for p,d in documents.items() if ('archive_hdfs_uri' in d or 'archive_blob' in d) and 'archive' in d and 'checks' in d};deleted={};evictions=0;workers=0
 for p,d in documents.items():
  if d.get('status','').startswith('verified ') and d.get('status','').endswith(' eviction completed'):
   target=recovery_key(d)
   if target not in publications:raise ValueError('eviction publication missing')
   publication,pub=publications[target]
   if digest(publication)!=d['publication_receipt_sha256'] or d['archive_sha256']!=pub['archive']['sha256']:raise ValueError('eviction recovery lineage differs')
   if 'replay_receipt_sha256' in d and d['replay_receipt_sha256'] not in retained.values():raise ValueError('eviction replay evidence missing')
   for f in d['files']:
    value=f['path']
    if value.startswith('/outputs/'):actual=p.parent/Path(value).relative_to('/outputs')
    elif value.startswith('/opt/'):actual=publication.parent/Path(value).relative_to('/opt')
    else:raise ValueError('unsafe evicted path namespace')
    if '..' in Path(value).parts or actual.exists() or actual.is_symlink():raise ValueError('evicted payload present or unsafe')
    if actual in deleted and deleted[actual]!=f['sha256']:raise ValueError('conflicting recovery identity')
    deleted[actual]=f['sha256']
   evictions+=1
 for p,d in documents.items():
  if 'candidate_hashes' not in d:continue
  workers+=1
  if d.get('runtime_lock')!=expected_runtime_lock or not d.get('checks') or any(c['exit_code'] for c in d['checks']):raise ValueError('nested live runtime/check differs')
  for name,h in d['candidate_hashes'].items():
   relative=Path(name)
   if relative.is_absolute() or '..' in relative.parts or digest(code_root/relative)!=h:raise ValueError('nested current candidate differs')
  if 'source_record_sha256' in d:
   component=d.get('component','lidar')
   if expected_source_hashes.get(component)!=d['source_record_sha256']:raise ValueError('native source receipt differs')
  if 'admitted_source_record_hashes' in d and d['admitted_source_record_hashes']!=expected_source_hashes:raise ValueError('native source admission differs')
  root=p.parent.parent.parent if p.parent.parent.name=='evidence' else p.parent
  for name,h in d.get('artifacts',{}).items():
   relative=Path(name)
   if relative.is_absolute() or '..' in relative.parts:raise ValueError('unsafe retained artifact')
   artifact=root/relative
   if artifact.exists():
    if digest(artifact)!=h:raise ValueError('surviving native artifact changed')
   elif deleted.get(artifact)!=h:raise ValueError('missing artifact without verified eviction')
 return {'status':'trusted lifecycle retained evidence/current candidates independently reconciled','scene':cp['scene'],'retained_files':len(retained),'worker_receipts':workers,'verified_evictions':evictions,'evicted_artifacts':len(deleted),'scope':'native lifecycle evidence only; protocol/models/generalization remain open'}
