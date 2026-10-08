# Ticket 27 sandbox source-root fix

## Root cause

The live `train-0` failure was caused by `training_execution.sustained_sources.validate_sources`
using `receipt["source_snapshot_root"]` as the verification root. That field is the host
materialization path from the admitted receipt. Inside the Insula worker, the executed code is
mounted at `/experiment`, and the host receipt path is not a valid in-sandbox execution root.

Commit `08c4ac0` changed sustained execution validation from verifying the caller-provided root
with `verify_materialized_sources` to `verify_or_materialize_receipt_sources` against the receipt
root. When the host root was absent in the sandbox, validation tried to materialize the receipt and
failed while creating a temporary directory next to the host-only path.

## Fix

`training_execution.sustained_sources.validate_sources` now:

- checks runtime lock equality before source verification;
- resolves the source snapshot store from the receipt, with `SUREAL_SOURCE_SNAPSHOT_STORE` override;
- verifies the snapshot digest and pins from that store;
- verifies the caller-provided execution root, not `source_snapshot_root`;
- raises if the execution root is absent or if any mounted source file differs;
- never materializes receipt sources in the default worker path.

The host controller guard keeps its existing case-local recovery behavior through an explicit
`materialize_missing=True` opt-in. That opt-in materializes only the expected host snapshot root for
the controller-owned package, then re-runs mounted-root verification. Sandbox worker entrypoints do
not use the opt-in.

`evidence.source_snapshot.verify_materialized_sources` now accepts an optional top-level package
name. Schema-2 sustained receipts pin files as `autonomy/...`, while the sandbox mounts the
`autonomy` package itself at `/experiment`. The package option keeps receipt/archive verification
against the original pins and strips only the package prefix for the materialized-file comparison.

## Call-site audit

Inside sandbox, source receipt validation:

- `training_execution/train_sustained.py`: runs from `WORKER_ENTRIES` in both
  `sustained_controller_backend.py` and `admit_sustained.py`; calls
  `validate_sources("/experiment", ...)`. Fixed by the common validator.
- `training_execution/audit_sustained_transition.py`: controller audit worker, executed from
  `/tmp/verifier` while validating `/experiment`; fixed by the common validator.
- `training_execution/replay_sustained.py`: pilot admission worker in `admit_sustained.py`;
  calls `validate_sources("/experiment", ...)`. Fixed by the common validator.

Inside sandbox, no source receipt validation call:

- `training_execution/audit_sustained_loss.py`;
- `evaluation/prepare_sustained_v3.py`;
- `evaluation/audit_proposals_sustained_v3.py`;
- `evaluation/metrics_sustained_v3.py`;
- `evaluation/audit_metrics_sustained_v3.py`;
- `resources/execute_worker.py`;
- `resources/resource_archive_cli.py`.

Outside sandbox or intentionally host-side materialization:

- `training_execution/admit_sustained.py` and `training_execution/sustained_controller_backend.py`
  host guards call the same sustained validator on the materialized package root. The sustained
  controller guard explicitly opts into missing-package rehydration for its case-local source root.
- `training_execution/sustained_controller_sources.validate_host_sources` validates the host
  controller closure and may rehydrate the frozen host snapshot.
- `resources/sources.validate_sources` validates the resource-layer frozen source identity and may
  rehydrate the admitted resource snapshot before wrapping workers.
- `resources/stage.py` and `resources/backend.py` call `resources.sources.validate_sources` from the
  host launcher path before executing wrapped workers.
- `resources/checkpoint.py` uses `verify_or_materialize_receipt_sources` while building retention
  inventory for archived source snapshots; materialization is intentional there.
- `retention/retention_sources.py`, `retention/checkpoint_retention_sources.py`,
  `retention/pilot_retention_sources.py`, `retention/publish_scientific_directory.py`, and
  `retention/publish_symlink_audit.py` validate host publisher closures; materialization is
  intentional for host-side retention publication and audit.
- `studies/architecture/experiment_runner.py` checks archived architecture run snapshots on the host.

## Regression coverage

`autonomy/training_execution/sustained_sources_test.py` covers the live failure shape with a
schema-2 receipt whose pins are `autonomy/...` while the sandbox root is the mounted `autonomy`
package:

- receipt `source_snapshot_root` points at a non-executed host path, while the mounted root contains
  the exact materialized sources;
- verification succeeds through `SUREAL_SOURCE_SNAPSHOT_STORE` without creating the host path;
- tampering under the mounted root raises;
- a missing mounted root raises and does not materialize next to the receipt host path.

Focused red/green evidence:

- before the fix, `//autonomy/training_execution:sustained_sources_test` failed because the host
  root was materialized and mounted-root tampering/missing-root cases were accepted;
- after the fix, `//autonomy/training_execution:sustained_sources_test` passed.
- focused post-fix coverage passed for `//autonomy/training_execution:sustained_sources_test`,
  `//autonomy/training_execution:sustained_controller_backend_test`, and
  `//autonomy/evidence:source_snapshot_test`.
- full default suite passed with
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`
  on the 154-test baseline.
