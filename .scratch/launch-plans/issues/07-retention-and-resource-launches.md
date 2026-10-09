# 07: Retention publishers and resource bundles on launch plans

**What to build:** The retention publishers and the resource-bundle runner launch through launch plans. The resource bundle's swap of the root mount for read-only per-entry mounts is a plan option checked by the same lock and overlap rules.

**Blocked by:** 01, blob-store 11 (the blob-store migration rewrites these files)

**Status:** done

- [x] The root-mount swap is a launch-plan option, with offline tests
- [x] `resources/retention.py` and whatever retention publishing remains after blob-store 11 (the publication module and `retention/publish_scientific_directory.py`) build launch plans. No command-line splicing or hand-parsed lock remains
- [x] Tests assert on plans, not command-line slices
- [ ] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded

## Comments

Done:

- Added `build_plan(..., split_runtime_root=True)` in `autonomy/insula/launch_plan.py`. The option replaces the single read-only `/` rootfs mount with checked read-only per-entry mounts, excluding native mount targets such as `/experiment`, `/source`, `/outputs`, `/proc`, `/dev`, and `/tmp`. The strict lock check stays in `load_runtime_lock` / `load_default_runtime_lock`; duplicate-host and writable-overlap checks stay in `_validate_mounts`.
- Moved the active resource-bundle launch path onto launch-plan data in `autonomy/resources/command.py` and `autonomy/resources/stage.py`. Legacy command wrapping remains for old proof/receipt compatibility, but plan-backed stages now record both the original and wrapped launch plan and render only at `run_scoped`.
- Tightened plan-backed resource proof validation so the recorded plan must still contain the resource wrapper mounts by role (`resource-layer`, `resource-experiment-resources`, `resource-experiment-evidence`, `resource-output`) as well as the rendered command mounts.
- The active retention publisher check covered by this ticket is `autonomy/retention/publish_sustained_checkpoint.py`, which now verifies the default resource root through `load_default_runtime_lock`. On this base, `autonomy/retention/publication.py`, `retention/publish_scientific_directory.py`, `retention/publish_native_cache.py`, and `retention/publish_sustained_pilot.py` are blob-store publication workflows and do not launch Insula directly. `resources/retention.py` no longer exists as active code after blob-store 11.

Verification:

- `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/lp07-retention-resource-launches-20261009T102501Z/tmp PYTHONPATH=autonomy python3 -m unittest autonomy.insula.launch_plan_test autonomy.resources.command_test autonomy.resources.stage_test autonomy.retention.publish_sustained_checkpoint_test autonomy.retention.publication_sources_test` - 33 tests passed.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/insula:launch_plan_test //autonomy/resources:command_test //autonomy/resources:stage_test //autonomy/retention:publish_sustained_checkpoint_test //autonomy/retention:publication_sources_test //autonomy:source_snapshot_targets_test` - 6 tests passed.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` - 184 tests passed. This is the current branch count; related ticket comments on earlier workers recorded older 159 and 185 counts before intervening branch changes.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` - 17 tests passed.
- CUDA deferred: GPU 1 occupied. Precheck/poll observed GPU 1 UUID `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619` in `nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader` and memory above the allowed threshold on checks 1, 3, 4, 5, and 6; check 2 had memory below threshold but still had one compute-app entry. No CUDA suite was run.
