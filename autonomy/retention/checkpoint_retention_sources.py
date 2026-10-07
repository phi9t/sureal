"""Freeze the host closure that admits, archives and releases sustained checkpoint bytes."""
from pathlib import Path
from evidence.source_snapshot import LocalSnapshotStore,copy_source_snapshot,require_regular_file,verify_materialized_sources
REQUIRED=(
 'retention/publish_sustained_checkpoint.py','retention/sustained_checkpoint_inventory.py',
 'retention/checkpoint_retention_audit.py','retention/checkpoint_retention_sources.py',
 'retention/sustained_controller_lock.py','retention/checkpoint_retention_policy.py',
 'resources/scientific_budget.py','resources/scientific_payload.py',
 'resources/resource_archive.py','resources/resource_archive_cli.py',
 'resources/resource_rehydrate.py','resources/resource_release_plan.py',
 'evidence/source_snapshot.py','insula/entry.py','insula/runtime_identity.py',
)
SNAPSHOT_TARGET='//autonomy:sustained-checkpoint-retention-host'
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
