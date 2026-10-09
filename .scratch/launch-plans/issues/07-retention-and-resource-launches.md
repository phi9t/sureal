# 07: Retention publishers and resource bundles on launch plans

**What to build:** The retention publishers and the resource-bundle runner launch through launch plans. The resource bundle's swap of the root mount for read-only per-entry mounts is a plan option checked by the same lock and overlap rules.

**Blocked by:** 01, blob-store 11 (the blob-store migration rewrites these files)

**Status:** done

- [x] The root-mount swap is a launch-plan option, with offline tests
- [x] `resources/retention.py` and whatever retention publishing remains after blob-store 11 (the publication module and `retention/publish_scientific_directory.py`) build launch plans. No command-line splicing or hand-parsed lock remains
- [x] Tests assert on plans, not command-line slices
- [x] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded

## Comments

Done:

- Added `build_plan(..., split_runtime_root=True)` in `autonomy/insula/launch_plan.py`. The option replaces the single read-only `/` rootfs mount with checked read-only per-entry mounts, excluding native mount targets such as `/experiment`, `/source`, `/outputs`, `/proc`, `/dev`, and `/tmp`. The strict lock check stays in `load_runtime_lock` / `load_default_runtime_lock`; duplicate-host and writable-overlap checks stay in `_validate_mounts`.
- Moved the active resource-bundle launch path onto launch-plan data in `autonomy/resources/command.py` and `autonomy/resources/stage.py`. Legacy command wrapping remains for old proof/receipt compatibility, but plan-backed stages now record both the original and wrapped launch plan and render only at `run_scoped`.
- Tightened plan-backed resource proof validation so the recorded plan must still contain the resource wrapper mounts by role (`resource-layer`, `resource-experiment-resources`, `resource-experiment-evidence`, `resource-output`) as well as the rendered command mounts.
- The active retention publisher check covered by this ticket is `autonomy/retention/publish_sustained_checkpoint.py`, which now verifies the default resource root through `load_default_runtime_lock`. On this base, `autonomy/retention/publication.py`, `retention/publish_scientific_directory.py`, `retention/publish_native_cache.py`, and `retention/publish_sustained_pilot.py` are blob-store publication workflows and do not launch Insula directly. `resources/retention.py` no longer exists as active code after blob-store 11.

Coordinator review fixes:

- Plan-backed resource proofs now recompute the exact rendered wrapper command from the original rendered plan command, and also check that the original rendered command matches the recorded original plan's mount/environment/working-directory/command data. Extra mounts, reordered resource mounts, and changed mount modes are refused.
- `autonomy/insula/launch_plan.py` now exposes `with_mounts(...)` as the public validated plan-extension helper, and `autonomy/resources/command.py` uses it instead of importing the private `_assemble_plan`.
- Split runtime-root plans now preserve top-level symlink entries with `--symlink` mounts instead of binding the host symlink target as a directory. The offline fixture covers merged-usr style `/bin -> usr/bin` and `/lib -> usr/lib`.
- Masked split-root entries are the native role targets or runtime-populated scaffolding that must not be copied from the rootfs entry set: `experiment` is the code mount, `source` is the optional source mount, `outputs` is the writable output mount, `proc` and `dev` are provided by bwrap/device handling, `tmp` is the private tmpfs, and `driver` is owned by GPU driver mounting.

Verification:

- Review red checks were observed on `e2b799f`: plan-backed `validate_proof` accepted an extra executed mount and reordered resource mount; split-root top-level symlinks rendered as bind mounts; `with_mounts` was missing.
- `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/lp07-retention-resource-launches-20261009T102501Z/tmp PYTHONPATH=autonomy python3 -m unittest autonomy.insula.launch_plan_test autonomy.resources.command_test autonomy.resources.stage_test autonomy.retention.publish_sustained_checkpoint_test autonomy.retention.publication_sources_test` - 35 tests passed.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/insula:launch_plan_test //autonomy/resources:command_test //autonomy/resources:stage_test //autonomy/retention:publish_sustained_checkpoint_test //autonomy/retention:publication_sources_test //autonomy:source_snapshot_targets_test` - 6 tests passed.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` - 184 tests passed. This is the current branch count; related ticket comments on earlier workers recorded older 159 and 185 counts before intervening branch changes.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` - 17 tests passed.
- CUDA precheck initially found GPU 1 occupied, then the bounded poll found GPU 1 free on check 5: UUID `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619`, memory 4 MiB, no compute-app entry.
- `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` - 29 tests passed.
