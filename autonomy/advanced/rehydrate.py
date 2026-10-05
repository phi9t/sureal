"""Bounded verified recovery to a fresh directory; no general tar extraction."""
import shutil,tarfile
from pathlib import Path
from advanced.archive import verify_archive,sha

def rehydrate_archive(archive,manifest,destination,*,max_bytes):
 check=verify_archive(archive,manifest,max_bytes=max_bytes)
 destination=Path(destination)
 destination.mkdir(exist_ok=False)
 with tarfile.open(archive,'r:*') as reader:
  for member in reader:
   target=destination/member.name
   target.parent.mkdir(parents=True,exist_ok=True)
   with reader.extractfile(member) as source,target.open('xb') as output:
    shutil.copyfileobj(source,output,length=1024*1024)
   target.chmod(0o444)
 for record in manifest['members']:
  target=destination/record['path']
  if target.stat().st_size!=record['bytes'] or sha(target)!=record['sha256']:raise ValueError('rehydrated member differs')
 return {**check,'verified_rehydration':True}
