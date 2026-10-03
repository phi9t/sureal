"""Append-only evidence-indexed research notes with a verifiable hash chain."""
import datetime,fcntl,hashlib,json,os
from pathlib import Path
CATEGORIES={'observation','hypothesis','decision','follow_up'}
def digest(path):
 with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def fsync_directory(path):
 descriptor=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(descriptor)
 finally:os.close(descriptor)
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def read_entries(path):
 path=Path(path)
 if not path.exists():return []
 entries=[];previous=None
 for line in path.read_text().splitlines():
  if not line:raise ValueError('blank or partial journal entry')
  entry=json.loads(line);claimed=entry['sha256'];payload={k:v for k,v in entry.items() if k!='sha256'}
  if payload['previous_hash']!=previous or hashlib.sha256(canonical(payload)).hexdigest()!=claimed or payload['sequence']!=len(entries)+1:raise ValueError('journal history changed')
  entries.append(entry);previous=claimed
 return entries

def append_entry(path,category,experiments,content,evidence):
 if category not in CATEGORIES or not isinstance(content,str) or not content.strip() or not isinstance(experiments,list) or not experiments:raise ValueError('category, experiment IDs and nonempty content required')
 retained=[(Path(p).resolve(),Path(p).read_bytes()) for p in evidence]
 references=[{'path':str(p),'sha256':hashlib.sha256(data).hexdigest()} for p,data in retained]
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 with path.with_suffix('.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX);entries=read_entries(path)
  # Preserve exactly the bytes hashed for this entry, even if a caller later
  # replaces a mutable receipt. All snapshots precede durable journal append.
  snapshots=path.parent/'journal-evidence'
  if snapshots.is_symlink():raise ValueError('regular immutable evidence directory required')
  snapshots.mkdir(exist_ok=True)
  for (_,data),reference in zip(retained,references):
   snapshot=snapshots/reference['sha256']
   if snapshot.exists():
    if snapshot.is_symlink() or snapshot.read_bytes()!=data:raise ValueError('immutable journal evidence changed')
   else:
    with snapshot.open('xb') as output:output.write(data);output.flush();os.fsync(output.fileno())
  fsync_directory(snapshots);fsync_directory(path.parent)
  payload={'sequence':len(entries)+1,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'category':category,'experiments':experiments,'content':content,'evidence':references,'previous_hash':entries[-1]['sha256'] if entries else None};entry={**payload,'sha256':hashlib.sha256(canonical(payload)).hexdigest()}
  with path.open('ab') as output:output.write(canonical(entry)+b'\n');output.flush();os.fsync(output.fileno())
  fsync_directory(path.parent)
 return entry
