# 02: GPU launch plans

**What to build:** A researcher requests a GPU by index on a launch plan and gets that device, the control and UVM devices, the driver libraries and the GPU environment, from the same code the Bazel launcher uses. The GPU live verifiers use it instead of copying device handling or taking a lock from an old receipt.

**Blocked by:** 01

**Status:** done

- [x] A plan takes an optional GPU index. The module adds the device, control and UVM devices, driver libraries under `/driver` and the GPU environment, honours `SUREAL_BAZEL_GPU_DEVICES`, and never picks a GPU itself
- [x] The Bazel launcher's GPU configuration and the launch-plan module share one implementation
- [x] The receipt record names the GPU by requested index and device UUID, not device paths
- [x] `insula/verify_gpu_live.py` and `insula/verify_gpu_isolation.py` use GPU launch plans and the module's lock loading. Neither copies device handling nor reads a runtime lock out of an old receipt
- [x] Offline tests cover the GPU additions using a fake device list. A `requires_gpu` test runs a trivial CUDA query through a GPU plan on GPU 1 and records its pass
- [x] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded

## Comments

### 2026-10-09 worker evidence

Done. Implemented GPU launch plans with explicit requested GPU index metadata, shared the GPU mount/environment implementation between `insula.launch_plan` and the Bazel launcher, recorded GPU receipts by requested index plus device UUID, and migrated `insula/verify_gpu_live.py` and `insula/verify_gpu_isolation.py` to build fresh checked launch plans instead of splicing GPU argv or replaying receipt commands.

Verification run from this worker worktree, with logs under `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/lp02-gpu-plans-20261009T010151Z/tmp`:

- Red/green focused tests:
  - `PYTHONPATH=autonomy python3 -m unittest autonomy.insula.launch_plan_test.LaunchPlanTests.test_gpu_plan_uses_requested_device_only_and_records_uuid_not_paths`: failed first on missing `plan_data()["gpu"]`, then passed.
  - `PYTHONPATH=autonomy python3 -m unittest autonomy.insula.bazel_wrapper_test.BazelWrapperTests.test_cuda_config_selects_gpu_rootfs_and_projects_driver_inputs`: failed first on missing emitted `gpu` metadata, then on missing nested GPU-rootfs test environment, then passed.
  - `PYTHONPATH=autonomy python3 -m unittest autonomy.insula.gpu_verifier_plan_test`: failed first because verifier helpers were absent and old source patterns remained, then passed.
- Focused Bazel coverage: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/insula:launch_plan_test //autonomy/insula:bazel_wrapper_test //autonomy/insula:gpu_verifier_plan_test`: passed, 3/3 tests.
- New real GPU live test: `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/insula:launch_plan_gpu_live_test`: passed, 1/1 test. GPU 1 was checked immediately before the successful run at `4 MiB / 183359 MiB, 0%`.
- Default CPU suite: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: passed, 169/169 tests. Ticket baseline was 168; new count is 169.
- Parallax suite: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`: passed, 17/17 tests.
- CUDA suite on GPU 1 only: `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: passed, 29/29 tests including `//autonomy/insula:launch_plan_gpu_live_test`. GPU 1 was checked before the full CUDA run at `4 MiB / 183359 MiB, 0%` and after the run at `4 MiB / 183359 MiB, 0%`.

### 2026-10-09 coordinator review fix evidence

Fixed the reviewed safety issue where `SUREAL_BAZEL_GPU_DEVICES` could override a GPU 1 plan with a different `/dev/nvidiaN` node. Override entries now reject any host or guest path that names a per-GPU node other than the requested index, allow only the requested per-GPU node plus NVIDIA control/UVM/modeset nodes as inside device paths, and still allow remapped host paths for tests and nonstandard host layouts.

Verification run from this worker worktree, with logs under `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/lp02-gpu-plans-20261009T010151Z/tmp`:

- Red/green focused test: `PYTHONPATH=autonomy python3 -m unittest autonomy.insula.launch_plan_test.LaunchPlanTests.test_gpu_device_override_rejects_different_gpu_index autonomy.insula.launch_plan_test.LaunchPlanTests.test_gpu_device_override_accepts_remapped_host_paths_for_requested_index` failed first because host and guest `/dev/nvidia0` overrides were accepted for a GPU 1 plan, then passed after the validation fix.
- Focused Python coverage: `PYTHONPATH=autonomy python3 -m unittest autonomy.insula.launch_plan_test autonomy.insula.bazel_wrapper_test autonomy.insula.gpu_verifier_plan_test`: passed, 24/24 tests.
- Focused Bazel coverage: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/insula:launch_plan_test //autonomy/insula:bazel_wrapper_test //autonomy/insula:gpu_verifier_plan_test`: passed, 3/3 tests.
- Default CPU suite: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: passed, 169/169 tests.
- Parallax suite: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`: passed, 17/17 tests.
- CUDA suite on GPU 1 only: `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: passed, 29/29 tests including `//autonomy/insula:launch_plan_gpu_live_test`. GPU 1 was checked before the run at `4 MiB / 183359 MiB, 0%` and after the run at `4 MiB / 183359 MiB, 0%`.
