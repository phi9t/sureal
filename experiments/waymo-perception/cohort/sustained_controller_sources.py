"""Freeze the host closure for sustained controller execution and retention."""
import hashlib,shutil
from pathlib import Path
from cohort.checkpoint_retention_sources import REQUIRED as RETENTION_REQUIRED
REQUIRED=tuple(sorted(set(RETENTION_REQUIRED)|{
 'cohort/run_sustained.py','cohort/sustained_controller_backend.py',
 'cohort/sustained_controller_sources.py','cohort/sustained_workflow.py',
 'cohort/sustained_control.py','cohort/sustained_admission.py',
 'cohort/sustained_contract.py','cohort/sustained_scoring_budget.py',
 'cohort/sustained_stage_inputs.py','cohort/sustained_sources.py',
 'architecture/experiment_runner.py',
}))
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
