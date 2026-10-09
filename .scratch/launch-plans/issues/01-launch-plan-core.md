# 01: Launch-plan module with full runtime-lock checking

**What to build:** A researcher loads a runtime lock and gets back a launch plan describing one execution inside a dedicated Insula. The plan uses code, an optional source, an output, named inputs, environment and a command, and the researcher can read it as data, render it to run, and record it in a receipt. The lock is checked in full in either form before any plan exists. `insula/entry` and the Bazel launcher are rebuilt on the module, so both existing entry points prove it end to end. See `.scratch/launch-plans/spec.md` and autonomy ADR 0003.

**Blocked by:** none; the stale GPU `rootfs-v6` lock blocker was resolved by building and promoting `gpu-rootfs-v7`.

**Status:** done

- [x] The module in `insula` exposes only these operations: load runtime lock, build plan, read plan as data, render plan, record plan. It absorbs `sandbox_plan`, the lock reading in `entry`, and `runtime_identity`'s content check
- [x] Both lock forms are checked in full: the recipe-digest form (`rootfs-v4`, `rootfs-v6`: schema, Dockerfile, requirements, test-tools requirements when present, Bazel version and binary when present, content digest) and the image form (metrics and motion-CLI: image id, recipe hashes, parent image when named, content digest). A missing lock is an error. Each failure names the field
- [x] The content digest is cached per root filesystem path and lock digest for the life of the process. The time to check `rootfs-v4` and `rootfs-v6` uncached is measured and recorded in the ticket
- [x] Mount rules hold: no host directory mounted twice, no writable mount overlapping any other, read-only mounts may nest, and errors name both roles. The source mount is optional. Named inputs are restricted to `/tmp`, `/opt`, `/srv` and `/mnt`. Extra environment that collides with a module-owned variable is an error
- [x] The receipt record lists the runtime by lock digest and form, mounts by role, inside path, mode and digest, the environment and the command, with no host paths
- [x] `insula/entry` checks the lock before emitting or executing a plan, and defaults to the root filesystem the Bazel launcher uses. The Bazel launcher builds its plan through the module and gains the recipe check. Its existing structural tests still pass
- [x] The current CPU, GPU, metrics and motion-CLI root filesystems are named in exactly one place that every launch reads. Semantic-layout ticket 29 left the current CPU root's name repeated in six modules (Bazel launcher, resource backend, sustained admission, sustained controller, M0 receipt, semantic-recovery runtime), and `insula/entry` still defaults to `rootfs-v2`
- [x] Offline tests with fixture locks in both forms and a tiny fixture root filesystem cover every lock failure, the cache, every mount rule and environment collisions, all asserting on plans as data
- [x] A `requires_live_gate` test runs a trivial command through a real plan in the current CPU root filesystem and records its pass
- [x] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded

## Comments

### 2026-10-09 worker evidence

Implemented the launch-plan core, moved `autonomy/insula/entry.py` and the Bazel launcher onto it, and centralized the current CPU, GPU, metrics and motion-CLI root filesystem names in `autonomy/insula/runtime_roots.py`.

Verification run from this worker worktree, with logs under `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/lp01-launch-plan-core-20261008T234853Z/tmp`:

- Focused module/compatibility tests: Python unittest suite passed 39 tests across launch-plan, entry, live-gate, Bazel wrapper, resources backend, sustained controller and semantic-recovery coverage.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/insula/...`: passed, 9/9 tests.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors --test_tag_filters=requires_live_gate,-requires_gpu,-known_failure //autonomy/insula:launch_plan_live_test`: passed, 1/1 test. This is the real `requires_live_gate` trivial-command launch through the current CPU root filesystem.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: passed, 159/159 tests. Baseline in ticket was 158; new count is 159.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`: passed, 17/17 tests.
- `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: attempted with GPU 1 free, but failed before executing tests because the strict recipe check rejected the existing GPU lock: `dockerfile_sha256: expected 4bf7096c4e1b9d70dac3fdc8eb0387ea57bd6b71f40daec76f88d13c6a037bfd, found '4e0eb315fe262dac2e438085e64410513d9284c9aa6618e1b6cb90a0fad4faf7'`.

Measured uncached content-digest times:

- Current CPU `rootfs-v5`: 2.850s raw `rootfs_identity`, digest `09b794f6fb2797f9f798bcb09e97478a04044536f87f636eddc85c82361d1962`.
- Historical CPU `rootfs-v4`: 2.871s raw `rootfs_identity`, digest `429e7c76ff605dc634e21836e72c40f2ee9d756b0269b031f4e6ec222b057cbb`.
- GPU `rootfs-v6`: 25.127s raw `rootfs_identity`, digest `5a1af6a165eb3d59781eda28fee6acd2672b6a53e3645252eeb6579beb720eb4`.
- Earlier full `load_runtime_lock` check for the current CPU rootfs measured 2.819s.

Additional CUDA blocker evidence: the checked-in `autonomy/insula/Dockerfile.gpu-bazel-rootfs-v6` hashes to `4bf7096c4e1b9d70dac3fdc8eb0387ea57bd6b71f40daec76f88d13c6a037bfd`, while the existing GPU lock records `4e0eb315fe262dac2e438085e64410513d9284c9aa6618e1b6cb90a0fad4faf7`. The checked-in `autonomy/insula/gpu-requirements.lock` hashes to `fee5c337db2d227df763b7ba085a8df00e089708ded4c97e5a39a24879b0de9a`, while the existing GPU lock records `038ba6bbc16870b6430481127b15ab2830e5dac0a6b14c30f218a43853e35923`. The read-only comparison worktrees `final26-closeout-verify` and `final26-review` show the same current GPU recipe hashes, so the local GPU lock is stale against the current source.

### 2026-10-09 gpu-rootfs-v7 closeout evidence

Built a fresh GPU Bazel root filesystem from the current committed recipe without modifying or deleting `gpu-rootfs-v6` or its lock:

- Command: `WAYMO_GPU_INSULA_PREVIOUS_ROOT=/data02/home/philip.yang/.cache/waystone/waymo-perception/gpu-rootfs-v6 WAYMO_GPU_INSULA_ROOT=/data02/home/philip.yang/.cache/waystone/waymo-perception/gpu-rootfs-v7 WAYMO_GPU_INSULA_IMAGE_TAG=sureal-waymo-gpu:bazel-9.2.0-rootfs-v7 bash autonomy/insula/build_gpu_bazel_rootfs_v6.sh`
- Log directory: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/lp01b-logs/build-v7.Xg20AF`
- Build time: 150s.
- Required base image was present locally as `sha256:eaf68603ced6f9abb5ee401522a07774183a8412ff3d9de61278f09c0738749d`.
- Built image id: `sha256:da548988f6d6e6b442f986a9d5f90f159b5ecf1a4c619fed497ee2fc958072f4`.
- New rootfs content digest: `14908ff0fa2c9a712ea106de684b261bee9bbcf296bd52c3dc24685592044941`.
- New lock file digest: `c68df2817045b7a947e454a849005f26b8fece30613db77f6dee5d13bcdbb131`.
- New lock `dockerfile_sha256`: `4bf7096c4e1b9d70dac3fdc8eb0387ea57bd6b71f40daec76f88d13c6a037bfd`, matching `autonomy/insula/Dockerfile.gpu-bazel-rootfs-v6`.
- New lock `requirements_sha256`: `fee5c337db2d227df763b7ba085a8df00e089708ded4c97e5a39a24879b0de9a`, matching `autonomy/insula/gpu-requirements.lock`.
- New lock Bazel fields: `bazel_version=9.2.0`, `bazel_linux_x86_64_sha256=7668a95db1250f12c40407251e4e203b4ec8bf39bc495d2f485b2d8c99048694`.
- The build script left no container behind for `sureal-waymo-gpu:bazel-9.2.0-rootfs-v7`.

Promoted the current GPU root in the single runtime-roots registry to `gpu-rootfs-v7`. The full ADR 0003 lock check accepts it through `insula.launch_plan.load_runtime_lock(current_gpu_rootfs(), default_lock(current_gpu_rootfs()))` as recipe-digest form, with lock digest `c68df2817045b7a947e454a849005f26b8fece30613db77f6dee5d13bcdbb131`.

While rerunning the CUDA gate after the stale lock was fixed, the launcher hit a separate strict-mount failure on host driver symlink aliases: `gpu-driver:libcuda.so.580.105.08 and gpu-driver:libcuda.so.580.105.08: duplicate inside mount /driver/libcuda.so.580.105.08`. Added a regression to `bazel_wrapper_test` for symlinked driver aliases, kept inside mount names as discovered aliases, and kept the duplicate host-mount rule strict except for the same read-only regular file mounted under multiple aliases.

Verification run from this worker worktree, with logs under `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/lp01b-logs/gates.2wy4cz`:

- Red/green focused test: `PYTHONPATH=autonomy python3 autonomy/insula/bazel_wrapper_test.py -k cuda_config_selects_gpu_rootfs_and_projects_driver_inputs` failed first on `gpu-rootfs-v6`, then passed after promoting `gpu-rootfs-v7`; after the driver-alias regression was added, it failed first on duplicate driver mounts, then passed after the alias-preserving fix.
- Focused unit coverage after the driver-alias fix: `PYTHONPATH=autonomy python3 autonomy/insula/launch_plan_test.py && PYTHONPATH=autonomy python3 autonomy/insula/bazel_wrapper_test.py`: passed 9/9 launch-plan tests and 9/9 wrapper tests.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: passed, 159/159 tests after the final code change.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`: passed, 17/17 tests.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors --test_tag_filters=requires_live_gate,-requires_gpu,-known_failure //autonomy/insula:launch_plan_live_test`: passed, 1/1 test.
- `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: passed on GPU 1, 28/28 tests. GPU 1 was checked immediately before the final CUDA run at `4 MiB / 183359 MiB, 0%`, and after the run it was again `4 MiB / 183359 MiB, 0%`.
