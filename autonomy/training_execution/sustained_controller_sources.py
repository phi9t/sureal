"""Freeze the host closure for sustained controller execution and retention."""
from pathlib import Path
from evidence.source_snapshot import file_sha256 as sha,is_regular_file,snapshot_target_and_materialize,verify_or_materialize_receipt_sources
from retention.checkpoint_retention_sources import HISTORICAL_REQUIRED as RETENTION_HISTORICAL_REQUIRED
from retention.checkpoint_retention_sources import REQUIRED as RETENTION_REQUIRED
REQUIRED=tuple(sorted(set(RETENTION_REQUIRED)|{
 'training_execution/run_sustained.py','training_execution/sustained_controller_backend.py',
 'training_execution/sustained_controller_sources.py','training_execution/sustained_workflow.py',
 'training_execution/sustained_control.py','training_execution/sustained_admission.py',
 'detection/sustained_contract.py','resources/sustained_scoring_budget.py',
 'retention/publication.py','blob_store/core.py',
 'training_execution/sustained_stage_inputs.py','training_execution/sustained_sources.py',
 'resources/backend.py','resources/checkpoint.py','resources/command.py',
 'resources/execute_worker.py','resources/kernel_scope.py','resources/process_lifecycle.py',
 'resources/scoped_stage.py','resources/sources.py','resources/stage.py',
 'resources/stage_accounting.py',
 'studies/architecture/experiment_runner.py',
}))
HISTORICAL_REQUIRED=tuple(sorted(set(RETENTION_HISTORICAL_REQUIRED)|{
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
SNAPSHOT_TARGET='//autonomy/training_execution:run_sustained'
def freeze_host_sources(repository,destination,*,store=None,repo_root=None,bazel=None,runner=None):
 repository=Path(repository);destination=Path(destination)
 if not all(is_regular_file(repository/name) for name in REQUIRED):raise ValueError('complete regular host source closure required')
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
