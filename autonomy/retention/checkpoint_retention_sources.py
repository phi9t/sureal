"""Freeze the host closure that admits, archives and releases sustained checkpoint bytes."""
from pathlib import Path
from evidence.source_snapshot import require_regular_file,snapshot_target_and_materialize,verify_or_materialize_receipt_sources
REQUIRED=(
 'retention/publish_sustained_checkpoint.py','retention/sustained_checkpoint_inventory.py',
 'retention/checkpoint_retention_audit.py','retention/checkpoint_retention_sources.py',
 'retention/publisher_runtime.py','retention/sustained_controller_lock.py','retention/checkpoint_retention_policy.py',
 'resources/scientific_budget.py','resources/scientific_payload.py',
 'resources/resource_archive.py','resources/resource_archive_cli.py',
 'resources/resource_rehydrate.py','resources/resource_release_plan.py',
 'evidence/source_snapshot.py','insula/entry.py','insula/runtime_identity.py',
)
HISTORICAL_REQUIRED=(
 'retention/publish_sustained_checkpoint.py','retention/sustained_checkpoint_inventory.py',
 'retention/checkpoint_retention_audit.py','retention/checkpoint_retention_sources.py',
 'retention/sustained_controller_lock.py','retention/checkpoint_retention_policy.py',
 'resources/scientific_budget.py','resources/scientific_payload.py',
 'resources/resource_archive.py','resources/resource_archive_cli.py',
 'resources/resource_rehydrate.py','resources/resource_release_plan.py',
 'evidence/source_snapshot.py','insula/entry.py','insula/runtime_identity.py',
)
SNAPSHOT_TARGET='//autonomy/retention:publish_sustained_checkpoint'
def sha(path):
 from evidence.source_snapshot import file_sha256
 return file_sha256(path)
def regular(path):
 try:require_regular_file(path)
 except ValueError:return False
 return True
def freeze_host_sources(repository,destination,*,store=None,repo_root=None,bazel=None,runner=None):
 repository=Path(repository);destination=Path(destination)
 if not all(regular(repository/name) for name in REQUIRED):raise ValueError('complete regular host source closure required')
 if repository.name!='autonomy':raise ValueError('Bazel target source snapshot context required')
 kwargs={'repo_root':Path(repo_root) if repo_root is not None else repository.parent}
 if store is not None:kwargs['store']=store
 if bazel is not None:kwargs['bazel']=bazel
 if runner is not None:kwargs['runner']=runner
 receipt=snapshot_target_and_materialize(SNAPSHOT_TARGET,destination,**kwargs)
 validate_host_sources(repository,receipt)
 return receipt

def validate_host_sources(repository,pins):
 required={'autonomy/'+name for name in REQUIRED} if pins.get('schema_version')==2 else set(HISTORICAL_REQUIRED)
 if not required<=set(pins.get('source_pins',{})):raise ValueError('complete host execution source bindings required')
 return verify_or_materialize_receipt_sources(pins,pins['source_snapshot_root'],env_var='SUREAL_SOURCE_SNAPSHOT_STORE')
