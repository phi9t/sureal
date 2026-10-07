"""Deterministic, bounded archives with independent member/hash verification."""
import gzip,hashlib,tarfile
from pathlib import Path,PurePosixPath
from evidence.source_snapshot import file_sha256,require_regular_file

DEFAULT_LIMIT=768*1024**2

def sha(path):
 return file_sha256(path)

def safe_name(name):
 if not isinstance(name,str) or not name or any(c in name for c in ['\\','\x00','\n','\r']):raise ValueError('unsafe archive member')
 p=PurePosixPath(name)
 if p.is_absolute() or any(s in ('','.', '..') for s in name.split('/')) or str(p)!=name:raise ValueError('unsafe archive member')
 return name

def create_archive(root,paths,archive,*,max_bytes=DEFAULT_LIMIT):
 root=Path(root).resolve();archive=Path(archive);paths=list(paths)
 if not root.is_dir() or not paths or len(set(paths))!=len(paths) or type(max_bytes) is not int or max_bytes<=0:raise ValueError('unique files, root and positive bound required')
 records=[];sources=[];total=0
 for name in sorted(paths):
  safe_name(name);path=root/name
  try:require_regular_file(path)
  except ValueError as error:raise ValueError('regular source files without symlinks required') from error
  if root not in path.resolve().parents:raise ValueError('source outside archive root')
  size=path.stat().st_size;total+=size
  if total>max_bytes:raise ValueError('archive payload exceeds bound')
  records.append({'path':name,'bytes':size,'sha256':sha(path)});sources.append(path)
 if archive.resolve() in [p.resolve() for p in sources]:raise ValueError('archive cannot overwrite a source')
 with archive.open('xb') as raw:
  with gzip.GzipFile(fileobj=raw,mode='wb',filename='',mtime=0,compresslevel=6) as compressed:
   with tarfile.open(fileobj=compressed,mode='w',format=tarfile.PAX_FORMAT) as writer:
    for record,path in zip(records,sources):
     info=tarfile.TarInfo(record['path']);info.size=record['bytes'];info.mode=0o444;info.mtime=0;info.uid=info.gid=0
   with require_regular_file(path).open('rb') as stream:writer.addfile(info,stream)
 manifest={'schema_version':1,'members':records,'payload_bytes':total,'archive_bytes':archive.stat().st_size,'archive_sha256':sha(archive)}
 verify_archive(archive,manifest,max_bytes=max_bytes)
 return manifest

def verify_archive(archive,manifest,*,max_bytes=DEFAULT_LIMIT):
 archive=Path(archive)
 if archive.stat().st_size!=manifest['archive_bytes'] or sha(archive)!=manifest['archive_sha256']:raise ValueError('archive bytes or hash differ')
 records=manifest['members'];expected={safe_name(r['path']):r for r in records}
 if not records or len(expected)!=len(records) or sum(r['bytes'] for r in records)>max_bytes or any(type(r['bytes']) is not int or r['bytes']<0 for r in records):raise ValueError('invalid or unbounded manifest')
 seen=set();total=0
 try:
  with tarfile.open(archive,'r:*') as reader:
   for member in reader:
    name=safe_name(member.name)
    if name in seen or name not in expected or not member.isfile() or member.linkname:raise ValueError('unexpected, duplicate or nonregular member')
    record=expected[name]
    if member.size!=record['bytes']:raise ValueError('member size differs')
    stream=reader.extractfile(member)
    if stream is None or hashlib.file_digest(stream,'sha256').hexdigest()!=record['sha256']:raise ValueError('member hash differs')
    seen.add(name);total+=member.size
 except (tarfile.TarError,OSError,EOFError) as error:raise ValueError('invalid archive') from error
 if seen!=set(expected) or total!=sum(r['bytes'] for r in records):raise ValueError('missing member or incorrect accounting')
 return {'exact_members_and_hashes':True,'members':len(seen),'payload_bytes':total,'archive_sha256':manifest['archive_sha256']}
