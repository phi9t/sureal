# 02: One wrapper command runs Bazel inside Insula

**What to build:** A contributor types one repository-level wrapper command and a Bazel test of one existing perception unit test runs inside the new CPU rootfs and passes. The wrapper is the only entry point: it verifies the rootfs, enters the sandbox, and runs Bazel with persistent caches. This ticket also settles which Bazel spawn strategy and server mode work when nested inside the Insula sandbox.

**Blocked by:** 01 (A new version of the CPU rootfs carries Bazel 9.2)

**Status:** ready-for-agent

- [x] The repository root has the Bazel module file, its committed lock file, the Bazel version file and the Bazel configuration; packages are declared only for the two research programs
- [x] The Python toolchain is the rootfs interpreter with its installed packages; Bazel fetches no third-party Python package
- [x] The wrapper clears the environment, sets a fixed home, mounts the rootfs read-only, and mounts the repository and one git-ignored cache directory that is also listed in the Bazel ignore file
- [x] A second run of the same test is served from the persistent cache
- [x] The wrapper has a mode that prints the sandbox command as data without running it, covered by a unit test
- [x] The wrapper refuses to run, with a clear message, when the rootfs does not match its lock; covered by a unit test
- [x] The working spawn strategy and server mode are recorded in the Bazel configuration with a one-line reason each
- [x] Network is available inside the sandbox during the build

## Comments

Built:

- Added repository-level `bazelw`. It verifies `~/.cache/waystone/waymo-perception/insula/rootfs-v3` against `rootfs-v3.lock.json`, checks Bazel 9.2.0 in the lock, emits a JSON sandbox plan with `--emit-plan`, or executes Bazel through `bwrap`.
- Kept Bzlmod enabled. Normal wrapper runs pass `--lockfile_mode=error`; `--update-lock` runs with `--lockfile_mode=update` and bind-mounts only `MODULE.bazel.lock` writable over the read-only repository mount.
- Removed `WORKSPACE` and the legacy workspace flags `--enable_workspace`, `--noenable_bzlmod`, and `--repositories_without_autoloads=*`.
- Added `rules_python` as a `bazel_dep`, configured `local_runtime_repo` and `local_runtime_toolchains_repo` for `/usr/local/bin/python`, and registered that rootfs Python toolchain.
- Converted the initial test to `py_library` plus `py_test`, and added a second `py_test` for `tests/test_anchor_grid.py`, which imports `numpy` through the rootfs interpreter and the target's declared import roots.
- The committed Bazel files declare no `pip.parse`, PyPI, requirements, wheel, or hermetic Python-interpreter download configuration. The wrapper passes `--ignore_dev_dependency`; after regenerating the lock from a cleaned lock state, `MODULE.bazel.lock` has no `pip`, `pypi`, `pythonhosted`, requirements, or `.whl` entries.
- Registered a local null C++ toolchain target for this pure-Python gate because the CPU rootfs has no compiler/binutils and `rules_python` analysis loads `rules_cc`. It is only to satisfy toolchain resolution for these Python targets.
- Added `.bazel-cache/` to `.gitignore` and `.bazelignore`; the wrapper mounts it at `/outputs` and uses it for `--output_base`, `--repository_cache`, `--disk_cache`, and fixed `HOME=/outputs/home`.
- Added package declarations only under `experiments/3d-pathway/` and `experiments/waymo-perception/`.
- Recorded the working Bazel modes in `.bazelrc`: `startup --batch` because no Bazel server has to survive the Insula process namespace, and `standalone` spawn/test strategy because `linux-sandbox` is not registered inside `rootfs-v3`.
- Cleaned the ignored `.bazel-cache/` probe directories; the worktree cache now has one layout: `home`, `output-base`, `repository-cache`, and `disk-cache`.

Verification commands and results:

- Red test before implementation: `PYTHONPATH=experiments/waymo-perception python3 -m unittest experiments.waymo-perception.tests.test_bazel_wrapper -v`
  - Result: 2 failures, both reporting `repository-level Bazel wrapper is missing`.
- Red test for the review fix: `PYTHONPATH=experiments/waymo-perception python3 -m unittest experiments.waymo-perception.tests.test_bazel_wrapper -v`
  - Result before changing `bazelw`: 2 failures, covering the unwanted global `PYTHONPATH` sandbox environment and missing `--update-lock` behavior.
- `PYTHONPATH=experiments/waymo-perception python3 -m unittest experiments.waymo-perception.tests.test_bazel_wrapper -v`
  - Result: 3 tests, 0 failures.
- `PYTHONPATH=experiments/waymo-perception python3 -m unittest experiments.waymo-perception.tests.test_bazel_wrapper experiments.waymo-perception.tests.test_runtime_identity experiments.waymo-perception.tests.test_insula_entry experiments.waymo-perception.tests.test_cpu_rootfs_build -v`
  - Result: 9 tests, 0 failures.
- `git diff --check`
  - Result: passed.
- `find . -path './.bazel-cache' -prune -o -name BUILD.bazel -print | sort`
  - Result: only `./experiments/3d-pathway/BUILD.bazel` and `./experiments/waymo-perception/BUILD.bazel`.
- `rg -n -- "--enable_workspace|--noenable_bzlmod|--repositories_without_autoloads|\\bPYTHONPATH\\b|\\bpip\\b|pip_parse|pythonhosted|pypi|requirements|\\.whl" MODULE.bazel MODULE.bazel.lock .bazelrc experiments/waymo-perception/BUILD.bazel bazelw || true`
  - Result: no matches.
- `./bazelw --update-lock mod deps`
  - Result: passed and generated the committed Bzlmod lock.
- `jq 'keys, (.moduleExtensions // {} | keys), (.facts // {} | keys), .registryFileHashes | length' MODULE.bazel.lock`
  - Result: lock has 6 top-level keys, 3 module extensions, 0 facts, and 188 registry file hashes.
- `./bazelw query //...`
  - Result: package targets are only under `//experiments/waymo-perception:...`.
- `./bazelw --emit-plan test //experiments/waymo-perception:tools_test_suites`
  - Result: JSON plan starts with `bwrap`, contains `--clearenv`, fixed `HOME=/outputs/home`, read-only rootfs and repository mounts, `/etc/resolv.conf` mounted read-only, `.bazel-cache` mounted at `/outputs`, no `PYTHONPATH`, Bzlmod lockfile error mode, and Bazel cache flags under `/outputs`.
- `./bazelw --emit-plan --update-lock test //experiments/waymo-perception:tools_test_suites`
  - Result: JSON plan uses `--lockfile_mode=update` and includes the writable bind mount for `MODULE.bazel.lock` while retaining the read-only repository mount.
- Network probe using the emitted wrapper plan: `python3 - <<'PY' ... socket.create_connection(("bcr.bazel.build", 443), timeout=8) ... PY`
  - Result: `network-ok`.
- Stale-lock probe: temporarily restored the old empty lock, then ran `./bazelw test //experiments/waymo-perception:tools_test_suites --test_output=errors`
  - Result: failed with status 48 and `Missing checksum ... not permitted with --lockfile_mode=error. Please run bazel mod deps --lockfile_mode=update`.
- Stale-lock update probe: with only the temporary stale lock in place, ran `./bazelw --update-lock test //experiments/waymo-perception:tools_test_suites --test_output=errors`
  - Result: passed and changed only `MODULE.bazel.lock` relative to the pre-probe dirty set.
- `./bazelw --update-lock test //experiments/waymo-perception:tools_test_suites //experiments/waymo-perception:anchor_grid_test --test_output=errors`
  - Result: both targets passed.
- `./bazelw test //... --test_output=errors`
  - Result: 2 test targets passed from the populated persistent cache, with `24 action cache hit`, `(cached) PASSED`, and `Executed 0 out of 2 tests`.
- Second run: `./bazelw test //... --test_output=errors`
  - Result: 2 test targets passed again from the persistent cache, with `24 action cache hit`, `(cached) PASSED`, and `Executed 0 out of 2 tests`.
- Cache no-download check: `./bazelw test --repository_disable_download //... --test_output=errors`
  - Result: 2 test targets passed from the populated persistent cache, with `24 action cache hit`, `(cached) PASSED`, and `Executed 0 out of 2 tests`.
- `python3 experiments/waymo-perception/tools/pins.py check --base work/semantic-layout/integration`
  - Result: `PASS: 0 changed file(s) cited by retained receipts`.

Pinned files changed and why:

- None. No protected Python files under `experiments/waymo-perception/{pipeline,gpu,tier1,cohort,resources}` were changed.

Reviewer notes:

- The rootfs network is shared with the host network namespace; the wrapper does not use `--unshare-net`. `/etc/resolv.conf` is mounted read-only because `rootfs-v3`'s resolver file is empty.
- Bazel prints an OpenJDK deprecation warning from the rootfs JVM on every invocation; the tests and build targets passed despite that environment warning.
