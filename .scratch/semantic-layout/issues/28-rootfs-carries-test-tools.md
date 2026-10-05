# 28: The perception rootfs carries the tools its tests need

**What to build:** A contributor runs the default perception test set and the tests that were excluded only because the rootfs lacks a tool now run and pass. A new version of the perception CPU rootfs carries git, curl, pytest and a C++ compiler, and the wrapper keeps its Bazel caches out of the directory that tests treat as their output mount. This closes follow-ups recorded while reviewing tickets 02, 03, 04 and 07.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] A new version of the perception CPU rootfs is built with git, curl, pytest (hash-pinned through a requirement lock) and a C++ compiler with binutils; Bazel 9.2 and every Python package of the current version are unchanged; the current and earlier rootfs versions and their locks are untouched on disk
- [x] The wrapper selects the new version for perception targets, and its unit tests cover the selection
- [x] The placeholder C++ toolchain is removed and Bazel resolves the rootfs compiler; a trivial C++ test target builds and passes to prove it
- [x] The modules tagged `requires_host_tools` only for git or curl, and the two tagged `requires_pytest`, lose those tags and pass in the default run; the pytest modules run under real pytest, not an emulation; any module that still cannot run keeps a tag with its actual error recorded
- [x] The wrapper mounts its Bazel caches at a dedicated path that is not `/outputs`, so a test that inspects `/outputs` never sees Bazel writing there; `cohort/test_sustained_worker_guard` passes ten consecutive runs under `--config=cuda`
- [x] The default run, the `--config=cuda` run and `//parallax/...` all pass, with counts recorded against the previous counts (139 default, 24 GPU, 17 curriculum)
- [x] The GPU rootfs is left as it is unless a GPU-tagged test needs one of these tools; if so, say which and stop with needs-info

## Comments

Built:

- Added CPU rootfs `rootfs-v4` for autonomy at `/data02/home/philip.yang/.cache/waystone/waymo-perception/insula/rootfs-v4` with lock `/data02/home/philip.yang/.cache/waystone/waymo-perception/insula/rootfs-v4.lock.json`. It keeps Bazel 9.2.0 and the existing Python package versions from `rootfs-v3`, and adds only the hash-locked pytest toolchain packages: `iniconfig==2.3.0`, `packaging==26.3`, `pluggy==1.6.0`, `pygments==2.21.0`, `pytest==9.1.1`.
- Updated `autonomy/insula/Dockerfile` and `autonomy/build.sh` to install and validate git, curl, g++, ar, and pytest, and to record `requirements-test-tools.lock` in the rootfs lock.
- Updated `bazelw` to select autonomy `rootfs-v4`, mount `.bazel-cache` at `/tmp/bazel-cache`, mount `/outputs` as tmpfs, and set `HOME=/tmp/bazel-cache/home`.
- Removed the placeholder null C++ toolchain and added `//autonomy:rootfs_compiler_smoke_test` as the rootfs compiler proof.
- Removed `requires_host_tools` and `requires_pytest` tags. The two pytest modules run through `python -m pytest -q` in `autonomy/tools/bazel_test_runner.py`.
- Kept `tests/test_motion_causal_projection.py` out of the default run with specific tags `requires_motion_causal_project_binary` and `requires_upstream_protoc`; with filters cleared it fails on `FileNotFoundError: [Errno 2] No such file or directory: 'protoc'`.
- Added a Git-unavailable fallback to `autonomy/tools/layers.py` for Bazel sandbox/runfiles execution. The fallback is needed because Bazel mounts the linked-worktree `.git` file without the external common git dir.
- Added curriculum rootfs `rootfs-v2` at `/data02/home/philip.yang/.cache/waystone/3d-pathway/insula/rootfs-v2` with lock `/data02/home/philip.yang/.cache/waystone/3d-pathway/insula/rootfs-v2.lock.json`, preserving `rootfs-v1`. This is needed after removing the null C++ toolchain because `rules_cc` auto-configuration analyzes `//parallax/...` and requires gcc/g++/binutils in the selected rootfs.
- Left the GPU rootfs unchanged. No GPU-tagged test needed git, curl, pytest, or a new GPU image; `--config=cuda` now runs the documented GPU-tagged suite instead of all default CPU targets inside the GPU rootfs.

Verification:

- Red seam checks observed before fixes:
  - `./bazelw test //autonomy:association__test_contract //autonomy:association__test_provenance //autonomy:tests__test_gcs_bootstrap //autonomy:tools__test_layers //autonomy:tools__test_pins //autonomy:viewer__tests__test_repo_hygiene //autonomy:tools__test_bazel_test_runner` initially failed only on `//autonomy:tools__test_layers` with `git ls-files ... returned non-zero exit status 128`.
  - `PYTHONPATH=autonomy python3 -m unittest autonomy.tools.test_layers.LayerTests.test_sources_fall_back_to_package_files_when_git_metadata_is_unavailable` failed with the same `CalledProcessError`.
  - `./bazelw test //parallax/... --test_output=errors --cache_test_results=no` failed during analysis with `Auto-Configuration Error: Cannot find gcc or CC`.
  - `PYTHONPATH=autonomy python3 -m unittest autonomy.tests.test_bazel_wrapper.BazelWrapperTests.test_parallax_targets_select_the_curriculum_rootfs` failed after the test expectation moved to `rootfs-v2`, proving the wrapper still selected `rootfs-v1`.
- `autonomy/build.sh` -> `rootfs=/data02/home/philip.yang/.cache/waystone/waymo-perception/insula/rootfs-v4`, `lock=/data02/home/philip.yang/.cache/waystone/waymo-perception/insula/rootfs-v4.lock.json`.
- `parallax/insulas/build-bazel-rootfs.sh` -> `rootfs=/data02/home/philip.yang/.cache/waystone/3d-pathway/insula/rootfs-v2`, `lock=/data02/home/philip.yang/.cache/waystone/3d-pathway/insula/rootfs-v2.lock.json`.
- Rootfs probes:
  - autonomy `rootfs-v4`: `bazel 9.2.0`, `git version 2.39.5`, `curl 7.88.1`, `g++ (Debian 12.2.0-14+deb12u1) 12.2.0`, `GNU ar (GNU Binutils for Debian) 2.40`, `pytest 9.1.1`.
  - parallax `rootfs-v2`: `bazel 9.2.0`, `git version 2.39.5`, `g++ (Debian 12.2.0-14+deb12u1) 12.2.0`, `GNU ar (GNU Binutils for Debian) 2.40`, `numpy 1.26.4`.
- Rootfs identity checks:
  - autonomy `rootfs-v3`: identity `2393eb27861a802e21a91a401eb69c43aa6b8238900e197d26d16d89e7599ddd`, lock match true.
  - autonomy `rootfs-v4`: identity `429e7c76ff605dc634e21836e72c40f2ee9d756b0269b031f4e6ec222b057cbb`, lock match true.
  - parallax `rootfs-v1`: identity `a7f4622f81f7bf485c3e23a14152bbc07fe8dc5803717faa0443fadc1447c43b`, lock match true.
  - parallax `rootfs-v2`: identity `66fa7ebcbd864edc434dcb86384afe0c51266b1e0539138d00bf9b20e53cfc5a`, lock match true.
- Lock recipe hashes match the committed files:
  - autonomy `rootfs-v4`: `requirements_sha256`, `test_tools_requirements_sha256`, and `dockerfile_sha256` all match current files.
  - parallax `rootfs-v2`: `requirements_sha256` and `dockerfile_sha256` match current files.
- `PYTHONPATH=autonomy python3 -m unittest autonomy/tests/test_bazel_wrapper.py autonomy/tests/test_cpu_rootfs_build.py autonomy/tools/test_bazel_test_runner.py autonomy/tools/test_layers.py` -> `Ran 16 tests in 2.065s`, `OK`.
- `./bazelw test //autonomy:rootfs_compiler_smoke_test --test_output=errors --cache_test_results=no` -> `Executed 1 out of 1 test: 1 test passes`.
- `./bazelw test //autonomy:association__test_contract //autonomy:association__test_provenance //autonomy:tests__test_gcs_bootstrap //autonomy:tools__test_layers //autonomy:tools__test_pins //autonomy:viewer__tests__test_repo_hygiene //autonomy:tools__test_bazel_test_runner` -> `Executed 6 out of 7 tests: 7 tests pass`.
- `./bazelw query 'attr("tags", "requires_gpu", kind(py_test, //autonomy/...))' | wc -l` -> `24`.
- `./bazelw query 'attr("tags", "requires_host_tools", kind(py_test, //autonomy/...)) union attr("tags", "requires_pytest", kind(py_test, //autonomy/...))'` -> `INFO: Empty results`.
- `./bazelw query 'attr("tags", "requires_motion_causal_project_binary", kind(py_test, //autonomy/...)) union attr("tags", "requires_upstream_protoc", kind(py_test, //autonomy/...))'` -> `//autonomy:tests__test_motion_causal_projection`.
- `./bazelw test //autonomy:tests__test_motion_causal_projection --test_tag_filters= --test_output=errors --cache_test_results=no` -> failed as expected, `Executed 1 out of 1 test: 1 fails locally`, with `FileNotFoundError: [Errno 2] No such file or directory: 'protoc'`.
- `./bazelw test //autonomy:cohort__test_sustained_worker_guard --config=cuda --runs_per_test=10 --test_output=errors --cache_test_results=no` -> `Executed 1 out of 1 test: 1 test passes`, stats over 10 runs.
- `./bazelw test //autonomy/... --test_output=errors --cache_test_results=no` -> previous count 139 default; current result `Executed 147 out of 147 tests: 147 tests pass`.
- `./bazelw test //autonomy/... --config=cuda --test_output=errors --cache_test_results=no` -> previous count 24 GPU; current result `Executed 24 out of 24 tests: 24 tests pass`.
- `./bazelw --emit-plan test //parallax/...` -> selected `/data02/home/philip.yang/.cache/waystone/3d-pathway/insula/rootfs-v2` and `--output_base=/tmp/bazel-cache/output-base-3d-pathway`.
- `./bazelw test //parallax/... --test_output=errors --cache_test_results=no` -> previous count 17 curriculum; current result `Executed 17 out of 17 tests: 17 tests pass`.
- `git diff --check` -> no output, exit 0.

Pinned-file record:

- `python3 autonomy/tools/pins.py check --base work/semantic-layout/integration` before the implementation commit reported:
  - `tools/layers.py: cited by 1 receipt(s): research/journal-evidence/a059d4977ad3edc663115019abca6caf22fd80e1f59158eee9ecc60ef659a9b3`
  - `tools/test_layers.py: cited by 1 receipt(s): research/journal-evidence/a059d4977ad3edc663115019abca6caf22fd80e1f59158eee9ecc60ef659a9b3`
  - `FAIL: 2 changed file(s) cited by retained receipts`
- Reason: `autonomy/tools/layers.py` needed a source-discovery fallback for Bazel/rootfs sandboxes where `git` exists but linked-worktree metadata is unavailable, and `autonomy/tools/test_layers.py` covers that fallback. No `research/` files were modified. No `.py` files under `experiments/waymo-perception/{pipeline,gpu,tier1,cohort,resources}` were added, changed, or removed.

Review-1 integration update:

- Set the status line back to `**Status:** ready-for-agent` in commit `c38f1df` before merging.
- Merged `work/semantic-layout/integration` and resolved conflicts by keeping integration's source snapshot filegroups/genqueries and this ticket's real rootfs compiler smoke target. `autonomy/bazel_tests.bzl` keeps integration's `extra_data` support and this ticket's pytest-mode args/data wiring.
- Verified the cache mount move remains compatible with the merged source snapshot work: `bazelw` still binds `.bazel-cache` at `/tmp/bazel-cache`, keeps `/outputs` as tmpfs, and the merged controller stage guard checks `/tmp/source-snapshots` plus `SUREAL_SOURCE_SNAPSHOT_STORE=/tmp/source-snapshots`.
- `./bazelw test //autonomy:source_snapshot_targets_test //autonomy:architecture__test_experiment_runner //autonomy:cohort__test_sustained_controller_guards --test_output=errors --cache_test_results=no` -> `Executed 3 out of 3 tests: 3 tests pass`.
- `PYTHONPATH=autonomy python3 -m unittest autonomy/tests/test_bazel_wrapper.py` -> `Ran 6 tests in 0.402s`, `OK`.
- `./bazelw test //autonomy/... --test_output=errors --cache_test_results=no` -> previous ticket-28 post-fix count 147 default, post-integration count `Executed 148 out of 148 tests: 148 tests pass`.
- `./bazelw test --config=cuda --test_tag_filters=requires_gpu //autonomy/... --test_output=errors --cache_test_results=no` -> previous count 24 GPU, post-integration count `Executed 24 out of 24 tests: 24 tests pass`.
- `./bazelw test //parallax/... --test_output=errors --cache_test_results=no` -> previous count 17 curriculum, post-integration count `Executed 17 out of 17 tests: 17 tests pass`.
- `./bazelw test //autonomy:cohort__test_sustained_worker_guard --config=cuda --runs_per_test=10 --test_output=errors --cache_test_results=no` -> `Executed 1 out of 1 test: 1 test passes`, stats over 10 runs.
- `python3 autonomy/tools/pins.py check --base work/semantic-layout/integration` before the review-1 merge/update commit reported the same retained-evidence citations:
  - `tools/layers.py: cited by 1 receipt(s): research/journal-evidence/a059d4977ad3edc663115019abca6caf22fd80e1f59158eee9ecc60ef659a9b3`
  - `tools/test_layers.py: cited by 1 receipt(s): research/journal-evidence/a059d4977ad3edc663115019abca6caf22fd80e1f59158eee9ecc60ef659a9b3`
  - `FAIL: 2 changed file(s) cited by retained receipts`
- Pinned-file reason remains unchanged: `autonomy/tools/layers.py` and `autonomy/tools/test_layers.py` carry the Bazel/rootfs linked-worktree Git metadata fallback and its test. No `research/` files were modified. No `.py` files under `experiments/waymo-perception/{pipeline,gpu,tier1,cohort,resources}` were added, changed, or removed.
