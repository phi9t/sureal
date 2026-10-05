# 01: A new version of the CPU rootfs carries Bazel 9.2

**What to build:** A contributor can build a new version of the perception CPU rootfs that contains Bazel 9.2 alongside the same Python packages as the current image. The current image stays on disk untouched, so past receipts still find the digest they recorded.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] The new rootfs is built from the existing image definition and the existing hash-pinned requirement lock, plus a checksum-verified Bazel 9.2 binary
- [x] The rootfs lock records the new image identity and the Bazel version and checksum
- [x] Inside the new rootfs, `bazel --version` reports 9.2 and the installed Python packages match the current image's package list exactly
- [x] The previous rootfs directory and its lock are byte-identical before and after the build
- [x] Every check that compares a runtime lock with the previous rootfs digest is listed in the ticket's comments, for re-admission later

## Comments

Built:

- `experiments/waymo-perception/insula/Dockerfile` now installs Bazel 9.2.0 from the Bazel release binary and verifies SHA-256 `7668a95db1250f12c40407251e4e203b4ec8bf39bc495d2f485b2d8c99048694` before making it executable.
- `experiments/waymo-perception/build.sh` now defaults to a new versioned destination, `~/.cache/waystone/waymo-perception/insula/rootfs-v3`, refuses to replace any existing destination or lock, validates Bazel and Python package parity through `bwrap`, preserves the previous rootfs and lock, and records Bazel metadata in `rootfs-v3.lock.json`.
- Added `experiments/waymo-perception/tests/test_cpu_rootfs_build.py` to test the build entrypoint with fake Docker, tar and bwrap tools. The tests first failed against the old behavior, then passed after the implementation.

New rootfs artifacts:

- Rootfs: `/data02/home/philip.yang/.cache/waystone/waymo-perception/insula/rootfs-v3`
- Lock: `/data02/home/philip.yang/.cache/waystone/waymo-perception/insula/rootfs-v3.lock.json`
- New rootfs identity: `2393eb27861a802e21a91a401eb69c43aa6b8238900e197d26d16d89e7599ddd`
- Image identity recorded in the lock: `sha256:2853fcb417e97400f3526b1d9e49fa88cac2bd0a5df71e00f480d1f3d6de859f`

Verification commands and results:

- `PYTHONPATH=experiments/waymo-perception python3 -m unittest experiments.waymo-perception.tests.test_cpu_rootfs_build -v`
  - Red result before implementation: 2 failures. The old script refused to replace `rootfs-v2`, and package inventory drift was not rejected.
  - Green result after implementation: 2 tests, 0 failures.
- `PYTHONPATH=experiments/waymo-perception python3 -m unittest experiments.waymo-perception.tests.test_runtime_identity experiments.waymo-perception.tests.test_insula_entry experiments.waymo-perception.tests.test_cpu_rootfs_build -v`
  - Result: 6 tests, 0 failures.
- `experiments/waymo-perception/build.sh`
  - Result: built Docker image `sureal-waymo-cpu:bazel-9.2.0`, installed Bazel 9.2.0, exported `rootfs-v3`, and wrote `rootfs-v3.lock.json`.
- Independent rootfs lock verification:
  - `rootfs-v2` actual identity `aa18eaaca3c65821d1febcbafefa9d0d0a2a6dae03aa9bc55c7d9e19e769246e` matched its lock.
  - `rootfs-v3` actual identity `2393eb27861a802e21a91a401eb69c43aa6b8238900e197d26d16d89e7599ddd` matched its lock.
  - `rootfs-v3.lock.json` records `bazel_version: "9.2.0"` and `bazel_linux_x86_64_sha256: "7668a95db1250f12c40407251e4e203b4ec8bf39bc495d2f485b2d8c99048694"`.
- `bwrap --ro-bind /data02/home/philip.yang/.cache/waystone/waymo-perception/insula/rootfs-v3 / ... -- bazel --version`
  - Result: `bazel 9.2.0`.
- `bwrap ... rootfs-v2 ... -- python -m pip freeze --all | sort` and `bwrap ... rootfs-v3 ... -- python -m pip freeze --all | sort`, then `cmp -s`
  - Result: package inventory match, 10 lines.
- Previous rootfs preservation:
  - Before build, `rootfs-v2` identity was `aa18eaaca3c65821d1febcbafefa9d0d0a2a6dae03aa9bc55c7d9e19e769246e`.
  - After build, `rootfs-v2` identity remained `aa18eaaca3c65821d1febcbafefa9d0d0a2a6dae03aa9bc55c7d9e19e769246e`.
  - Before and after, `rootfs-v2.lock.json` SHA-256 remained `a8cc19c5f448b5b54cb4f09f0991688be1fe74a748387feb1a6bb99a52137030`.
- `python3 experiments/waymo-perception/tools/pins.py check --base work/semantic-layout/integration`
  - Result: `FAIL: 2 changed file(s) cited by retained receipts`.
  - Pinned files changed and why:
    - `build.sh`: cited by 4 retained receipts. Changed because this ticket changes the CPU rootfs build entrypoint to create the new Bazel-bearing rootfs version instead of `rootfs-v2`.
    - `insula/Dockerfile`: cited by 745 retained receipts. Changed because this ticket bakes checksum-verified Bazel 9.2.0 into the CPU rootfs image definition.
  - No protected Python files under `pipeline`, `gpu`, `tier1`, `cohort` or `resources` were changed.
- `PYTHONPATH=experiments/waymo-perception python3 -m unittest discover -s experiments/waymo-perception/tests -p 'test_*.py' -v`
  - Result: failed on the host with 190 discovered tests, 5 failures and 98 errors.
  - Main failure classes: missing host Python packages that live in the rootfs (`numpy`, `pyarrow`), missing upstream Waymo protobuf sources under `/upstream/src`, and one direct-I/O staging case rejected by the host filesystem with `OSError: [Errno 22] Invalid argument`.
  - The new rootfs ticket tests themselves passed inside this run.

Checks that compare a runtime lock or previous rootfs digest and need re-admission later:

- Rootfs-v2 path consumers found by `rg -l "rootfs-v2" experiments/waymo-perception docs .scratch --glob '!**/research/**' --glob '!docs/research/**' --glob '!**/__pycache__/**'`:
  - `docs/superpowers/plans/2026-10-03-balanced16-sustained-overfit.md`
  - `experiments/waymo-perception/advanced/prepare.py`
  - `experiments/waymo-perception/advanced/prepare_range.py`
  - `experiments/waymo-perception/advanced/publish.py`
  - `experiments/waymo-perception/advanced/run.py`
  - `experiments/waymo-perception/architecture/experiment_runner.py`
  - `experiments/waymo-perception/architecture/harness/audit-all-pillars-score-first.py`
  - `experiments/waymo-perception/architecture/harness/audit-architecture-score-first.py`
  - `experiments/waymo-perception/architecture/harness/audit-followup-score-first.py`
  - `experiments/waymo-perception/architecture/harness/audit-retain64-score-first.py`
  - `experiments/waymo-perception/architecture/harness/run-all-pillars-loss-audit.py`
  - `experiments/waymo-perception/architecture/harness/run-architecture-loss-audit.py`
  - `experiments/waymo-perception/architecture/harness/run-followup-loss-audit.py`
  - `experiments/waymo-perception/architecture/harness/run-retain64-loss-audit.py`
  - `experiments/waymo-perception/architecture/harness/score-all-pillars-score-first.py`
  - `experiments/waymo-perception/architecture/harness/score-architecture-score-first.py`
  - `experiments/waymo-perception/architecture/harness/score-followup-score-first.py`
  - `experiments/waymo-perception/architecture/harness/score-retain64-score-first.py`
  - `experiments/waymo-perception/build.sh`
  - `experiments/waymo-perception/cohort/prepare_balanced_native.py`
  - `experiments/waymo-perception/cohort/prepare_labels.py`
  - `experiments/waymo-perception/cohort/publish_native_cache.py`
  - `experiments/waymo-perception/cohort/publish_sustained_checkpoint.py`
  - `experiments/waymo-perception/cohort/publish_sustained_pilot.py`
  - `experiments/waymo-perception/cohort/re_admit_physical.py`
  - `experiments/waymo-perception/cohort/reconstruct.py`
  - `experiments/waymo-perception/cohort/run.py`
  - `experiments/waymo-perception/cohort/run_balanced.py`
  - `experiments/waymo-perception/cohort/scan.py`
  - `experiments/waymo-perception/cohort/score.py`
  - `experiments/waymo-perception/cohort/score_balanced.py`
  - `experiments/waymo-perception/cohort/score_parallel.py`
  - `experiments/waymo-perception/cohort/score_v2.py`
  - `experiments/waymo-perception/cohort/verify_coverage.py`
  - `experiments/waymo-perception/cohort/verify_labels.py`
  - `experiments/waymo-perception/cohort/verify_labels_v3.py`
  - `experiments/waymo-perception/evaluation/audit-perception-gate.py`
  - `experiments/waymo-perception/evaluation/verify-real-semantic-export.py`
  - `experiments/waymo-perception/inspect-scene.py`
  - `experiments/waymo-perception/pipeline/insula_entry.py`
  - `experiments/waymo-perception/pipeline/semantic_recovery_job.py`
  - `experiments/waymo-perception/pipeline/semantic_recovery_job_aligned.py`
  - `experiments/waymo-perception/pipeline/training_box_replay.py`
  - `experiments/waymo-perception/process-scientific-cohort.py`
  - `experiments/waymo-perception/publish-scientific-camera.py`
  - `experiments/waymo-perception/publish-scientific-scene.py`
  - `experiments/waymo-perception/publish-scientific-sidecars-bounded.py`
  - `experiments/waymo-perception/publish-scientific-sidecars-compressed.py`
  - `experiments/waymo-perception/publish-scientific-sidecars.py`
  - `experiments/waymo-perception/resources/retention.py`
  - `experiments/waymo-perception/scientific-camera-preprocess.py`
  - `experiments/waymo-perception/scientific-preprocess.py`
  - `experiments/waymo-perception/scripts/replay-motion-foundation.py`
  - `experiments/waymo-perception/tests/test_cpu_rootfs_build.py`
  - `experiments/waymo-perception/tests/test_m0_receipt.py`
  - `experiments/waymo-perception/tier1/prepare.py`
  - `experiments/waymo-perception/tier1/rescore_heading.py`
  - `experiments/waymo-perception/tier1/run.py`
  - `experiments/waymo-perception/verify-archive-dataset.py`
  - `experiments/waymo-perception/verify-camera-replay.py`
  - `experiments/waymo-perception/verify-geometry.py`
  - `experiments/waymo-perception/verify-m0.py`
  - `experiments/waymo-perception/verify-motion-cli-expanded.py`
  - `experiments/waymo-perception/verify-native.py`
  - `experiments/waymo-perception/verify-reconstruction.py`
  - `experiments/waymo-perception/verify-scientific-replay.py`
  - `experiments/waymo-perception/verify-scientific-scene.py`
- Runtime-lock equality/admission checks that compare a saved runtime lock with a current or expected runtime identity and should be re-admitted when their CPU runtime moves from `rootfs-v2` to `rootfs-v3`:
  - `experiments/waymo-perception/pipeline/m0_receipt.py`
  - `experiments/waymo-perception/pipeline/cohort_checkpoint.py`
  - `experiments/waymo-perception/pipeline/r0_compare.py`
  - `experiments/waymo-perception/pipeline/semantic_recovery_receipt.py`
  - `experiments/waymo-perception/pipeline/semantic_recovery_receipt_aligned.py`
  - `experiments/waymo-perception/pipeline/training_box_replay.py`
  - `experiments/waymo-perception/pipeline/training_box_replay_audit.py`
  - `experiments/waymo-perception/cohort/audit_sustained_transition.py`
  - `experiments/waymo-perception/cohort/replay_sustained.py`
  - `experiments/waymo-perception/cohort/sustained_controller_backend.py`
  - `experiments/waymo-perception/cohort/sustained_sources.py`
  - `experiments/waymo-perception/cohort/train_sustained.py`
  - `experiments/waymo-perception/process-scientific-cohort.py`
  - `experiments/waymo-perception/scientific-camera-preprocess.py`
  - `experiments/waymo-perception/scientific-preprocess.py`
  - `experiments/waymo-perception/tests/test_m0_receipt.py`
