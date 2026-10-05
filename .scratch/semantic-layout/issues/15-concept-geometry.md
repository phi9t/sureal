# 15: Concept batch: `geometry`

**What to build:** Coordinate and projection mathematics lives under `geometry`.

**Blocked by:** 13 (Concept batch: `insula` and `evidence`)

**Status:** ready-for-agent

- [x] Scope: transforms and the geometry foundation, camera coordinates, projection visibility, native range grids, range-shape references, files, workers and transfer
- [x] Every module in scope lives in its concept directory and is imported by package path; no `sys.path` manipulation remains in the moved code
- [x] Each moved test sits beside its module as `foo_test.py` and is a Bazel test target
- [x] Bazel visibility lets only the concepts above this one depend on it
- [x] File digests and regular-file checks in the moved code come from the evidence module, not local copies
- [x] The same test modules pass through the wrapper as before the batch, and the pin report for the batch is attached to the ticket
- [x] Files under `research/` are unchanged

## Comments

Implementation checkpoint:

- Added `autonomy/geometry/` as a concept-local Bazel package and moved the geometry foundation, native range reconstruction, camera-coordinate math, projection visibility, native range grid, range-shape file/reference/worker, transfer helper, and their direct tests under it.
- Updated active non-research callers to import `geometry.*` and updated live verifier/source lists to use the moved paths. Historical `research/` receipts were left untouched.
- Kept `pipeline/native_shape_source_replay.py` in `pipeline/` because it owns staging/runtime orchestration and still depends on `pipeline.staged_source`; its active worker command and code-pinning list now point at the moved geometry modules.
- Moved shared native range-shape test setup into `geometry/native_range_shape_test_fixtures.py`, avoiding test-to-test imports.
- Replaced local source-byte and regular-file checks in moved range-shape code with `evidence.source_integrity.verify_source` and `evidence.source_snapshot.file_sha256` / `require_regular_file`.

Red/green evidence:

- Red: `./bazelw test //autonomy:geometry__geometry_test --test_output=errors --cache_test_results=no` after moving the test/import first -> failed with `ModuleNotFoundError: No module named 'geometry.geometry'`.
- Green: `./bazelw test //autonomy/geometry:all_tests --test_output=errors --cache_test_results=no` -> `Executed 10 out of 10 tests: 10 tests pass.`
- Compatibility seam: `./bazelw test //autonomy:tests__test_native_shape_staging_deadline --test_output=errors --cache_test_results=no` -> `Executed 1 out of 1 test: 1 test passes.`
- Default component gate: `./bazelw test //autonomy/... --test_output=errors --cache_test_results=no` -> `Executed 148 out of 148 tests: 148 tests pass.`
- Source-snapshot/layering targets: `./bazelw test //autonomy:source_snapshot_targets_test //autonomy:tools__test_layers --test_output=errors --cache_test_results=no` -> `Executed 2 out of 2 tests: 2 tests pass.`
- Static checks: `python3 autonomy/tools/layers.py` -> `PASS: 0 layering problem(s) across 13 layers`; `git diff --check` -> exit 0; `git diff --name-only work/semantic-layout/integration..HEAD -- 'autonomy/research/**' 'parallax/research/**' 'research/**'` -> no output.

Pin report:

`python3 autonomy/tools/pins.py check --base work/semantic-layout/integration` -> exit 1 with `FAIL: 28 changed file(s) pinned by retained receipts`.

Changed pinned paths:

```text
cohort/raw_reconstruct.py
cohort/raw_reconstruct_v3.py
gpu/range-frontend-native-probe.py
gpu/range-pillar-native-probe.py
motion-evaluation/ingestion/current_geometry_fixture.py
pipeline/camera_coordinates.py -> geometry/camera_coordinates.py
pipeline/geometry.py -> geometry/geometry.py
pipeline/geometry_foundation.py -> geometry/geometry_foundation.py
pipeline/inspection.py
pipeline/native_range_grid.py -> geometry/native_range_grid.py
pipeline/native_range_shape_file.py -> geometry/native_range_shape_file.py
pipeline/native_range_shape_worker.py -> geometry/native_range_shape_worker.py
pipeline/native_range_shapes.py -> geometry/native_range_shapes.py
pipeline/native_shape_transfer.py -> geometry/native_shape_transfer.py
pipeline/projection_visibility.py -> geometry/projection_visibility.py
pipeline/reconstruction_probe.py
pipeline/scientific_reconstruction.py
scientific-preprocess.py
tests/test_camera_coordinates.py -> geometry/camera_coordinates_test.py
tests/test_camera_interpolation_parity.py
tests/test_geometry.py -> geometry/geometry_test.py
tests/test_geometry_foundation.py -> geometry/geometry_foundation_test.py
tests/test_native_range_grid.py -> geometry/native_range_grid_test.py
tests/test_native_range_shape_file.py -> geometry/native_range_shape_file_test.py
tests/test_native_range_shape_reference.py -> geometry/native_range_shape_reference_test.py
tests/test_native_range_shape_worker.py -> geometry/native_range_shape_worker_test.py
tests/test_native_range_shapes.py -> geometry/native_range_shapes_test.py
tests/test_native_shape_transfer.py -> geometry/native_shape_transfer_test.py
tests/test_projection_visibility.py -> geometry/projection_visibility_test.py
```

Pinned/guarded file reasons:

- The old `pipeline/geometry_foundation.py`, `pipeline/geometry.py`, `pipeline/camera_coordinates.py`, `pipeline/projection_visibility.py`, `pipeline/native_range_grid.py`, `pipeline/native_range_shapes.py`, `pipeline/native_range_shape_file.py`, `pipeline/native_range_shape_reference.py`, `pipeline/native_range_shape_worker.py`, and `pipeline/native_shape_transfer.py` paths were moved to `autonomy/geometry`; their old retained-receipt paths show up as changed because the receipts are historical.
- The moved test files were renamed from `tests/test_*.py` to colocated `geometry/*_test.py` Bazel targets.
- Active callers in `cohort`, `gpu`, `motion-evaluation`, and `pipeline` were changed only to import `geometry.*` after the move.
- `pipeline/native_shape_source_replay.py` and top-level verifier scripts were changed only so active launch commands, candidate hash lists, and test discovery paths refer to the moved geometry modules.

Final post-merge verification:

- `git merge work/semantic-layout/integration` -> `Already up to date.`
- `./bazelw test //autonomy/... --test_output=errors --cache_test_results=no` -> `Executed 148 out of 148 tests: 148 tests pass.`
- `./bazelw test --config=cuda --test_tag_filters=requires_gpu //autonomy/... --test_output=errors --cache_test_results=no` -> `Executed 24 out of 24 tests: 24 tests pass.`
- `./bazelw test //parallax/... --test_output=errors --cache_test_results=no` -> `Executed 17 out of 17 tests: 17 tests pass.`
- `python3 -m unittest tests.test_publication_audit` -> `Ran 30 tests in 17.979s` and `OK`.
- `python3 scripts/publication_audit.py --root .` -> `{"errors": [], "gitlinks": 2, "max_blob_bytes": 26214400, "schema_version": 1, "status": "pass", "tracked_files": 4983}`.
- `python3 autonomy/tools/pins.py check --base work/semantic-layout/integration` -> exit 1 with the same retained-receipt pin report above: `FAIL: 28 changed file(s) pinned by retained receipts`.
- `git diff --name-only work/semantic-layout/integration..HEAD -- 'autonomy/research/**' 'parallax/research/**' 'research/**'` -> no output.
