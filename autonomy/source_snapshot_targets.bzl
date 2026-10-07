SUSTAINED_RUN_SOURCE_GLOBS = [
    "cohort/**/*.py",
    "pipeline/**/*.py",
    "tier1/**/*.py",
]

SUSTAINED_CHECKPOINT_RETENTION_HOST_SOURCES = [
    "advanced/archive.py",
    "advanced/retention.py",
    "cohort/checkpoint_retention_audit.py",
    "cohort/checkpoint_retention_policy.py",
    "cohort/checkpoint_retention_sources.py",
    "cohort/publish_sustained_checkpoint.py",
    "cohort/sustained_checkpoint_inventory.py",
    "cohort/sustained_controller_lock.py",
    "//autonomy/insula:host_entry_runtime_py",
    "tier1/admission.py",
    "tier1/storage.py",
]

SUSTAINED_PILOT_RETENTION_HOST_SOURCES = [
    "advanced/archive.py",
    "advanced/retention.py",
    "cohort/pilot_retention_audit.py",
    "cohort/pilot_retention_sources.py",
    "cohort/publish_sustained_pilot.py",
    "cohort/sustained_pilot_inventory.py",
    "//autonomy/insula:host_entry_runtime_py",
    "tier1/admission.py",
    "tier1/storage.py",
]

NATIVE_CACHE_RETENTION_HOST_SOURCES = [
    "advanced/archive.py",
    "advanced/retention.py",
    "cohort/cache_inventory.py",
    "cohort/cache_retention_audit.py",
    "cohort/publish_native_cache.py",
    "cohort/retention_sources.py",
    "//autonomy/insula:host_entry_runtime_py",
    "tier1/admission.py",
    "tier1/storage.py",
]

SUSTAINED_CONTROLLER_HOST_SOURCES = [
    "advanced/archive.py",
    "advanced/retention.py",
    "architecture/experiment_runner.py",
    "cohort/checkpoint_retention_audit.py",
    "cohort/checkpoint_retention_policy.py",
    "cohort/checkpoint_retention_sources.py",
    "cohort/publish_sustained_checkpoint.py",
    "cohort/run_sustained.py",
    "cohort/sustained_admission.py",
    "cohort/sustained_checkpoint_inventory.py",
    "cohort/sustained_contract.py",
    "cohort/sustained_control.py",
    "cohort/sustained_controller_backend.py",
    "cohort/sustained_controller_lock.py",
    "cohort/sustained_controller_sources.py",
    "cohort/sustained_scoring_budget.py",
    "cohort/sustained_sources.py",
    "cohort/sustained_stage_inputs.py",
    "cohort/sustained_workflow.py",
    "//autonomy/insula:host_entry_runtime_py",
    "tier1/admission.py",
    "tier1/storage.py",
]
