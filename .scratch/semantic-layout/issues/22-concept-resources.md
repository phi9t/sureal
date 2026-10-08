# 22: Concept batch: `resources`

**What to build:** Measured, resource-bounded stage execution lives under `resources`, together with the continuation code that resumes and compares bounded replays.

**Blocked by:** 13 (Concept batch: `insula` and `evidence`)

**Status:** done

- [x] Scope: the stage backend, kernel scope, process lifecycle, stage accounting, commands, workers, checkpoint and retention, and the continuation and continuation-control code
- [x] The stage backend no longer imports from a study; the four study-specific imports are inverted or passed in
- [x] Every module in scope lives in its concept directory and is imported by package path; no `sys.path` manipulation remains in the moved code
- [x] Each moved test sits beside its module as `foo_test.py` and is a Bazel test target
- [x] Bazel visibility lets only the concepts above this one depend on it
- [x] File digests and regular-file checks in the moved code come from the evidence module, not local copies
- [x] The same test modules pass through the wrapper as before the batch, and the pin report for the batch is attached to the ticket
- [x] Files under `research/` are unchanged

## Comments

Built the `resources` concept package around measured, resource-bounded stage execution and bounded replay continuation helpers. The moved modules now live under `autonomy/resources`, tests sit beside their modules as `foo_test.py`, `autonomy/resources/BUILD.bazel` owns the concept-local `py_library` and `py_test` targets, and the layer declaration places `resources` below pipeline/gpu/tier1/advanced/cohort. The resource backend no longer imports study-owned modules directly; study-specific launcher/backend/stage reservation hooks are provided by the caller. File digest and regular-file checks in the moved resource code now use `evidence.source_snapshot` through `resources.sources` or direct evidence imports. The frozen resource command binds the validated resource source layer at both `/tmp/resource-layer` and `/experiment/resources` so package imports work without `sys.path` manipulation.

Integration note: merged `work/semantic-layout/integration` after ticket 18 (`segmentation`) before final verification. The merge commit is `823246d Merge integration after segmentation concept`; `work/semantic-layout/integration` at verification time was `4c0588c`.

Verification commands and results:

- `./bazelw test //autonomy/...` -> exit 0; `Executed 0 out of 149 tests: 149 tests pass.`
- `./bazelw test --config=cuda --test_tag_filters=requires_gpu //autonomy/...` -> exit 0; `Executed 24 out of 24 tests: 24 tests pass.`
- `./bazelw test //parallax/...` -> exit 0; `Executed 0 out of 17 tests: 17 tests pass.`
- `python3 -m unittest tests.test_publication_audit` -> exit 0; `Ran 30 tests in 15.630s`, `OK`.
- `python3 scripts/publication_audit.py --root .` -> exit 0; `{"errors": [], "gitlinks": 2, "max_blob_bytes": 26214400, "schema_version": 1, "status": "pass", "tracked_files": 4987}`.
- `./bazelw test //autonomy/resources:all_tests --test_output=errors --cache_test_results=no` -> exit 0; `Executed 15 out of 15 tests: 15 tests pass.`
- `python3 autonomy/tools/layers.py` -> exit 0; `PASS: 0 layering problem(s) across 13 layers`.
- `git diff --check` -> exit 0; no whitespace errors.
- `git diff --name-status work/semantic-layout/integration...HEAD` -> no `research/` paths; retained evidence under `research/` is unchanged.

Pin report:

`python3 autonomy/tools/pins.py check --base work/semantic-layout/integration` exits 1 with `FAIL: 26 changed file(s) pinned by retained receipts`. This is expected for this concept batch because retained research receipts pin the old resource/continuation/cohort paths or old file bytes. The changed pinned files and reasons are:

- `cohort/audit_sustained_transition.py`: imports the bounded replay values from the new `resources` concept owner.
- `cohort/replay_sustained.py`: imports the bounded replay values from the new `resources` concept owner.
- `cohort/sustained_replay_values.py -> resources/replay_values.py`: moved bounded replay values into the resource concept.
- `cohort/test_sustained_chunk_reference.py`: imports the bounded replay values from the new `resources` concept owner.
- `cohort/test_sustained_reference.py`: imports the bounded replay values from the new `resources` concept owner.
- `cohort/test_sustained_replay_values.py -> resources/replay_values_test.py`: moved the replay value test beside the resource-owned module.
- `continuation/compare_state.py -> resources/compare_state.py`: moved continuation comparison into the resource concept.
- `continuation/legacy_values.py -> resources/legacy_values.py`: moved continuation legacy values into the resource concept.
- `continuation/test_compare_state.py -> resources/compare_state_test.py`: moved the comparison test beside the resource-owned module.
- `continuation/test_legacy_values.py -> resources/legacy_values_test.py`: moved the legacy values test beside the resource-owned module.
- `continuation_control/legacy_binding.py -> resources/legacy_binding.py`: moved continuation-control legacy binding into the resource concept.
- `continuation_control/test_legacy_binding.py -> resources/legacy_binding_test.py`: moved the legacy binding test beside the resource-owned module.
- `resources/README.md`: updated resource concept documentation for the new local ownership and Bazel wrapper path.
- `resources/archive_worker.py`: replaced local digest/regular-file logic with evidence-owned helpers.
- `resources/command.py`: wrapped native commands with the resource source snapshot and package import mount.
- `resources/dependencies.py`: uses evidence-owned safe member naming.
- `resources/execute_worker.py`: uses package imports and evidence-owned regular-file checks.
- `resources/test_execute_worker.py -> resources/execute_worker_test.py`: renamed the test to the concept-local `foo_test.py` convention.
- `resources/test_kernel_scope.py -> resources/kernel_scope_test.py`: renamed the test to the concept-local `foo_test.py` convention.
- `resources/test_resource_archive.py -> resources/archive_worker_test.py`: renamed the test to match the module under test.
- `resources/test_resource_command.py -> resources/command_test.py`: renamed the test to match the module under test.
- `resources/test_resource_retention.py -> resources/retention_test.py`: renamed the test to match the module under test.
- `resources/test_resource_stage.py -> resources/stage_test.py`: renamed the test to match the module under test.
- `resources/test_scoped_stage.py -> resources/scoped_stage_test.py`: renamed the test to the concept-local `foo_test.py` convention.
- `resources/test_stage_accounting.py -> resources/stage_accounting_test.py`: renamed the test to the concept-local `foo_test.py` convention.
- `resources/test_worker_admission.py -> resources/worker_admission_test.py`: renamed the test to the concept-local `foo_test.py` convention.

2026-10-07 review-blocker repair:

P1 source-snapshot retention blocker fixed. `//autonomy/resources:resource_source_layer` now admits `evidence/source_snapshot.py` through the Bazel source closure, and `resources.sources.freeze_sources` materializes repo-relative snapshot members under a frozen root containing both `resources/` and `evidence/`. The resource wrapper now executes `/tmp/resource-layer/resources/execute_worker.py`, overlays frozen `resources/` at `/experiment/resources`, overlays frozen `evidence/` at `/experiment/evidence`, and refuses alias collisions. Retention publication now builds its execution package with `materialize_execution_package()` from the admitted materialized closure; it no longer copies current-tree `evidence/source_snapshot.py` or compares executed helper bytes against the current tree. Current-tree helper edits after admission are ignored; tampered or missing materialized helper bytes are rejected.

P2 concept-boundary blocker fixed. Removed the filename-only `test_tests_use_adjacent_module_test_names` assertion from `autonomy/resources/concept_boundary_test.py`. The remaining checks cover resource API ownership and forbidden study imports, without asserting on module locations or test filename layout beyond the build/spec seams.

Red/green snapshot seam:

- RED: `SUREAL_BAZEL_CACHE=/data02/home/philip.yang/workspace/sureal-worker-sureal-semantic-22-repair/.bazel-cache TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-22-repair-20261007T090638Z/tmp PYTHONDONTWRITEBYTECODE=1 ./bazelw test //autonomy/resources:sources_test //autonomy/resources:command_test //autonomy/resources:retention_test //autonomy/resources:stage_test //autonomy/resources:backend_test //autonomy:source_snapshot_targets_test --test_output=errors --cache_test_results=no` -> exit 3 before the production fix; failures showed `evidence/source_snapshot.py` absent from `source_pins`, missing `resources.sources.source_paths`, no `materialize_execution_package`, and the wrapper still expecting the old flat `/tmp/resource-layer/execute_worker.py` layout.
- GREEN: same command after the fix -> exit 0; `Executed 6 out of 6 tests: 6 tests pass.`

Verification commands and results for the repair:

- `SUREAL_BAZEL_CACHE=/data02/home/philip.yang/workspace/sureal-worker-sureal-semantic-22-repair/.bazel-cache TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-22-repair-20261007T090638Z/tmp PYTHONDONTWRITEBYTECODE=1 ./bazelw test //autonomy/resources:all_tests --test_output=errors --cache_test_results=no` -> exit 0; `Executed 15 out of 15 tests: 15 tests pass.`
- `SUREAL_BAZEL_CACHE=/data02/home/philip.yang/workspace/sureal-worker-sureal-semantic-22-repair/.bazel-cache TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-22-repair-20261007T090638Z/tmp PYTHONDONTWRITEBYTECODE=1 ./bazelw test //autonomy/evidence:source_snapshot_test //autonomy:source_snapshot_targets_test --test_output=errors --cache_test_results=no` -> exit 0; `Executed 2 out of 2 tests: 2 tests pass.`
- `SUREAL_BAZEL_CACHE=/data02/home/philip.yang/workspace/sureal-worker-sureal-semantic-22-repair/.bazel-cache TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-22-repair-20261007T090638Z/tmp PYTHONDONTWRITEBYTECODE=1 ./bazelw test //autonomy/... --test_output=errors --cache_test_results=no` -> exit 0; `Executed 149 out of 149 tests: 149 tests pass.`
- `SUREAL_BAZEL_CACHE=/data02/home/philip.yang/workspace/sureal-worker-sureal-semantic-22-repair/.bazel-cache TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-22-repair-20261007T090638Z/tmp PYTHONDONTWRITEBYTECODE=1 ./bazelw test --config=cuda --test_tag_filters=requires_gpu //autonomy/... --test_output=errors --cache_test_results=no` -> exit 0; `Executed 24 out of 24 tests: 24 tests pass.`
- `SUREAL_BAZEL_CACHE=/data02/home/philip.yang/workspace/sureal-worker-sureal-semantic-22-repair/.bazel-cache TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-22-repair-20261007T090638Z/tmp PYTHONDONTWRITEBYTECODE=1 ./bazelw test //parallax/... --test_output=errors --cache_test_results=no` -> exit 0; `Executed 17 out of 17 tests: 17 tests pass.`
- `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-22-repair-20261007T090638Z/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_publication_audit` -> exit 0; `Ran 30 tests in 14.089s`, `OK`.
- `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-22-repair-20261007T090638Z/tmp PYTHONDONTWRITEBYTECODE=1 python3 scripts/publication_audit.py --root .` -> exit 0; `{"errors": [], "gitlinks": 2, "max_blob_bytes": 26214400, "schema_version": 1, "status": "pass", "tracked_files": 4988}`.
- `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-22-repair-20261007T090638Z/tmp PYTHONDONTWRITEBYTECODE=1 python3 autonomy/tools/layers.py` -> exit 0; `PASS: 0 layering problem(s) across 14 layers`.
- `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-22-repair-20261007T090638Z/tmp PYTHONDONTWRITEBYTECODE=1 python3 autonomy/tools/pins.py check --base 5ba7237` -> exit 1; expected historical move report: `FAIL: 26 changed file(s) pinned by retained receipts`. This is the same retained-receipt concept-move class listed above, not a silent green claim.
- `git diff --name-status 5ba7237...HEAD -- autonomy/research` -> no output; retained research evidence diff is empty.
- `git diff --check` -> exit 0; no whitespace errors.

Count deltas for this repair before ticket evidence text: 15 files changed, 148 insertions, 40 deletions. Resource concept tests stayed at 15/15 pass; full autonomy stayed at 149/149 pass; GPU-tagged autonomy stayed at 24/24 pass; parallax stayed at 17/17 pass; publication unit tests stayed at 30/30 pass; publication audit tracked-file count is now 4988; layering report is now 14 layers.

Final integration review, 2026-10-07:

- Native Corenius worker candidate `8a974df` completed cleanly with exit 0 and was ready for review. Supervisor DEGRADED notes concerned parent branch movements and the optional root BUILD.bazel allow-path having no changes; no boundary violation was reported.
- Follow-up independent review found a missed downstream consumer: `validate_live_references()` prepended resources/ to keys that already contain their package path. Regression coverage now calls that audit on a real materialized execution package and rejects changed or missing helpers in both resources and evidence. The wrapper test failed before the one-line lookup fix and passed after it (five retention test methods). Raw red/green logs are `resources-retention-red.log` and `resources-retention-green.log` in `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/`. Independent rereview closed the finding.
- Recovery candidate `9cfbc92` integrates camera, inspection and motion from `0d07bdc`. Conflicts preserve all concept declarations and both resource and camera/inspection freezer inventories. The architecture table now reflects the merged layer order; motion no longer grants access to resources, which is now below it.
- Integrated gate: 16 focused resource/snapshot targets passed uncached; all 149 CPU targets and 24 GPU-tagged targets passed; 30 publication unit tests, publication audit, layer audit and whitespace checks passed. The extra CPU target relative to the 148 baseline is the resource concept boundary test. Parallax and wrapper/toolchain inputs are unchanged, so the worker's 17 uncached passing Parallax targets remain applicable. Retained research is byte-identical. The legacy tree-pin check still reports expected migration impact rather than successful historical tree validation.
- Exact commands, exits and logs are retained in `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/resources-verification/`. No live HDFS publication or new scientific receipt is claimed by these tests.
- Landing separates 20 byte-identical resource/continuation moves (`d2d4a66`) from wiring, with complete-tree equality checked against this verified recovery candidate. Original worker and mixed-history branches remain preserved.
