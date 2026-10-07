"""Freeze the host closure for sustained controller execution and retention."""
from pathlib import Path
from evidence.source_snapshot import LocalSnapshotStore,copy_source_snapshot,require_regular_file,verify_materialized_sources
from retention.checkpoint_retention_sources import REQUIRED as RETENTION_REQUIRED
REQUIRED=tuple(sorted(set(RETENTION_REQUIRED)|{
 'training_execution/run_sustained.py','training_execution/sustained_controller_backend.py',
 'training_execution/sustained_controller_sources.py','training_execution/sustained_workflow.py',
 'training_execution/sustained_control.py','training_execution/sustained_admission.py',
 'detection/sustained_contract.py','resources/sustained_scoring_budget.py',
 'training_execution/sustained_stage_inputs.py','training_execution/sustained_sources.py',
 'resources/backend.py','resources/checkpoint.py','resources/command.py',
 'resources/execute_worker.py','resources/kernel_scope.py','resources/process_lifecycle.py',
 'resources/scoped_stage.py','resources/sources.py','resources/stage.py',
 'resources/stage_accounting.py',
 'studies/architecture/experiment_runner.py',
}))
SNAPSHOT_TARGET='//autonomy:sustained-controller-host'
def sha(path):
 from evidence.source_snapshot import file_sha256
 return file_sha256(path)
def regular(path):
 try:require_regular_file(path)
 except ValueError:return False
 return True
def freeze_host_sources(repository,destination):
 repository=Path(repository);destination=Path(destination)
 if not all(regular(repository/name) for name in REQUIRED):raise ValueError('complete regular host source closure required')
 receipt=copy_source_snapshot(repository,REQUIRED,destination,LocalSnapshotStore(destination.parent/'source-snapshots'),target=SNAPSHOT_TARGET)
 validate_host_sources(repository,receipt)
 return receipt

def validate_host_sources(repository,pins):
 if set(pins.get('source_pins',{}))!=set(REQUIRED):raise ValueError('complete host execution source bindings required')
 return verify_materialized_sources(pins['source_snapshot_root'],pins)
