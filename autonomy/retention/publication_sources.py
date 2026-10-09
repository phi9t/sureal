"""Source snapshot declarations for retained publication entrypoints."""

from pathlib import Path

from evidence.source_snapshot import (
    is_regular_file,
    snapshot_target_and_materialize,
    verify_or_materialize_receipt_sources,
)


CHECKPOINT_TARGET = "//autonomy/retention:publish_sustained_checkpoint"
NATIVE_CACHE_TARGET = "//autonomy/retention:publish_native_cache"
PILOT_TARGET = "//autonomy/retention:publish_sustained_pilot"

CHECKPOINT_REQUIRED = (
    "blob_store/core.py",
    "evidence/source_snapshot.py",
    "insula/launch_plan.py",
    "insula/runtime_identity.py",
    "insula/runtime_roots.py",
    "resources/backend.py",
    "resources/scientific_budget.py",
    "resources/scientific_payload.py",
    "retention/checkpoint_retention_policy.py",
    "retention/publication.py",
    "retention/publication_sources.py",
    "retention/publish_sustained_checkpoint.py",
    "retention/publisher_runtime.py",
    "retention/sustained_checkpoint_inventory.py",
    "retention/sustained_controller_lock.py",
)

NATIVE_CACHE_REQUIRED = (
    "blob_store/core.py",
    "evidence/source_snapshot.py",
    "resources/scientific_budget.py",
    "resources/scientific_payload.py",
    "retention/cache_inventory.py",
    "retention/publication.py",
    "retention/publication_sources.py",
    "retention/publish_native_cache.py",
    "retention/publisher_runtime.py",
    "retention/sustained_controller_lock.py",
)

PILOT_REQUIRED = (
    "blob_store/core.py",
    "evidence/source_snapshot.py",
    "resources/scientific_budget.py",
    "resources/scientific_payload.py",
    "retention/publication.py",
    "retention/publication_sources.py",
    "retention/publish_sustained_pilot.py",
    "retention/publisher_runtime.py",
    "retention/sustained_controller_lock.py",
    "retention/sustained_pilot_inventory.py",
)

HISTORICAL_CHECKPOINT_REQUIRED = (
    "retention/publish_sustained_checkpoint.py",
    "retention/sustained_checkpoint_inventory.py",
    "retention/checkpoint_retention_audit.py",
    "retention/checkpoint_retention_sources.py",
    "retention/sustained_controller_lock.py",
    "retention/checkpoint_retention_policy.py",
    "resources/scientific_budget.py",
    "resources/scientific_payload.py",
    "resources/resource_archive.py",
    "resources/resource_archive_cli.py",
    "resources/resource_rehydrate.py",
    "resources/resource_release_plan.py",
    "evidence/source_snapshot.py",
    "insula/entry.py",
    "insula/runtime_identity.py",
)

HISTORICAL_NATIVE_CACHE_REQUIRED = (
    "retention/publish_native_cache.py",
    "retention/cache_inventory.py",
    "retention/cache_retention_audit.py",
    "retention/retention_sources.py",
    "resources/scientific_budget.py",
    "resources/scientific_payload.py",
    "resources/resource_archive.py",
    "resources/resource_archive_cli.py",
    "resources/resource_rehydrate.py",
    "resources/resource_release_plan.py",
    "evidence/source_snapshot.py",
    "insula/entry.py",
    "insula/runtime_identity.py",
)

HISTORICAL_PILOT_REQUIRED = (
    "retention/publish_sustained_pilot.py",
    "retention/sustained_pilot_inventory.py",
    "retention/pilot_retention_audit.py",
    "retention/pilot_retention_sources.py",
    "resources/scientific_budget.py",
    "resources/scientific_payload.py",
    "resources/resource_archive.py",
    "resources/resource_archive_cli.py",
    "resources/resource_rehydrate.py",
    "resources/resource_release_plan.py",
    "evidence/source_snapshot.py",
    "insula/entry.py",
    "insula/runtime_identity.py",
)


def freeze_checkpoint_sources(repository, destination, *, store=None, repo_root=None, bazel=None, runner=None):
    return _freeze_sources(repository, destination, CHECKPOINT_REQUIRED, CHECKPOINT_TARGET, store, repo_root, bazel, runner)


def freeze_native_cache_sources(repository, destination, *, store=None, repo_root=None, bazel=None, runner=None):
    return _freeze_sources(
        repository,
        destination,
        NATIVE_CACHE_REQUIRED,
        NATIVE_CACHE_TARGET,
        store,
        repo_root,
        bazel,
        runner,
    )


def freeze_pilot_sources(repository, destination, *, store=None, repo_root=None, bazel=None, runner=None):
    return _freeze_sources(repository, destination, PILOT_REQUIRED, PILOT_TARGET, store, repo_root, bazel, runner)


def validate_checkpoint_sources(repository, receipt):
    return _validate_sources(repository, receipt, CHECKPOINT_REQUIRED, HISTORICAL_CHECKPOINT_REQUIRED)


def validate_native_cache_sources(repository, receipt):
    return _validate_sources(repository, receipt, NATIVE_CACHE_REQUIRED, HISTORICAL_NATIVE_CACHE_REQUIRED)


def validate_pilot_sources(repository, receipt):
    return _validate_sources(repository, receipt, PILOT_REQUIRED, HISTORICAL_PILOT_REQUIRED)


def _freeze_sources(repository, destination, required, target, store, repo_root, bazel, runner):
    repository = Path(repository)
    destination = Path(destination)
    if not all(is_regular_file(repository / name) for name in required):
        raise ValueError("complete regular host source closure required")
    if repository.name != "autonomy":
        raise ValueError("Bazel target source snapshot context required")
    kwargs = {"repo_root": Path(repo_root) if repo_root is not None else repository.parent}
    if store is not None:
        kwargs["store"] = store
    if bazel is not None:
        kwargs["bazel"] = bazel
    if runner is not None:
        kwargs["runner"] = runner
    receipt = snapshot_target_and_materialize(target, destination, **kwargs)
    _validate_sources(repository, receipt, required, ())
    return receipt


def _validate_sources(repository, receipt, required, historical_required):
    if not isinstance(receipt, dict):
        raise ValueError("host source receipt object required")
    if receipt.get("schema_version") == 2:
        required_pins = {"autonomy/" + name for name in required}
    else:
        required_pins = set(historical_required)
    if not required_pins <= set(receipt.get("source_pins", {})):
        raise ValueError("complete host execution source bindings required")
    return verify_or_materialize_receipt_sources(
        receipt,
        receipt["source_snapshot_root"],
        env_var="SUREAL_SOURCE_SNAPSHOT_STORE",
    )
