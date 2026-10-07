# 23: Concept batch: `inspection`

**What to build:** Tools for looking at scenes live under `inspection`: the web viewer, the explorer and the inspection views.

**Blocked by:** 14 (Concept batch: `dataset`), 15 (Concept batch: `geometry`)

**Status:** ready-for-agent

- [x] Scope: the viewer's exporter and its tests, the explorer's preview and render workers, scene inspection and inspection views
- [x] The viewer's web front end keeps its own npm toolchain and its run script works from the new location
- [x] Every module in scope lives in its concept directory and is imported by package path; no `sys.path` manipulation remains in the moved code
- [x] Each moved test sits beside its module as `foo_test.py` and is a Bazel test target
- [x] Bazel visibility lets only the concepts above this one depend on it
- [x] File digests and regular-file checks in the moved code come from the evidence module, not local copies
- [x] The same test modules pass through the wrapper as before the batch, and the pin report for the batch is attached to the ticket
- [x] Files under `research/` are unchanged

## Comments

Built:
- Moved the inspection concept into `autonomy/inspection`: scene inspection, inspection views/validation, explorer preview/render helpers, the viewer exporter, adjacent exporter tests, repo-hygiene test, viewer run script, site stub and Vite frontend.
- Added `autonomy/inspection/BUILD.bazel` with the concept `py_library`, runfiles groups, adjacent `py_test` targets and `all_tests`.
- Updated root autonomy build groups, layer declarations, publication-audit paths and viewer ignores for the new concept location.
- Added `evidence.source_snapshot.file_digest(path, algorithm)` and made moved digest callers use the evidence regular-file/digest helpers.

Focused verification:
- `./bazelw test //autonomy/evidence:source_snapshot_test //autonomy/inspection:all_tests --test_output=errors --cache_test_results=no` passed, 7/7 tests.
- `./bazelw test //autonomy/evidence:source_snapshot_test //autonomy/inspection:all_tests //autonomy:tools__test_layers //autonomy:source_snapshot_targets_test //autonomy:tools_test_suites --test_output=errors --cache_test_results=no` passed, 10/10 tests.
- `bash -n autonomy/inspection/viewer/run.sh` passed.
- `autonomy/inspection/viewer/run.sh help` passed and printed usage from the moved path.
- `(cd autonomy/inspection/viewer/web && npm ci)` passed.
- `autonomy/inspection/viewer/run.sh build` passed.
- `git diff --check` passed.
- `git diff --name-only | rg '(^|/)research/'` returned no paths.

Pinned/restricted-file report before this commit:
- `python3 autonomy/tools/pins.py check --base work/semantic-layout/integration` exited 1 with `FAIL: 70 changed file(s) pinned by retained receipts`.
- Of those 70 paths, 54 are this ticket's inspection batch: `explorer/camera_preview.py`, `tests/test_inspection.py`, viewer exporter files, viewer exporter tests, viewer `run.sh`, viewer web files and the removed `viewer/tests/__init__.py`. These are changed because the ticket requires those retained inspection/viewer/explorer files to move under the `inspection` concept. `viewer/tests/__init__.py` is removed because tests now sit beside modules as `*_test.py` and no separate `tests` package remains.
- The other 16 reported paths are detection-core files already moved by ticket 16 on `work/semantic-layout/integration` but not yet merged into this branch at the time of this pre-commit guard run: `detection/anchor_assignment.py`, `detection/anchor_grid.py`, `detection/box_coding.py`, `detection/detector_geometry.py`, `detection/detector_loss.py`, `detection/native_detection_adapter.py`, `detection/packed_point_features.py`, `detection/pillar_encoder.py`, `detection/pillar_packing.py`, `detection/training_box_process.py`, `detection/training_box_reference.py`, `detection/training_box_resources.py`, `detection/training_box_sender.py`, `detection/training_box_sources.py`, `detection/training_box_statistics.py` and `detection/training_box_wire.py`. They are integration drift, not inspection-ticket edits.
- Restricted inventory `.py` changes made by this ticket: `autonomy/pipeline/inspection.py`, `autonomy/pipeline/inspection_views.py` and `autonomy/pipeline/inspection_validate.py` moved into `autonomy/inspection` because the ticket explicitly scopes scene inspection and inspection views into the inspection concept; `autonomy/cohort/sustained_sources.py` changed only to keep the sustained-source inventory covering the new concept package.


Recovery and independent review, 2026-10-07:

- Preserved the stopped merge's working diff and unmerged index under `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/inspection-merge-preimage`. The incoming merge is integration `5ba7237`; inspection work was already committed at `af75e50`.
- Kept both detection and inspection in the build dependencies, source inventories, and Insula visibility. Removed an incomplete conflict resolution's reference to nonexistent `//autonomy/detection:runfiles`. The incoming detection package supplies its Python sources through its library dependency.
- Independent Spec/Standards review found that the moved viewer `test` command failed unittest discovery. Reproduced `ImportError: Start directory is not importable` with `PYTHONPATH` unset. The command now delegates to `bazelw`, as the build ADR requires. With `WAYMO_VIEWER_VENV=/nonexistent` and `PYTHONPATH` unset, `run.sh test --test_output=errors --cache_test_results=no` passed 6/6 tests. The command needs no local viewer environment. Scoped independent review found the blocker resolved.
- Focused inspection, evidence, source-snapshot and layer targets passed 10/10. Full `./bazelw test //autonomy/... --test_output=errors` passed 148/148; CUDA configuration passed 24/24; `//parallax/...` passed 17/17. Counts match ticket 16's baseline. `python3 -m unittest tests.test_publication_audit` passed 30 tests. Publication audit reported no errors; layering reported zero problems across 16 layers. Logs and exact commands are in `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/inspection-verification/results.json`.
- `bash -n autonomy/inspection/viewer/run.sh` and the viewer production build passed. The build transformed 42 modules. Retained `research/` files have no diff against `5ba7237`.
- The pin report against `5ba7237` exited 1 and lists 54 inspection/viewer paths pinned by retained receipts, matching the ticket's inspection-only inventory above. This is recorded migration impact, not a passing legacy receipt check. The final two-line dispatcher correction changes bytes of a path already in that inventory.
- Preserve the original mixed move/edit commit and recovery branch. The landing branch `work/semantic-layout/23-reviewed` begins with `f5c3225`: exactly 61 byte-identical renames, zero inserted/deleted lines. Apply the verified final tree in a separate wiring commit. Check tree identity before integration; do not rewrite the original branch.
