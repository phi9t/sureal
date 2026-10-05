"""Freeze the host closure that admits, archives and releases sustained pilot bytes."""
import hashlib,shutil
from pathlib import Path
REQUIRED=(
 'cohort/publish_sustained_pilot.py','cohort/sustained_pilot_inventory.py',
 'cohort/pilot_retention_audit.py','cohort/pilot_retention_sources.py',
 'tier1/admission.py','tier1/storage.py','advanced/archive.py',
 'advanced/retention.py','pipeline/insula_entry.py','pipeline/runtime_identity.py',
)
def sha(path):
 with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def regular(path):
 return path.is_file() and not any(p.is_symlink() for p in [path,*path.parents])
def freeze_host_sources(repository,destination):
 repository=Path(repository);destination=Path(destination)
 if not all(regular(repository/name) for name in REQUIRED):raise ValueError('complete regular host source closure required')
 destination.mkdir(exist_ok=False);pins={}
 for name in REQUIRED:
  original=repository/name;snapshot=destination/name;snapshot.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,snapshot)
  digest=sha(original)
  if sha(snapshot)!=digest:raise ValueError('host source changed while frozen')
  pins[name]={'original':str(original),'snapshot':str(snapshot),'sha256':digest}
 validate_host_sources(repository,pins)
 return pins

def validate_host_sources(repository,pins):
 repository=Path(repository)
 if set(pins)!=set(REQUIRED):raise ValueError('complete host execution source bindings required')
 for name,pin in pins.items():
  original=repository/name;snapshot=Path(pin['snapshot'])
  if str(original)!=pin['original'] or not regular(original) or not regular(snapshot) or sha(original)!=pin['sha256'] or sha(snapshot)!=pin['sha256']:raise ValueError('host source/snapshot differs')
