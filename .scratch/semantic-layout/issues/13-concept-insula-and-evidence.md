# 13: Concept batch: `insula` and `evidence`

**What to build:** Sandbox entry and the evidence tooling live in their concept directories. A contributor finds the Insula launcher, rootfs identity checks and the first-milestone probes under `insula`, and the journal, tracker and snapshot code under `evidence`.

**Blocked by:** 11 (The architecture runner pins a source snapshot), 12 (The sustained-run guard verifies a snapshot)

**Status:** ready-for-agent

- [x] Scope: the Insula entry and launch plan, rootfs identity, the M0 probe and receipt code, staging leases; the research journal, tracker, projection and publication; the pin report tool
- [x] The wrapper and the live-gate launcher share one sandbox-plan implementation
- [x] Every module in scope lives in its concept directory and is imported by package path; no `sys.path` manipulation remains in the moved code
- [x] Each moved test sits beside its module as `foo_test.py` and is a Bazel test target
- [x] Bazel visibility lets only the concepts above this one depend on it
- [x] File digests and regular-file checks in the moved code come from the evidence module, not local copies
- [x] The same test modules pass through the wrapper as before the batch, and the pin report for the batch is attached to the ticket
- [x] Files under `research/` are unchanged

## Comments

Built:

- Added concept-local Bazel packages for `autonomy/insula` and `autonomy/evidence` with explicit visibility to the concepts above them.
- Moved the Insula entrypoint, runtime identity checks, M0 probe/receipt/validator, staging lease, and their tests under `autonomy/insula`.
- Moved the research journal, tracker, projection, publication, pin report implementation, source-integrity checks, and their tests under `autonomy/evidence`.
- Added `autonomy/insula/sandbox_plan.py`; `bazelw` and the live-gate launcher now compose their bwrap arguments through that shared implementation.
- Kept the required `autonomy/tools/pins.py` command as a compatibility wrapper around `evidence.pins`.
- Updated non-research callers and Bazel source-snapshot targets to import/use `insula.*` and `evidence.*` package paths instead of old `pipeline/*` and `tracking/*` locations.
- Moved digest and regular-file policy in the moved code onto `evidence.source_snapshot.file_sha256` and `require_regular_file`.

Verification:

- `./bazelw test //autonomy/... --test_output=errors --cache_test_results=no` -> `Executed 150 out of 150 tests: 150 tests pass.`
- `./bazelw test //autonomy/insula:m0_receipt_test --test_output=errors --cache_test_results=no --test_tag_filters=requires_live_gate` -> `Executed 1 out of 1 test: 1 test passes.`
- `./bazelw test //parallax/... --test_output=errors --cache_test_results=no` -> `Executed 17 out of 17 tests: 17 tests pass.`
- `python3 autonomy/tools/layers.py` -> `PASS: 0 layering problem(s) across 12 layers`.
- `git diff --check` -> exit 0, no output.
- `git diff --name-only work/semantic-layout/integration..HEAD -- 'autonomy/research/**' 'parallax/research/**' 'research/**'` -> no output.
- `python3 autonomy/tools/pins.py check --base work/semantic-layout/integration` -> exit 1 with `FAIL: 86 changed file(s) pinned by retained receipts`.

Pin report:

The pin guard reports retained historical receipts affected by this intentional concept move. The 86 changed retained-receipt-pinned paths/renames are:

```text
acquire-scientific-cohort.py
advanced/admit.py
advanced/close.py
advanced/prepare.py
advanced/prepare_range.py
advanced/publish.py
advanced/run.py
cohort/prepare_balanced_native.py
cohort/prepare_labels.py
cohort/reconstruct.py
cohort/scan.py
cohort/verify_coverage.py
cohort/verify_labels.py
cohort/verify_labels_v3.py
enter.sh
evaluation/audit-perception-gate.py
evaluation/verify-detection-adapter.py
evaluation/verify-detection-contract.py
evaluation/verify-native-metrics.py
evaluation/verify-real-detection-export.py
evaluation/verify-real-semantic-export.py
evaluation/verify-segmentation-contract.py
evaluation/verify-segmentation-export.py
gpu/verify-isolation.py
gpu/verify-live.py
inspect-scene.py
pipeline/insula_entry.py -> insula/entry.py
pipeline/m0_probe.py -> insula/m0_probe.py
pipeline/m0_receipt.py -> insula/m0_receipt.py
pipeline/m0_validate.py -> insula/m0_validate.py
pipeline/native_range_shape_reference.py
pipeline/native_shape_source_replay.py
pipeline/runtime_identity.py -> insula/runtime_identity.py
pipeline/semantic_recovery_job.py
pipeline/semantic_recovery_job_aligned.py
pipeline/source_integrity.py -> evidence/source_integrity.py
pipeline/staged_derived_archive.py
pipeline/staged_derived_archive_aligned.py
pipeline/staged_source.py
pipeline/staging_lease.py -> insula/staging_lease.py
pipeline/training_box_replay.py
process-scientific-cohort.py
publish-scientific-camera.py
publish-scientific-scene.py
publish-scientific-sidecars-bounded.py
publish-scientific-sidecars-compressed.py
publish-scientific-sidecars.py
scientific-camera-preprocess.py
scientific-preprocess.py
scripts/recover-sustained-pilot-scoring-long.py
scripts/recover-sustained-pilot-scoring.py
scripts/replay-motion-foundation.py
scripts/run-expanded-matrix.py
tests/test_insula_entry.py -> insula/entry_test.py
tests/test_m0_receipt.py -> insula/m0_receipt_test.py
tests/test_native_shape_staging_deadline.py
tests/test_runtime_identity.py -> insula/runtime_identity_test.py
tests/test_semantic_recovery_job.py
tests/test_source_integrity.py -> evidence/source_integrity_test.py
tests/test_staged_derived_archive.py
tests/test_staged_derived_archive_aligned.py
tests/test_staging_lease.py -> insula/staging_lease_test.py
tests/test_training_box_replay.py
tier1/prepare.py
tier1/rescore_heading.py
tier1/run.py
tools/pins.py
tools/test_pins.py -> evidence/pins_test.py
tracking/journal.py -> evidence/journal.py
tracking/live_contract.py -> evidence/live_contract.py
tracking/projection.py -> evidence/projection.py
tracking/publish.py -> evidence/publish.py
tracking/test_journal.py -> evidence/journal_test.py
tracking/test_projection.py -> evidence/projection_test.py
tracking/test_publish.py -> evidence/publish_test.py
verify-archive-dataset.py
verify-camera-replay.py
verify-geometry.py
verify-m0.py
verify-motion-cli-expanded.py
verify-motion-cli.py
verify-motion-native.py
verify-native.py
verify-reconstruction.py
verify-scientific-replay.py
verify-scientific-scene.py
```

Pinned/guarded file reasons:

- The old `pipeline/insula_entry.py`, `pipeline/runtime_identity.py`, `pipeline/m0_probe.py`, `pipeline/m0_receipt.py`, `pipeline/m0_validate.py`, and `pipeline/staging_lease.py` paths were moved to `autonomy/insula`; their old retained-receipt paths show up as changed because the receipts are historical.
- The old `pipeline/source_integrity.py`, `tracking/*`, `tools/pins.py`, and moved tests were moved or wrapped by `autonomy/evidence` so evidence behavior lives in the evidence concept.
- Active pipeline files were updated only to import `evidence.source_integrity`, `insula.entry`, `insula.runtime_identity`, and `insula.staging_lease`, and to keep source pins valid after the concept move.
- Guarded `.py` files under `autonomy/gpu`, `autonomy/tier1`, `autonomy/cohort`, and `autonomy/resources` were changed only for import/path compatibility or source-closure lists required by the moved `insula` and `evidence` packages.
- Top-level, `advanced`, `evaluation`, and `scripts` callers were changed only to reference the new package paths and moved module locations.

Reviewer notes:

- No file under any `research/` directory was modified.
- `bazelw` uses one launcher-local `sys.path.insert(0, str(AUTONOMY))` before normal `insula` imports, as requested in review 1. The no-`sys.path` rule remains enforced for moved library/test code inside the build graph. The live-gate worker plan still sets `PYTHONPATH=/experiment` for worker repository imports.
- The retained receipts are left untouched as historical evidence under the source-pin ADR.

Review 1 follow-up:

- Added `py_library` exports `//autonomy/evidence:evidence` and `//autonomy/insula:insula`; concept tests and the root bridge tests now use library deps for Python imports. Filegroups remain only for source-snapshot/file-data consumers.
- Deleted `autonomy/evidence/concept_layout_test.py` and `autonomy/insula/concept_layout_test.py`. The live-gate/shared-plan behavioral check now lives in `autonomy/insula/entry_test.py`.
- Removed `evidence.journal.digest`; journal, tracker, and publisher digest paths use `evidence.source_snapshot.file_sha256`.
- Replaced the wrapper's synthetic package registration with one launcher-local `autonomy/` path insertion and normal imports. The compatibility `autonomy/tools/pins.py` wrapper follows the same entrypoint pattern.
- Made `evidence.pins.changed` rename-aware using `git diff -M20% --name-status -z`, hashing the base-revision old path and reporting moved pinned files as `old -> new`.
- Added pin tests for deleted pinned files, pure pinned moves, pinned move plus edit, unpinned moves, and whole-package-directory renames.

Review 1 verification:

- `./bazelw test //autonomy/evidence:pins_test --test_output=errors --cache_test_results=no` -> `Executed 1 out of 1 test: 1 test passes.`
- `./bazelw test //autonomy/evidence:all //autonomy/insula:all //autonomy:source_snapshot_targets_test //autonomy:tests__test_bazel_wrapper --test_output=errors --cache_test_results=no` -> `Executed 12 out of 12 tests: 12 tests pass.`
- `./bazelw test //autonomy/... --test_output=errors --cache_test_results=no` -> `Executed 148 out of 148 tests: 148 tests pass.`
- `./bazelw test --config=cuda --test_tag_filters=requires_gpu,-requires_live_gate,-requires_host_tools,-requires_pytest,-known_failure //autonomy/... --test_output=errors --cache_test_results=no` -> `Executed 24 out of 24 tests: 24 tests pass.`
- `./bazelw test //parallax/... --test_output=errors --cache_test_results=no` -> `Executed 17 out of 17 tests: 17 tests pass.`
- `python3 autonomy/tools/layers.py` -> `PASS: 0 layering problem(s) across 12 layers`.
- `git diff --check` -> exit 0, no output.
- `git diff --name-only work/semantic-layout/integration..HEAD -- 'autonomy/research/**' 'parallax/research/**' 'research/**'` -> no output.
- `python3 autonomy/tools/pins.py check --base work/semantic-layout/integration` -> exit 1 with `FAIL: 86 changed file(s) pinned by retained receipts`; moved pinned files are now reported with `old -> new` paths.

Review 2 follow-up:

- Fixed the living-document link in `autonomy/research-task-index.md` from the moved `tracking/README.md` path to `evidence/README.md`.
- Removed the stale `tracking/` area from `autonomy/ARCHITECTURE.md`; evidence tooling is now documented under the `evidence/` layer.
- Searched living Markdown for stale moved paths named by the review, excluding retained `research/` and dated spec/plan directories. No `tracking/` path or moved `pipeline/insula_entry`, `pipeline/runtime_identity`, `pipeline/m0_*`, `pipeline/staging_lease`, or `pipeline/source_integrity` path remains. The documented `python3 autonomy/tools/pins.py ...` commands remain valid through the compatibility entrypoint.

Review 2 verification:

- `python3 -m unittest tests.test_publication_audit` -> `Ran 30 tests`, `OK`.
- `python3 scripts/publication_audit.py --root .` -> `{"errors": [], "gitlinks": 2, "max_blob_bytes": 26214400, "schema_version": 1, "status": "pass", "tracked_files": 4981}`.
