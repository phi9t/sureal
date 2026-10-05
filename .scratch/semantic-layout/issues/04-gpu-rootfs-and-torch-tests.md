# 04: Torch tests run under Bazel in the GPU rootfs

**What to build:** A contributor opts in to the GPU configuration and the 26 torch-dependent test modules run under Bazel inside a new version of the GPU rootfs, without staging a live gate. The default run still works on the CPU rootfs alone.

**Blocked by:** 03 (Every perception CPU test runs under Bazel, in place)

**Status:** ready-for-agent

- [x] A new version of the GPU rootfs carries Bazel 9.2 with the same packages as the current GPU image; the current image is untouched
- [x] The wrapper selects the GPU rootfs when the GPU configuration is requested, and projects the host driver libraries as the existing GPU gates do
- [x] The 26 torch modules run under the GPU configuration and their results are recorded
- [x] The default configuration excludes every GPU-tagged target
- [x] CUDA use is opt-in; torch tests that need only the CPU run without a visible GPU

## Comments

- Built an additive Bazel-enabled GPU rootfs recipe in `experiments/waymo-perception/gpu/Dockerfile.bazel-rootfs-v6` and `experiments/waymo-perception/gpu/build_bazel_rootfs_v6.sh`. The legacy cited `gpu/Dockerfile` and `gpu/build.sh` are unchanged so retained research receipts still describe the same bytes.
- Created `/data02/home/philip.yang/.cache/waystone/waymo-perception/gpu-rootfs-v6` and `/data02/home/philip.yang/.cache/waystone/waymo-perception/gpu-rootfs-v6.lock.json`. The existing `/data02/home/philip.yang/.cache/waystone/waymo-perception/gpu-rootfs` and lock were preserved by identity checks in the builder.
- Updated `bazelw` so `--config=cuda` selects `gpu-rootfs-v6`, uses `/outputs/output-base-gpu`, projects `/dev/nvidia1`, `/dev/nvidiactl`, `/dev/nvidia-uvm`, and binds driver libraries with prefixes `libcuda.so`, `libnvidia-ptxjitcompiler.so`, and `libnvidia-nvvm.so` into `/driver`.
- Updated the wrapper workspace mount plan to keep `/experiment` as a tmpfs layer with repo-root entries and non-conflicting Waymo child directories. This preserves legacy absolute `/experiment/<waymo-child>` paths while Bazel still runs from the repo root.
- After merging ticket 06, the workspace mount bridge still mounts top-level `parallax/` at `/experiment/parallax` and no longer depends on `experiments/3d-pathway`. The bridge is temporary compatibility for legacy absolute `/experiment/<child>` paths; ticket 26 removes it.
- Marked the two torch-dependent CPU-only guard targets with `env = {"CUDA_VISIBLE_DEVICES": ""}` while keeping them `requires_gpu` so they run only in the opt-in GPU configuration but cannot see CUDA.
- Current Bazel inventory has 24 `requires_gpu` `py_test` targets, not 26. `./bazelw query 'attr("tags", "requires_gpu", kind(py_test, //experiments/waymo-perception/...))' | wc -l` returned `24`; all 24 are recorded below and passed under `--config=cuda`.
- Pinned files changed: none under `experiments/waymo-perception/{pipeline,gpu,tier1,cohort,resources}` as `.py` files. Retained-receipt cited files changed: none; `python3 experiments/waymo-perception/tools/pins.py check --base work/semantic-layout/integration` returned `PASS: 0 changed file(s) cited by retained receipts`.
- The recipe is named `v6` because five build iterations were needed. The lead deleted the superseded `gpu-rootfs-v2` through `gpu-rootfs-v5` builds, reclaiming 52 GB; future failed rootfs builds from this ticket should be deleted before building the next version because they are this branch's own state, not shared state.

Verification:

- `PYTHONPATH=experiments/waymo-perception python3 -m unittest experiments/waymo-perception/tests/test_bazel_wrapper.py experiments/waymo-perception/tests/test_gpu_rootfs_build.py` -> `Ran 7 tests in 0.684s`, `OK`.
- `bash experiments/waymo-perception/gpu/build_bazel_rootfs_v6.sh` -> `rootfs=/data02/home/philip.yang/.cache/waystone/waymo-perception/gpu-rootfs-v6`, `lock=/data02/home/philip.yang/.cache/waystone/waymo-perception/gpu-rootfs-v6.lock.json`.
- `bwrap ... -- bazel --version` inside `gpu-rootfs-v6` -> `bazel 9.2.0`.
- `bwrap ... -- /usr/bin/python3.12 -c 'import torch; print(torch.__version__)'` inside `gpu-rootfs-v6` -> `2.9.1+cu130`.
- `bwrap ... -- /usr/local/bin/python -c 'import sys, torch; print(sys.executable); print(torch.__version__)'` inside `gpu-rootfs-v6` -> `/opt/waymo/bin/python`, `2.9.1+cu130`.
- `./bazelw test //experiments/waymo-perception:tests__test_bazel_wrapper //experiments/waymo-perception:tests__test_gpu_rootfs_build --test_output=errors --cache_test_results=no` -> `Executed 2 out of 2 tests: 2 tests pass.`
- `./bazelw query 'attr("tags", "requires_gpu", kind(py_test, //experiments/waymo-perception/...))' | wc -l` -> `24`.
- `./bazelw test --config=cuda $(./bazelw query 'attr("tags", "requires_gpu", kind(py_test, //experiments/waymo-perception/...))' | rg '^//') --test_output=errors --cache_test_results=no --keep_going` -> `Executed 24 out of 24 tests: 24 tests pass.`
- `./bazelw query 'kind(py_test, //experiments/waymo-perception/...) except attr("tags", "requires_gpu", kind(py_test, //experiments/waymo-perception/...))' | wc -l` -> `155`; the same command output did not contain sampled GPU targets `advanced__test_models`, `tests__test_detector_loss`, or `cohort__test_sustained_transition_guard`.
- `./bazelw test //experiments/waymo-perception:tests__test_detector_loss --test_output=errors --cache_test_results=no --nobuild` under the default config -> expected exit `1` with `WARNING: All specified test targets were excluded by filters`, `Found 1 target and 0 test targets`.
- `./bazelw test //experiments/waymo-perception/... --test_output=errors --cache_test_results=no` -> `Executed 138 out of 138 tests: 138 tests pass.`
- `./bazelw query --output=build '//experiments/waymo-perception:cohort__test_sustained_transition_guard + //experiments/waymo-perception:cohort__test_sustained_worker_guard' | rg -n 'name =|env =|CUDA_VISIBLE_DEVICES|tags =|requires_gpu'` -> both targets show `tags = ["perception_unit", "requires_gpu"]` and `env = {"CUDA_VISIBLE_DEVICES": ""}`.
- `python3 experiments/waymo-perception/tools/pins.py check --base work/semantic-layout/integration && git diff --check` -> `PASS: 0 changed file(s) cited by retained receipts`; `git diff --check` produced no output.

Review 1 merge update:

- Merged `work/semantic-layout/integration` and resolved conflicts in `bazelw` and `experiments/waymo-perception/tests/test_bazel_wrapper.py` by keeping both ticket 06 behavior and this ticket's GPU behavior.
- `bazelw` now keeps parallax target routing, the autonomy/parallax spanning-pattern refusal, lock-update mode, GPU rootfs selection, GPU output base, driver/device projection, and the temporary `/experiment` workspace bridge.
- `TMPDIR=$PWD/.bazel-cache/tmp PYTHONPATH=experiments/waymo-perception python3 -m unittest experiments/waymo-perception/tests/test_bazel_wrapper.py experiments/waymo-perception/tests/test_gpu_rootfs_build.py` -> `Ran 8 tests in 0.767s`, `OK`. A direct run without `TMPDIR` hit host `/tmp` capacity before assertions; no checks were weakened.
- `./bazelw test //experiments/waymo-perception:tests__test_bazel_wrapper //experiments/waymo-perception:tests__test_gpu_rootfs_build --test_output=errors --cache_test_results=no` -> `Executed 2 out of 2 tests: 2 tests pass.`
- `./bazelw test //experiments/waymo-perception/... --test_output=errors --cache_test_results=no` -> `Executed 138 out of 138 tests: 138 tests pass.`
- `./bazelw test --config=cuda --test_tag_filters=requires_gpu //experiments/waymo-perception/... --test_output=errors --cache_test_results=no` -> `Executed 24 out of 24 tests: 24 tests pass.`
- `./bazelw test //parallax/... --test_output=errors --cache_test_results=no` -> `Executed 17 out of 17 tests: 17 tests pass.`
- `./bazelw --emit-plan test //...` -> exit `2`, `target pattern spans autonomy and parallax; run each component separately so the wrapper can select the correct rootfs`.
- `python3 experiments/waymo-perception/tools/pins.py check --base work/semantic-layout/integration && git diff --check` -> `PASS: 0 changed file(s) cited by retained receipts`; `git diff --check` produced no output.
