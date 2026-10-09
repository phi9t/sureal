# 05: Sustained-checkpoint publication spec

**What to build:** The sustained controller publishes and releases each checkpoint through the publication module, keeping its subprocess entry point and its lock handoff, with release only after a passing audit.

**Blocked by:** 04

**Status:** done

- [x] The sustained-checkpoint publication is a spec with checkpoints under the `checkpoints/` area and release enabled
- [x] Its subprocess entry point and `--lock-fd` lock handoff behave as before for the controller
- [x] Local files are released only after store, readback and a passing audit; a failing audit releases nothing (tested)
- [x] The controller backend's readers of publication receipts read the new shape
- [x] Default CPU suite, `--config=cuda` suite and `//parallax/...` pass with counts recorded

## Comments

Done 2026-10-09:

- Added `sustained_checkpoint_spec` to `retention.publication`. It publishes archive-mode checkpoint blobs under `checkpoints/perception-sustained-checkpoints/<run-id>/checkpoint/...`, uses copy staging, sets `release=True`, audits the stored manifest and chunks, and releases local payload files only after the audit passes.
- Added publication release-plan support for blob receipts so the native controller can bind `release-completed.json` to `archive_blob_key` entries instead of old HDFS archive URIs.
- Reworked `retention.publish_sustained_checkpoint` to keep the same `python -m retention.publish_sustained_checkpoint` subprocess entry point and `--lock-fd` handoff while delegating store/readback/audit/release to the publication module. The local test path uses a local blob store; the default live path remains the Waystone descriptor.
- Updated native release validation and resume recovery to read the new blob publication receipt shape through `retention.publication.audit`, while keeping old HDFS publication receipts readable on the existing branch.
- Updated the sustained-checkpoint publisher source closure to include `retention/publication.py` and `blob_store/core.py`.
- No live sustained run was executed. No live HDFS writes were performed.
- Pins check: `python3 autonomy/tools/pins.py check --base work/semantic-layout/integration` was not applicable in this worktree because `autonomy/tools/pins.py` is absent.
- Red checks before implementation: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/retention:publication_test //autonomy/retention:publish_sustained_checkpoint_test //autonomy/training_execution:sustained_controller_backend_test` failed for missing `sustained_checkpoint_spec`, unsupported local subprocess args, and the old native publication reader shape.
- Focused green checks:
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/retention:publication_test //autonomy/retention:publish_sustained_checkpoint_test //autonomy/training_execution:sustained_controller_backend_test` passed: 3 out of 3 tests.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/retention:all_tests //autonomy/training_execution:run_sustained_test //autonomy/resources:checkpoint_blob_publication_test` passed: 15 out of 15 tests.
- Required gates:
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed: 182 out of 182 tests.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed: 17 out of 17 tests.
  - GPU 1 check before CUDA showed GPU 1 UUID `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619`, 4 MiB used, 0% utilization, and no compute process on GPU 1.
  - `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed: 29 out of 29 tests.
