"""A complete verified HDFS publication is necessary before planning release."""
from pathlib import Path
from evidence.source_snapshot import require_regular_file
from resources.resource_archive import safe_name,sha
STAGES=['create-live','archive-put','archive-get','manifest-put','manifest-get','verify-live','rehydrate-live']
def release_plan(root,publication):
 root=Path(root)
 if root.is_symlink() or not root.is_dir():raise ValueError('regular source directory required')
 if publication.get('closure_complete') is not True or publication.get('manifest_readback_exact') is not True:raise ValueError('closed native run and manifest readback required')
 records={};plan=[]
 for chunk in publication['chunks']:
  if not chunk['archive_hdfs_uri'].startswith('hdfs://'):raise ValueError('HDFS recovery URI required')
  if [c['stage'] for c in chunk['checks']]!=STAGES or any(c['exit_code']!=0 for c in chunk['checks']):raise ValueError('every live and transfer gate required')
  for member in chunk['manifest']['members']:
   name=safe_name(member['path'])
   if name in records:raise ValueError('duplicate inventory member')
   records[name]=member;path=root/name
   if not path.is_file() or any(p.is_symlink() for p in [path,*path.parents] if p!=root and root in p.parents):raise ValueError('regular payload without symlinks required')
   try:require_regular_file(path)
   except ValueError as error:raise ValueError('regular payload without symlinks required') from error
   if path.stat().st_size!=member['bytes'] or sha(path)!=member['sha256']:raise ValueError('source payload differs')
   plan.append({**member,'local_path':str(path),'archive_hdfs_uri':chunk['archive_hdfs_uri']})
 inventory={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() or p.is_symlink()}
 if not records or set(records)!=inventory:raise ValueError('complete source inventory required')
 return plan
