"""Count unique scientific payloads; atomically link byte-identical immutable files."""
import os,uuid
from pathlib import Path
from evidence.source_snapshot import file_sha256 as sha,require_regular_file

def unique_payload_bytes(root):
 root=Path(root)
 if root.is_symlink():raise ValueError('scientific payload root must not be a symlink: '+str(root))
 if not root.is_dir():raise ValueError('scientific payload root must be a directory: '+str(root))
 seen=set();total=0
 for p in root.rglob('*'):
  if p.is_symlink():raise ValueError('scientific payload entries must not be symlinks: '+str(p))
  if not p.is_file():continue
  require_regular_file(p)
  s=p.stat();key=(s.st_dev,s.st_ino)
  if key not in seen:seen.add(key);total+=s.st_size
 return total

def deduplicate(paths):
 paths=list(map(Path,paths));source=paths[0];digest=sha(source)
 if any(require_regular_file(p)!=p or sha(p)!=digest or p.stat().st_dev!=source.stat().st_dev for p in paths):raise ValueError('Only same-filesystem regular byte-identical files may be linked')
 saved=0
 for p in paths[1:]:
  if p.stat().st_ino==source.stat().st_ino:continue
  temporary=p.with_name(p.name+'.dedup-'+uuid.uuid4().hex)
  try:os.link(source,temporary);os.replace(temporary,p)
  finally:temporary.unlink(missing_ok=True)
  assert sha(p)==digest and p.stat().st_ino==source.stat().st_ino;saved+=p.stat().st_size
 return {'sha256':digest,'paths':list(map(str,paths)),'relinked_bytes':saved}
