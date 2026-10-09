# 11: Delete the command-line form of launch_plan

**What to build:** No active code can build a sandbox command line except the launch-plan module's renderer. `launch_plan`'s command-line form and `live_gate_plan` are gone, and a check keeps it that way.

**Blocked by:** 02, 03, 04, 05, 06, 07, 08, 09, 10

**Status:** done

- [x] `insula.entry.launch_plan` (command-line form) and `sandbox_plan.live_gate_plan` are deleted, and no active import of either remains
- [x] A test fails if any active file outside the module renders `bwrap` arguments or parses a runtime lock itself. Frozen areas are excluded by path
- [x] The documentation that describes launching inside Insula (`autonomy/ARCHITECTURE.md` and `insula` docs) names the launch-plan module as the only way in
- [x] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded

## Comments

### 2026-10-09 worker evidence

Done. Deleted the active command-line launch surface by removing
`insula.entry.launch_plan(...)`, deleting `autonomy/insula/sandbox_plan.py`, and
deleting the obsolete `autonomy/insula/entry_test.py` coverage for those
interfaces. The CLI path in `autonomy/insula/entry.py` now loads the runtime
lock through `insula.launch_plan.load_runtime_lock(...)`, emits structured
`plan_data(...)` for `--emit-plan`, and renders only at `os.execvp(...)`.
`autonomy/insula/bazel_launcher.py` now carries structured `Mount` records and
structured emitted mounts instead of reconstructing `bwrap` mount argv rows.

Added `autonomy/insula/launch_plan_boundary_test.py`. It scans active text files
for legacy `insula.entry.launch_plan` / `sandbox_plan.live_gate_plan` faces,
direct `bwrap` argv construction or mount/namespace flag splicing, and direct
runtime-lock parsing / rootfs verification outside the launch-plan boundary.
Frozen evidence paths are excluded by path, matching the storage-boundary test
pattern; tests are excluded from the active scan. The planted-red proof was
run with `SUREAL_LAUNCH_PLAN_PLANT_VIOLATION=1` and failed on the planted
`bwrap`, mount, namespace and runtime-lock violations. The normal boundary
scanner returned no active violations.

Moved strict checks without weakening them:

- `autonomy/training_execution/sustained_controller_backend.py`: command mount
  and environment checks now read old command receipts through
  `insula.launch_plan.read_receipt_mounts(...)` plus
  `resources.command.inspect_legacy_receipt_command(...)`. The same rootfs,
  worker, code, output, source-snapshot store, input, artifact, driver and
  verifier checks still run. Resource-wrapped legacy receipts are unwrapped only
  after the shared legacy parser accepts the wrapper command shape.
- `autonomy/studies/architecture/experiment_runner.py`: receipt mount checks
  for `/tmp/inputs` and `/tmp/worker.py` now go through
  `read_receipt_mounts(...)` when the row contains a launch plan or literal
  legacy `bwrap` receipt; source-worker legacy rows remain source-path checks.
- `autonomy/insula/verify_m0.py`: the bad-lock fixture is derived from
  `load_runtime_lock(...).data` instead of reading `*.lock.json` directly.

Documentation now names `autonomy/insula/launch_plan.py` as the only active
path for loading/checking runtime locks, building/reading/rendering/running
plans and recording launch-plan receipts. `autonomy/ARCHITECTURE.md` now
describes `--emit-plan` as structured launch-plan data, not an Insula command.
`docs/ticket29/plan.md` no longer points live-gate work at
`insula.entry.launch_plan` or `insula.sandbox_plan.compose_bwrap_plan`.

LP07-owned active survivors are deliberately path-allowlisted in the boundary
test and were not edited here: `autonomy/resources/command.py`,
`autonomy/resources/stage.py` and
`autonomy/retention/publish_sustained_checkpoint.py`. They still contain
command parsing/rootfs verification surfaces owned by the parallel LP07 review
path; the allowlist is narrow and path-based so the coordinator can merge LP07
and drop it later.

Verification:

- Red proof: `SUREAL_LAUNCH_PLAN_PLANT_VIOLATION=1 PYTHONPATH=autonomy python3 -m unittest autonomy.insula.launch_plan_boundary_test.LaunchPlanBoundaryTests.test_active_code_uses_only_launch_plan_module_for_sandbox_and_lock_boundaries` failed on 5 planted violations.
- Focused Python coverage: `PYTHONPATH=autonomy python3 -m unittest autonomy.insula.launch_plan_boundary_test autonomy.insula.bazel_wrapper_test autonomy.training_execution.sustained_stage_inputs_test autonomy.training_execution.sustained_launch_plan_test autonomy.training_execution.sustained_controller_backend_test` passed `30/30`.
- Focused Bazel coverage: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/insula:launch_plan_boundary_test //autonomy/insula:bazel_wrapper_test //autonomy/training_execution:sustained_stage_inputs_test //autonomy/training_execution:sustained_launch_plan_test //autonomy/training_execution:sustained_controller_backend_test` passed `5/5`.
- Failure repair coverage after the full gate exposed stale fixtures: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/insula:launch_plan_boundary_test //autonomy/training_execution:sustained_controller_sources_test //autonomy/studies:architecture__experiment_runner_test //autonomy/training_execution:run_sustained_test` passed `4/4`.
- Default CPU suite: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed `185/185`. The base count stayed `185`: deleting `entry_test.py` and adding `launch_plan_boundary_test.py` net to no default-count change.
- Parallax suite: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed `17/17`.
- GPU 1 precheck before CUDA: GPU 1 UUID
  `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619` was absent from
  `nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader`, and GPU 1
  memory was `4 MiB`.
- CUDA suite on GPU 1 only: `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed `30/30`, including
  `//autonomy/insula:launch_plan_gpu_live_test` and
  `//autonomy/training_execution:sustained_launch_plan_gpu_smoke_test`.

### 2026-10-09 coordinator review follow-up

Merged LP07 from `base/a3fb2cc` as separate commit
`270fa03 Merge branch 'base/a3fb2cc' into
worker/lp11-delete-command-line-launches`, then removed the temporary
`LP07_OWNED_EXACT` boundary allowlist. The active scanner now reports LP07
survivors in `resources/command.py`, `resources/stage.py`, and retention code
unless they go through `insula.launch_plan`. `resources.command` keeps only the
narrow named `inspect_legacy_receipt_command(...)` compatibility shim for old
receipts, and that shim delegates to `insula.launch_plan`.

Kept the LP07 mount-order resolution when moving checks into the launch-plan
module: resource wrapper rendering and rendered-record comparison now follow
`render_plan` order, with non-`/tmp` mounts first, then the `/tmp` tmpfs, then
mounts under `/tmp`. The strict resource proof checks moved from
`resources/command.py` / `resources/stage.py` into `insula.launch_plan`; the
check set is unchanged.

Restored strict legacy rootfs checking in
`training_execution.sustained_controller_backend.check_stage(...)`. The new
all-stage check remains, and when a stage lock object is unavailable legacy
receipts now fall back to the stage root (`GPU_ROOT`, `CPU_ROOT`, or
`METRICS_ROOT`) instead of skipping `/`. Added a regression case that tampers a
GPU stage rootfs to `CPU_ROOT`; it was proven red on `729a8ef` and green after
the fix. The `run_sustained_test.py` fixture was tightened to give fake resumed
backends per-stage runtime locks and matching command root mounts.

Review verification:

- Focused repaired target:
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/training_execution:run_sustained_test`
  passed `1/1`.
- Default CPU suite:
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`
  passed `185/185`. Count unchanged from the LP11 baseline.
- Parallax suite:
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`
  passed `17/17`. Count unchanged.
- Storage-boundary check:
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/blob_store:storage_boundary_test`
  passed `1/1`.
- Planted-red boundary proof:
  `SUREAL_LAUNCH_PLAN_PLANT_VIOLATION=1 PYTHONPATH=autonomy python3 -m unittest autonomy.insula.launch_plan_boundary_test.LaunchPlanBoundaryTests.test_active_code_uses_only_launch_plan_module_for_sandbox_and_lock_boundaries`
  failed as expected on 5 planted violations.
- GPU 1 precheck before CUDA: GPU 1 UUID
  `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619` was absent from
  `nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader`, and GPU 1
  memory was `4 MiB`.
- CUDA suite on GPU 1 only:
  `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`
  passed `30/30`. Count unchanged.
- `git diff --check` was clean.
