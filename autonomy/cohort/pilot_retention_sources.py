"""Freeze the host closure that admits, archives and releases sustained pilot bytes."""
from pathlib import Path
from evidence.source_snapshot import LocalSnapshotStore,copy_source_snapshot,verify_materialized_sources
REQUIRED=(
 'cohort/publish_sustained_pilot.py','cohort/sustained_pilot_inventory.py',
 'cohort/pilot_retention_audit.py','cohort/pilot_retention_sources.py',
 'tier1/admission.py','tier1/storage.py','advanced/archive.py',
 'advanced/retention.py','pipeline/insula_entry.py','pipeline/runtime_identity.py',
)
def sha(path):
 from evidence.source_snapshot import file_sha256
 return file_sha256(path)
def regular(path):
 return path.is_file() and not any(p.is_symlink() for p in [path,*path.parents])
def freeze_host_sources(repository,destination):
 repository=Path(repository);destination=Path(destination)
 if not all(regular(repository/name) for name in REQUIRED):raise ValueError('complete regular host source closure required')
 receipt=copy_source_snapshot(repository,REQUIRED,destination,LocalSnapshotStore(destination.parent/'source-snapshots'),target='//autonomy:sustained-pilot-retention-host')
 validate_host_sources(repository,receipt)
 return receipt

def validate_host_sources(repository,pins):
 if set(pins.get('source_pins',{}))!=set(REQUIRED):raise ValueError('complete host execution source bindings required')
 return verify_materialized_sources(pins['source_snapshot_root'],pins)
