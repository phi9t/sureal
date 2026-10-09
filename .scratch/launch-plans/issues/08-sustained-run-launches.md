# 08: The sustained run launches from fresh launch plans

**What to build:** The balanced16 sustained run's admission, controller, training, replay and transition audit build fresh launch plans (GPU plans for GPU stages, CPU and metrics plans otherwise) instead of replaying the command from an old receipt (`detector-gpu-live-a`) and rewriting it by mount target.

**Blocked by:** 02, blob-store 11 (the blob-store migration rewrites the sustained run's storage)

**Status:** done

- [x] `training_execution/admit_sustained.py`, `sustained_controller_backend.py`, `train_sustained.py`, `replay_sustained.py` and `audit_sustained_transition.py` build launch plans and load the GPU, CPU and metrics locks through the module. No code reads a command or a runtime lock out of an old receipt, and `rebind_rootfs_mount` is deleted
- [x] Every input spliced today (`/tmp/inputs`, `/tmp/native`, `/tmp/physical`, `/tmp/boxes`, `/tmp/runtime-lock.json`, `/tmp/scientific` and the snapshot store) is a named input. `CUBLAS_WORKSPACE_CONFIG` is declared environment
- [x] GPU stages request GPU 1 by index from the run's own configuration
- [x] Offline tests assert on each stage's plan. A `requires_gpu` smoke test runs one trivial stage through the controller's GPU plan on GPU 1
- [x] The sustained run is not re-admitted here. Blob-store 12 does that once, after this ticket
- [x] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded

## Comments

### 2026-10-09 worker evidence

Moved sustained admission, controller, train, replay and transition-audit launches onto direct calls to `autonomy/insula/launch_plan.py`. The stages load GPU, CPU and metrics runtime locks with `load_default_runtime_lock`/`load_runtime_lock`, build plans through `build_plan`, render with `render_plan`, and record the launch-plan receipt data. No sustained run was re-admitted here.

The strict checks were preserved in these places:

- Whole runtime-lock equality remains in `autonomy/training_execution/sustained_sources.py::validate_sources`, with recipe-digest GPU locks accepted after launch-plan loading while equality and 64-hex rootfs digest checks remain strict.
- Worker runtime-lock reads remain strict at `/tmp/runtime-lock.json`; stage data files moved from `/source` to `/tmp/inputs` to avoid duplicate host mounts.
- Mount duplicate and overlap checks remain in `autonomy/insula/launch_plan.py`. The only additive exception is explicit `allow_readonly_inputs_cover_output=True` for sustained stages, allowing the read-only `/tmp/scientific` named input to cover writable output beneath the same scientific-processing tree.
- `render_plan()` now renders the `/tmp` tmpfs before named inputs under `/tmp/*`; this keeps the same checks but fixes real bwrap ordering for `/tmp/inputs`.

Focused verification:

- `PYTHONPATH=autonomy python3 -m unittest autonomy.training_execution.sustained_launch_plan_test autonomy.training_execution.sustained_sources_test.SustainedSourceTests.test_runtime_admission_accepts_recipe_digest_lock_loaded_by_launch_plan`: passed.
- `PYTHONPATH=autonomy python3 -m unittest autonomy.training_execution.sustained_controller_backend_test autonomy.training_execution.run_sustained_test autonomy.training_execution.sustained_stage_inputs_test autonomy.training_execution.sustained_sources_test`: passed, 38 tests.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/insula:launch_plan_test //autonomy/training_execution:sustained_launch_plan_test`: passed, 2/2 tests.
- Forbidden old-launch scan returned no matches for `detector-gpu-live-a`, `rebind_rootfs_mount`, old `insula.entry.launch_plan` imports, `verify_rootfs(`, old command replay, or `command.index('--')` in the five sustained-run launch files.

GPU smoke evidence:

- GPU 1 was checked before the smoke: UUID `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619`, memory used `4 MiB`, and no compute app on that UUID.
- `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/training_execution:sustained_launch_plan_gpu_smoke_test`: passed, 1/1 test in 26.7s. The test is tagged `requires_gpu` and runs one trivial controller GPU-stage plan requesting GPU index 1.

Required gates:

- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: passed, 185/185 tests. This matches the ticket-12 launch-plan base count.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`: passed, 17/17 tests. This matches the launch-plan base count.
- GPU 1 became occupied after the smoke, so the CUDA gate waited and rechecked. It was free again at `2026-10-09T11:16:47Z` with memory used `4 MiB` and no compute app on the GPU 1 UUID.
- `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: passed, 30/30 tests in 118.974s. The count increases from the ticket-12 launch-plan base of 29 because this ticket adds `//autonomy/training_execution:sustained_launch_plan_gpu_smoke_test`.
- `git diff --check`: passed.

### 2026-10-09 review fix evidence

Coordinator review found that GPU driver pinning was weaker than the old sustained-run path. Fixed this at the launch-plan seam: GPU driver mounts now carry build-time file sha256 digests in the plan, `record_plan()` records those digests, and `render_plan()` refuses a plan if a pinned driver file changes before execution. Sustained admission and controller receipts copy those plan driver pins into `driver_hashes` as path-to-sha256 evidence for GPU stages; non-GPU stages keep `{}`. `check_stage()` now requires non-empty GPU `driver_hashes`, checks that they equal the recorded GPU driver mount digests by mounted driver filename, and re-verifies the driver files from the receipt paths.

Added red/green coverage:

- `autonomy.insula.launch_plan_test.LaunchPlanTests.test_gpu_plan_uses_requested_device_only_and_records_uuid_not_paths`: initially failed because GPU driver mounts had no plan digest; now passes and also proves `render_plan()` rejects a changed driver file.
- `autonomy.training_execution.sustained_controller_backend_test.ControllerGuardTests.test_gpu_stage_receipt_rechecks_driver_hashes_from_launch_plan`: initially failed because non-empty `driver_hashes` were rejected; now passes and proves a changed driver file fails `check_stage()`.

The `/tmp` render-ordering change remains scoped to plans with before-device mounts under `/tmp/*`. I checked the non-sustained launch-plan callers by scanning `build_plan` uses and rerunning their Bazel coverage in the full CPU gate (`//autonomy/...`), including dataset, camera, geometry, inspection, segmentation, evaluation and Insula launch tests. Plans without `/tmp/*` named inputs render the same relative non-`/tmp` mount order; plans with `/tmp/*` now render the `/tmp` tmpfs first so bwrap can create those mountpoints. `allow_readonly_inputs_cover_output=True` is still limited to sustained stages: it permits the old-command-equivalent read-only `/tmp/scientific` mount over the scientific-processing root while stage outputs remain writable descendants under that same tree.

Review-fix verification:

- `PYTHONPATH=autonomy python3 -m unittest autonomy.insula.launch_plan_test autonomy.training_execution.sustained_controller_backend_test autonomy.training_execution.sustained_launch_plan_test autonomy.training_execution.run_sustained_test`: passed, 43 tests.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: passed, 185/185 tests.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`: passed, 17/17 tests.
- CUDA smoke and full CUDA gate were deferred on this review-fix rerun because GPU 1 stayed occupied for the full one-hour wait. Checks at `2026-10-09T11:40:45Z`, `11:50:45Z`, `12:00:45Z`, `12:10:46Z`, `12:20:47Z` and `12:30:48Z` all listed GPU 1 UUID `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619` in `nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader`; memory went from `175859 MiB` down to `26 MiB`, but the UUID remained present in compute apps.
