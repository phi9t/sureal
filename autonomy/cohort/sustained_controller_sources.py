"""Freeze the host closure for sustained controller execution and retention."""
from pathlib import Path
from evidence.source_snapshot import LocalSnapshotStore,copy_source_snapshot,verify_materialized_sources
from cohort.checkpoint_retention_sources import REQUIRED as RETENTION_REQUIRED
REQUIRED=tuple(sorted(set(RETENTION_REQUIRED)|{
 'cohort/run_sustained.py','cohort/sustained_controller_backend.py',
 'cohort/sustained_controller_sources.py','cohort/sustained_workflow.py',
 'cohort/sustained_control.py','cohort/sustained_admission.py',
 'cohort/sustained_contract.py','cohort/sustained_scoring_budget.py',
 'cohort/sustained_stage_inputs.py','cohort/sustained_sources.py',
 'architecture/experiment_runner.py',
}))
SNAPSHOT_TARGET='//autonomy:sustained-controller-host'
def sha(path):
 from evidence.source_snapshot import file_sha256
 return file_sha256(path)
def regular(path):
 return path.is_file() and not any(p.is_symlink() for p in [path,*path.parents])
def freeze_host_sources(repository,destination):
 repository=Path(repository);destination=Path(destination)
 if not all(regular(repository/name) for name in REQUIRED):raise ValueError('complete regular host source closure required')
 receipt=copy_source_snapshot(repository,REQUIRED,destination,LocalSnapshotStore(destination.parent/'source-snapshots'),target=SNAPSHOT_TARGET)
 validate_host_sources(repository,receipt)
 return receipt

def validate_host_sources(repository,pins):
 if set(pins.get('source_pins',{}))!=set(REQUIRED):raise ValueError('complete host execution source bindings required')
 return verify_materialized_sources(pins['source_snapshot_root'],pins)
