# 02: One wrapper command runs Bazel inside Insula

**What to build:** A contributor types one repository-level wrapper command and a Bazel test of one existing perception unit test runs inside the new CPU rootfs and passes. The wrapper is the only entry point: it verifies the rootfs, enters the sandbox, and runs Bazel with persistent caches. This ticket also settles which Bazel spawn strategy and server mode work when nested inside the Insula sandbox.

**Blocked by:** 01 (A new version of the CPU rootfs carries Bazel 9.2)

**Status:** ready-for-agent

- [ ] The repository root has the Bazel module file, its committed lock file, the Bazel version file and the Bazel configuration; packages are declared only for the two research programs
- [ ] The Python toolchain is the rootfs interpreter with its installed packages; Bazel fetches no third-party Python package
- [ ] The wrapper clears the environment, sets a fixed home, mounts the rootfs read-only, and mounts the repository and one git-ignored cache directory that is also listed in the Bazel ignore file
- [x] A second run of the same test is served from the persistent cache
- [x] The wrapper has a mode that prints the sandbox command as data without running it, covered by a unit test
- [x] The wrapper refuses to run, with a clear message, when the rootfs does not match its lock; covered by a unit test
- [x] The working spawn strategy and server mode are recorded in the Bazel configuration with a one-line reason each
- [x] Network is available inside the sandbox during the build

## Comments

Built:

- Added repository-level `bazelw`. It verifies `~/.cache/waystone/waymo-perception/insula/rootfs-v3` against `rootfs-v3.lock.json`, checks Bazel 9.2.0 in the lock, emits a JSON sandbox plan with `--emit-plan`, or executes Bazel through `bwrap`.
- Added root Bazel files: `MODULE.bazel`, committed `MODULE.bazel.lock`, `.bazelversion`, `.bazelrc`, `.bazelignore`, and `WORKSPACE`.
- Added `.bazel-cache/` to `.gitignore` and `.bazelignore`; the wrapper mounts it at `/outputs` and uses it for `--output_base`, `--repository_cache`, `--disk_cache`, and fixed `HOME=/outputs/home`.
- Added package declarations only under `experiments/3d-pathway/` and `experiments/waymo-perception/`. The current Bazel graph exposes one perception target: `//experiments/waymo-perception:tools_test_suites`.
- Added a small in-repo Starlark unit-test rule that runs `/usr/local/bin/python` from the rootfs directly. The committed Bazel sources do not declare `rules_python`, `pip_parse`, PyPI, requirements, or wheel configuration.
- Recorded the working Bazel modes in `.bazelrc`: `startup --batch` because no Bazel server has to survive the Insula process namespace, and `standalone` spawn/test strategy because `linux-sandbox` is not registered inside `rootfs-v3`.
- The wrapper passes `--enable_workspace --noenable_bzlmod --repositories_without_autoloads=*` for this initial in-repo one-test gate. `MODULE.bazel` and `MODULE.bazel.lock` are present for the repository contract, but this target intentionally avoids external Python-package resolution.

Verification commands and results:

- Red test before implementation: `PYTHONPATH=experiments/waymo-perception python3 -m unittest experiments.waymo-perception.tests.test_bazel_wrapper -v`
  - Result: 2 failures, both reporting `repository-level Bazel wrapper is missing`.
- Red test for the workspace-mode follow-up: `PYTHONPATH=experiments/waymo-perception python3 -m unittest experiments.waymo-perception.tests.test_bazel_wrapper -v`
  - Result: 1 failure, `--enable_workspace` missing from the emitted Bazel command.
- `PYTHONPATH=experiments/waymo-perception python3 -m unittest experiments.waymo-perception.tests.test_bazel_wrapper experiments.waymo-perception.tests.test_runtime_identity experiments.waymo-perception.tests.test_insula_entry experiments.waymo-perception.tests.test_cpu_rootfs_build -v`
  - Result: 8 tests, 0 failures.
- `find . -path './.bazel-cache' -prune -o -name BUILD.bazel -print | sort`
  - Result: only `./experiments/3d-pathway/BUILD.bazel` and `./experiments/waymo-perception/BUILD.bazel`.
- `./bazelw query //...`
  - Result: only `//experiments/waymo-perception:tools_test_suites`.
- `./bazelw --emit-plan test //experiments/waymo-perception:tools_test_suites`
  - Result: JSON plan starts with `bwrap`, contains `--clearenv`, fixed `HOME=/outputs/home`, read-only rootfs and repository mounts, `/etc/resolv.conf` mounted read-only, `.bazel-cache` mounted at `/outputs`, and Bazel cache flags under `/outputs`.
- Network probe using the emitted wrapper plan: `python3 - <<'PY' ... socket.create_connection(("bcr.bazel.build", 443), timeout=8) ... PY`
  - Result: `network-ok`.
- `./bazelw --cache .bazel-cache/final-02-20261005T0714Z test //... --test_output=errors`
  - Result: 1 target, `//experiments/waymo-perception:tools_test_suites`, passed; `Executed 1 out of 1 test`.
- Second run: `./bazelw --cache .bazel-cache/final-02-20261005T0714Z test //... --test_output=errors`
  - Result: same target passed from cache; output included `6 action cache hit`, `(cached) PASSED`, and `Executed 0 out of 1 test`.
- Cache no-download check: `./bazelw --cache .bazel-cache/final-02-20261005T0714Z test --experimental_repository_disable_download //... --test_output=errors`
  - Result: same target passed from the populated persistent cache; output included `6 action cache hit`, `(cached) PASSED`, and `Executed 0 out of 1 test`.
- `rg -n "rules_python|pip_parse|pythonhosted|requirements|whl_" MODULE.bazel .bazelrc experiments/waymo-perception/BUILD.bazel experiments/waymo-perception/bazel_unittest.bzl bazelw || true`
  - Result: no matches.
- `python3 experiments/waymo-perception/tools/pins.py check --base work/semantic-layout/integration`
  - Result: `PASS: 0 changed file(s) cited by retained receipts`.

Pinned files changed and why:

- None. No protected Python files under `experiments/waymo-perception/{pipeline,gpu,tier1,cohort,resources}` were changed.

Reviewer notes:

- The rootfs network is shared with the host network namespace; the wrapper does not use `--unshare-net`. `/etc/resolv.conf` is mounted read-only because `rootfs-v3`'s resolver file is empty.
- Bazel 9 still initializes built-in external rule repositories in its output base even for this custom in-repo test rule. This work does not configure Bazel to fetch third-party Python packages, and the checked-in module lock does not record Python-package repositories.
