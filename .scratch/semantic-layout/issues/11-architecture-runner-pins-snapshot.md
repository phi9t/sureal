# 11: The architecture runner pins a source snapshot

**What to build:** A researcher runs an architecture experiment and its receipts pin a source snapshot taken by the evidence module. Verifying the run checks the snapshot, not the working tree. This is the first real gate on the new evidence model.

**Blocked by:** 09 (Evidence module: snapshot, fetch and verify)

**Status:** ready-for-agent

- [x] A new run records the snapshot digest and the build target it was taken from
- [x] Verifying and resuming a run check the recorded snapshot and succeed after an unrelated source file is edited
- [x] Verifying fails when the snapshot's bytes differ from the recorded digest
- [x] Verification without a run identifier, which compared tracked receipts with the working tree, is removed and the user guide says so
- [x] The runner's own freezing code is replaced by the evidence module
- [x] Receipts of earlier runs are unchanged

## Comments

Built:

- Added `//autonomy:architecture_experiment_runner_snapshot`, a Bazel-declared source closure for the architecture runner, harness drivers, GPU/pipeline workers, evidence snapshot module, and the retained research inputs the harness reads.
- Replaced `architecture/experiment_runner.py`'s local source-copy hash freeze with `evidence.source_snapshot.snapshot_bazel_target`, `LocalSnapshotStore`, and `verify_receipt_sources`.
- New architecture runs now write `source_snapshot_sha256`, `source_snapshot_target`, `source_snapshot_bytes`, and `source_pins` in `run.json`.
- New stage receipts are annotated with the same `source_snapshot_sha256`, `source_snapshot_target`, and `source_pins` before admission verification. If a stage receipt exists from an interrupted run before annotation, resume pins it from `run.json` before skip verification.
- `check_snapshot`, resume, `verify --run-id`, and `summarize` verify the recorded snapshot through the evidence module, not the working tree.
- Retired `architecture.py verify <experiment>` without `--run-id`; the architecture guide now documents that the legacy working-tree comparison mode is gone.
- Preserved earlier receipts by not editing any file under `autonomy/research/`.

Verification:

- Red test before implementation: `./bazelw test //autonomy:architecture__test_experiment_runner --test_output=errors --cache_test_results=no` -> failed as expected with missing `source_snapshot_sha256`, `check_snapshot` still reading `source_sha256`, no runner `LocalSnapshotStore`, and no-run-id verify still reaching legacy working-tree receipt checks.
- Red test for interrupted stage-receipt resume repair: `./bazelw test //autonomy:architecture__test_experiment_runner --test_filter=RunnerTests.test_existing_stage_receipt_is_pinned_before_resume_skip_verifies_it --test_output=errors --cache_test_results=no` -> failed as expected with `receipt source snapshot digest required`.
- `./bazelw test //autonomy:architecture__test_experiment_runner --test_output=errors --cache_test_results=no` -> `Executed 1 out of 1 test: 1 test passes.`
- `./bazelw query --output=label 'kind("source file", filter("^//", labels("srcs", deps(//autonomy:architecture_experiment_runner_snapshot)) union labels("data", deps(//autonomy:architecture_experiment_runner_snapshot))))'` -> printed the architecture runner/harness, evidence snapshot module, GPU/pipeline workers, and the declared retained research inputs; no root `BUILD.bazel` package was added.
- Temporary local-store smoke: `snapshot_bazel_target('//autonomy:architecture_experiment_runner_snapshot', LocalSnapshotStore($tmp))` then `verify_receipt_sources(...)` -> `target=//autonomy:architecture_experiment_runner_snapshot`, `digest=fc8e8d64dc42f893e89a8f520149f58cf2aa297b03777f1dfc8d1948b81ad4be`, `archive_bytes=849920`, `source_files=186`, `has_runner=True`, `has_doc=False`, `study_spec_sha256=fef072b2737a4fda94a029944fb999d78be482669b1cd989af953d93b5e7ecf1`.
- `./bazelw test //autonomy/... --cache_test_results=no` -> `Executed 139 out of 139 tests: 139 tests pass.`
- `python3 autonomy/tools/pins.py check --base work/semantic-layout/integration` -> `PASS: 0 changed file(s) cited by retained receipts`.
- `git diff --check` -> passed.
- `find . -path './.bazel-cache' -prune -o -name BUILD.bazel -print | sort` -> only `./autonomy/BUILD.bazel` and `./parallax/BUILD.bazel`.

Reviewer notes:

- The requested legacy pin command path under `experiments/waymo-perception/tools/pins.py` no longer exists after ticket 07's rename, so I used `python3 autonomy/tools/pins.py check --base work/semantic-layout/integration`.
- Pinned files changed: none. The pin guard reported `0 changed file(s) cited by retained receipts`, and this ticket did not edit the protected legacy `experiments/waymo-perception/{pipeline,gpu,tier1,cohort,resources}` inventory.
- The dated study spec remains in `docs/`; to keep Bazel package boundaries only under `autonomy/` and `parallax/`, the runner source pins the current study-spec digest as a constant instead of adding a root or docs Bazel package.
