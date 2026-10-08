# 18: Concept batch: `segmentation`

**What to build:** Semantic and instance segmentation code lives under `segmentation`, including the native segmentation scoring contract.

**Blocked by:** 14 (Concept batch: `dataset`), 15 (Concept batch: `geometry`)

**Status:** done

- [x] Scope: semantic mapping and support, archive support, the point semantic encoder, point-mask relations and mask point support, foreground support, label coverage, supervision alignment, no-label-zone overlap, segmentation export, semantic recovery jobs, receipts and accounting, and the segmentation contract verifiers
- [x] Every module in scope lives in its concept directory and is imported by package path; no `sys.path` manipulation remains in the moved code
- [x] Each moved test sits beside its module as `foo_test.py` and is a Bazel test target
- [x] Bazel visibility lets only the concepts above this one depend on it
- [x] File digests and regular-file checks in the moved code come from the evidence module, not local copies
- [x] The same test modules pass through the wrapper as before the batch, and the pin report for the batch is attached to the ticket
- [x] Files under `research/` are unchanged

## Pin report

Pre-commit check: `python3 autonomy/tools/pins.py check --base work/semantic-layout/integration` exited 1 because this ticket intentionally moves retained-receipt pinned segmentation files into the `segmentation` concept and updates direct callers.

Pinned files changed and why:
- `pipeline/camera_semantic_scoring.py`, `pipeline/foreground_support.py`, `pipeline/label_coverage.py`, `pipeline/mask_point_support.py`, `pipeline/nlz_overlap.py`, `pipeline/point_mask_relation.py`, `pipeline/point_semantic_encoder.py`, `pipeline/segment_statistics.py`, `pipeline/segmentation_export.py`, `pipeline/semantic_archive_support.py`, `pipeline/semantic_mapping.py`, `pipeline/semantic_recovery_accounting.py`, `pipeline/semantic_recovery_job.py`, `pipeline/semantic_recovery_job_aligned.py`, `pipeline/semantic_recovery_receipt.py`, `pipeline/semantic_recovery_receipt_aligned.py`, `pipeline/semantic_support.py`, `pipeline/staged_derived_archive.py`, `pipeline/staged_derived_archive_aligned.py`, and `pipeline/supervision_alignment.py` moved to `segmentation/` because this ticket defines semantic and instance segmentation as their own concept.
- `evaluation/prepare-real-semantics.py`, `evaluation/real-camera-semantic-probe.py`, `evaluation/real-nlz-probe.py`, `evaluation/segmentation-contract-fixtures.py`, `evaluation/validate-real-nlz.py`, `evaluation/validate-real-semantic-source.py`, `evaluation/validate-real-semantic-wire.py`, `evaluation/verify-real-semantic-export.py`, `evaluation/verify-segmentation-contract.py`, and `evaluation/verify-segmentation-export.py` moved to `segmentation/` because they are segmentation contract, real semantic export, camera semantic, and no-label-zone verifiers for this concept.
- `tests/test_camera_semantic_scoring.py`, `tests/test_foreground_support.py`, `tests/test_label_coverage.py`, `tests/test_mask_point_support.py`, `tests/test_nlz_overlap.py`, `tests/test_point_mask_relation.py`, `tests/test_point_semantic_encoder.py`, `tests/test_segment_statistics.py`, `tests/test_segmentation_export.py`, `tests/test_semantic_archive_support.py`, `tests/test_semantic_mapping.py`, `tests/test_semantic_recovery_accounting.py`, `tests/test_semantic_recovery_job.py`, `tests/test_semantic_recovery_receipt.py`, `tests/test_semantic_recovery_receipt_aligned.py`, `tests/test_semantic_support.py`, `tests/test_staged_derived_archive.py`, `tests/test_staged_derived_archive_aligned.py`, and `tests/test_supervision_alignment.py` moved beside their modules as `segmentation/*_test.py` to satisfy the concept-local test rule.
- `evaluation/evaluator-unit-checks.py` now discovers the moved segmentation exporter test in `/experiment/segmentation`.
- `pipeline/detection_export.py` and `pipeline/prediction_records.py` now import the moved segmentation export and no-label-zone helpers by package path.

## Comments

Built:
- Added `autonomy/segmentation/` as a first-class concept package with a `py_library`, command/runfile filegroups, and concept-local `py_test` targets.
- Moved semantic mapping/support, archive support, point semantic encoding, point-mask and mask-point helpers, foreground support, label coverage, supervision alignment, no-label-zone overlap, segmentation export, semantic recovery jobs/receipts/accounting, staged archive helpers, camera semantic scoring, and segmentation contract/real-source verifiers into `segmentation/`.
- Updated live callers and wrapper discovery to import the moved code by package path (`segmentation.*`) with `autonomy/` as the import root.
- Routed moved production file digest and regular-file checks through `evidence.source_snapshot`.
- Merged `work/semantic-layout/integration`: already up to date.

Verification:
- Red seam before move: `./bazelw test //autonomy/segmentation:semantic_mapping_test --test_output=errors --cache_test_results=no` failed with `ModuleNotFoundError: No module named 'segmentation.semantic_mapping'`.
- Green seam after move: `./bazelw test //autonomy/segmentation:semantic_mapping_test --test_output=errors --cache_test_results=no` passed, 1 test passed.
- `./bazelw test //autonomy/segmentation:all_tests --test_output=errors --cache_test_results=no --keep_going` passed, 14 of 14 default-filtered segmentation tests passed.
- `python3 autonomy/tools/layers.py` passed with `PASS: 0 layering problem(s) across 15 layers`.
- `./bazelw query 'kind(py_test, //autonomy/segmentation:*)'` listed all 19 concept-local test targets.
- `rg -n "sys\\.path" autonomy/segmentation -g '*.py'` produced no matches.
- Non-research stale-import scan for moved `pipeline.*` modules produced no matches.
- `git status --short ':(glob)**/research/**'` produced no output; files under `research/` are unchanged.
- Post-merge `./bazelw test //autonomy/... --test_output=errors --cache_test_results=no --keep_going` passed, 148 of 148 tests passed.
- Post-merge `./bazelw test --config=cuda --test_tag_filters=requires_gpu //autonomy/... --test_output=errors --cache_test_results=no --keep_going` passed, 24 of 24 tests passed, including `//autonomy/segmentation:point_semantic_encoder_test`.
- Post-merge `./bazelw test //parallax/... --test_output=errors --cache_test_results=no --keep_going` passed, 17 of 17 tests passed.
- `python3 -m unittest tests.test_publication_audit` passed, 30 tests ran.
- `python3 scripts/publication_audit.py --root .` passed with `{"errors": [], "gitlinks": 2, "max_blob_bytes": 26214400, "schema_version": 1, "status": "pass", "tracked_files": 4985}`.
- Final pre-comments pin check: `python3 autonomy/tools/pins.py check --base work/semantic-layout/integration` exited 1 with `FAIL: 40 changed file(s) pinned by retained receipts`; the changed pinned files and reasons are listed in the pin report above.

Reviewer notes:
- The pin guard failure is expected for this ticket because retained receipts point at the old `pipeline/`, `evaluation/`, and `tests/` paths. The source files were moved into the `segmentation` concept without editing retained research evidence.
- Default wrapper filters still exclude live-gate and known-failure tests; those moved tests are registered as Bazel targets with their existing tags.
