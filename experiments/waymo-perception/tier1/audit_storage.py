"""Offline real-payload audit of all historical hardlink dedup groups."""
import hashlib,json
from pathlib import Path
candidate=json.loads(Path('/tmp/candidate.json').read_text());prefix=str(Path.home()) # host paths are translated by scientific root marker
count=0;logical=0;unique=0
for group in candidate['groups']:
 keys=set()
 for original in group['paths']:
  relative=original.split('/scientific-processing/',1)[1];p=Path('/source')/relative
  assert p.is_file() and not p.is_symlink() and p.stat().st_size==group['size']
  with p.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==group['sha256']
  s=p.stat();keys.add((s.st_dev,s.st_ino));logical+=s.st_size;count+=1
 assert len(keys)==1;unique+=group['size']
Path('/outputs/check.json').write_text(json.dumps({'all_real_payloads_rehashed_offline':True,'groups':len(candidate['groups']),'paths':count,'logical_group_bytes':logical,'unique_group_bytes':unique,'freed_bytes':logical-unique},indent=2));print('PASS historical payload digests and hardlink groups',len(candidate['groups']),count)
