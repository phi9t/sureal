# 05: The curriculum's tests run under Bazel, in place

**What to build:** A contributor runs one wrapper command and the 3D reconstruction curriculum's CPU numerical contract passes as Bazel targets, with the tree where it is now. This ticket decides whether the curriculum can share the perception CPU rootfs or needs a rootfs of its own.

**Blocked by:** 02 (One wrapper command runs Bazel inside Insula)

**Status:** done

- [x] The curriculum's 17 test modules are Bazel test targets
- [x] The CPU numerical contract passes through the wrapper, or the ticket records exactly which tests fail under Python 3.12 and the newer NumPy
- [x] If it cannot share the perception rootfs, a curriculum rootfs with Bazel 9.2 is built from a hash-pinned lock and the wrapper selects it for curriculum targets
- [x] Tests that require a real container gate stay opt-in and are excluded by default
- [x] The existing CI job for the curriculum still passes unchanged

## Comments

Built:

- Added Bazel targets for all 17 existing `experiments/3d-pathway/tests/test_*.py` modules.
- Kept real container/B200 reference tests opt-in through their existing environment gates; default Bazel and unittest discovery skip those gates.
- Fixed `experiments/3d-pathway/run.sh` so subprocess calls work under Bazel's safe-path Python bootstrap without relying on implicit script-directory imports.
- Added a curriculum Bazel rootfs recipe under `experiments/3d-pathway/insulas/`, with Bazel 9.2.0, Python 3.10, Git, and hash-pinned NumPy 1.26.4.
- Built the versioned rootfs at `/data02/home/philip.yang/.cache/waystone/3d-pathway/insula/rootfs-v1` with lock `/data02/home/philip.yang/.cache/waystone/3d-pathway/insula/rootfs-v1.lock.json`; the wrapper verifies this lock before entering bwrap and selects it for `//experiments/3d-pathway...` targets.
- Kept the existing curriculum CI job command in `.github/workflows/publication.yml` unchanged.

Verification:

- `./bazelw test --nocache_test_results //experiments/3d-pathway/...` -> `Executed 17 out of 17 tests: 17 tests pass.`
- `PYTHONPATH=experiments/waymo-perception python3 -m unittest experiments.waymo-perception.tests.test_bazel_wrapper -v` -> `Ran 4 tests in 0.245s`, `OK`.
- `bwrap --unshare-user --unshare-pid --unshare-ipc --unshare-uts --die-with-parent --ro-bind "$HOME/.cache/waystone/3d-pathway/insula/rootfs-v1" / --ro-bind /etc/resolv.conf /etc/resolv.conf --ro-bind "$PWD" /experiment --bind "$PWD/.bazel-cache" /outputs --proc /proc --dev /dev --tmpfs /tmp --clearenv --setenv HOME /outputs/home --setenv USER sureal --setenv LOGNAME sureal --setenv PATH /usr/local/bin:/usr/bin:/bin --setenv TMPDIR /tmp --setenv PYTHONNOUSERSITE 1 --setenv PYTHONDONTWRITEBYTECODE 1 --chdir /experiment -- env PYTHONPATH=experiments/3d-pathway python -m unittest discover -s experiments/3d-pathway/tests -p 'test_*.py' -v` -> `Ran 209 tests in 373.835s`, `OK (skipped=10)`.
- `python3 experiments/waymo-perception/tools/pins.py check --base work/semantic-layout/integration` -> `PASS: 0 changed file(s) cited by retained receipts`.
- `git diff --check` -> exit 0, no output.

Pinned files changed:

- None. No `.py` files under `experiments/waymo-perception/{pipeline,gpu,tier1,cohort,resources}` were added, changed, or removed.

Reviewer notes:

- The perception rootfs could not run the full curriculum suite because `test_foundation_geometry_reference` requires Git. The curriculum rootfs exists to keep that tool dependency explicit without changing the perception rootfs.
- Host-only `PYTHONPATH=experiments/3d-pathway python3 -m unittest discover -s experiments/3d-pathway/tests -p 'test_*.py' -v` is not a valid verification on this host because host Python 3.14 does not provide the pinned NumPy dependency; the unchanged command shape passed inside the curriculum rootfs above.
