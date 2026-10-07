# 19: Concept batch: `range_view`

**What to build:** Range-image models live under `range_view`.

**Blocked by:** 16 (Concept batch: `detection` core)

**Status:** done

- [x] Scope: the range frontend, the range-pillar hybrid, sparse windows and sparse window attention, and range fusion
- [x] Every module in scope lives in its concept directory and is imported by package path; no `sys.path` manipulation remains in the moved code
- [x] Each moved test sits beside its module as `foo_test.py` and is a Bazel test target
- [x] Bazel visibility lets only the concepts above this one depend on it
- [x] File digests and regular-file checks in the moved code come from the evidence module, not local copies
- [x] The same test modules pass through the wrapper as before the batch, and the pin report for the batch is attached to the ticket
- [x] Files under `research/` are unchanged

## Pin report

Final pre-evidence check: `python3 autonomy/tools/pins.py check --base a5cf66c` exited 1 with `FAIL: 7 changed file(s) pinned by retained receipts`.

Changed pinned paths and why:

- `advanced/range_fusion.py -> range_view/range_fusion.py` moved because range fusion is owned by the `range_view` concept.
- `pipeline/range_frontend.py -> range_view/range_frontend.py` moved because the range frontend is owned by the `range_view` concept.
- `pipeline/sparse_window_attention.py -> range_view/sparse_window_attention.py` moved because sparse window attention is owned by the `range_view` concept.
- `pipeline/sparse_windows.py -> range_view/sparse_windows.py` moved because sparse window bucketing is owned by the `range_view` concept.
- `tests/test_range_frontend.py -> range_view/range_frontend_test.py` moved beside the range frontend as a concept-local Bazel test.
- `tests/test_sparse_window_attention.py -> range_view/sparse_window_attention_test.py` moved beside sparse window attention as a concept-local Bazel test.
- `tests/test_sparse_windows.py -> range_view/sparse_windows_test.py` moved beside sparse window bucketing as a concept-local Bazel test.

The retained receipts that pin the old paths are historical records and were not rewritten. `tests/test_range_pillar_hybrid.py -> range_view/range_pillar_hybrid_test.py` and `advanced/test_range_fusion.py -> range_view/range_fusion_test.py` also moved for the concept-local test rule, but the pin report did not list them as pinned changed files.

## Comments

Built:

- Added `autonomy/range_view/` as a first-class concept package with a `py_library`, concept-local `py_test` targets, and an `all_py` source filegroup.
- Moved the range frontend, range-pillar hybrid, sparse window bucketing, sparse window attention, range fusion, and their direct tests into `range_view/`.
- Updated active imports to package paths (`range_view.*`) with `autonomy/` as the import root.
- Wired `range_view` into root `autonomy` test/dependency lists, sustained source-snapshot filegroups, `cohort/sustained_sources.py`, and `autonomy/tools/layers.py`.
- Updated active `gpu/range-*-native-probe.py` launch-smoke imports to the moved package path so they still resolve. No scientific recipe, objective, hash, or runtime behavior in those probe scripts was changed.

Focused verification:

- Red seam before package wiring: `./bazelw test //autonomy/range_view:sparse_windows_test --test_output=errors --cache_test_results=no` failed with `no such package 'autonomy/range_view': BUILD file not found`.
- Green seam after package wiring: `./bazelw test //autonomy/range_view:sparse_windows_test --test_output=errors --cache_test_results=no` passed, 1 of 1 test passed.
- `./bazelw test --config=cuda --test_tag_filters=requires_gpu //autonomy/range_view:all_tests --test_output=errors --cache_test_results=no --keep_going` passed, 4 of 4 GPU-tagged range-view tests passed.
- `./bazelw query 'kind(py_test, //autonomy/range_view:*)'` listed `range_frontend_test`, `range_fusion_test`, `range_pillar_hybrid_test`, `sparse_window_attention_test`, and `sparse_windows_test`.
- `./bazelw test //autonomy/range_view:all_tests --test_output=errors --cache_test_results=no --keep_going` passed, 1 of 1 default-filtered range-view test passed.
- `./bazelw test //autonomy:source_snapshot_targets_test --test_output=errors --cache_test_results=no` passed, 1 of 1 test passed after the root filegroup used the explicit `//autonomy/range_view:all_py` edge rather than an empty cross-package glob.
- `rg -n "sys\\.path|hashlib|file_digest|is_file\\(|sha256" autonomy/range_view -g '*.py'` produced no matches.
- Non-research stale old import scan for the moved `pipeline.*` and `advanced.range_fusion` modules produced no matches.
- `cd autonomy && env -u PYTHONPATH python3 - <<'PY' ... from range_view.sparse_windows import partition_sparse_windows ... PY` printed `1`.

Full verification:

- `./bazelw test //autonomy/... --test_output=errors --cache_test_results=no --keep_going` passed, 148 of 148 tests passed.
- `./bazelw test --config=cuda --test_tag_filters=requires_gpu //autonomy/... --test_output=errors --cache_test_results=no --keep_going` passed, 24 of 24 tests passed.
- `./bazelw test //parallax/... --test_output=errors --cache_test_results=no --keep_going` passed, 17 of 17 tests passed.
- `python3 -m unittest tests.test_publication_audit` passed, 30 tests ran.
- `python3 scripts/publication_audit.py --root .` passed with `{"errors": [], "gitlinks": 2, "max_blob_bytes": 26214400, "schema_version": 1, "status": "pass", "tracked_files": 4988}`.
- `python3 autonomy/tools/layers.py` passed with `PASS: 0 layering problem(s) across 18 layers`.
- `git diff --check` exited 0.
- `git diff --name-only a5cf66c..HEAD -- 'autonomy/research/**' 'parallax/research/**' 'research/**'` produced no output.
- Final pin check: `python3 autonomy/tools/pins.py check --base a5cf66c` exited 1 with the retained-receipt pin report above. This is expected for intentional moves of pinned historical source paths and is not claimed as a green verification.

Count delta:

- Ticket16 baseline was 148 CPU autonomy tests, 24 GPU-tagged autonomy tests, 17 parallax tests, and 30 publication tests. This ticket matched those counts exactly.

Deferred procedure-record work:

- `advanced/prepare_range.py` and `advanced/range_cache_contract.py` remain fixed-batch range-fixture procedure records for the studies batch. They were not moved or refactored here.
- `gpu/range-frontend-native-probe.py`, `gpu/range-pillar-native-probe.py`, and `gpu/sparse-window-native-probe.py` remain hyphenated live-probe launchers in `gpu/`; this ticket changed only their imports so active launch smokes resolve the moved `range_view` package. Any later relocation as closed procedure records, and any digest-helper cleanup inside those scripts, is deferred to the relevant studies/detection-variants tickets.

Review:

- A clean-context reviewer found no Critical issues and no code-level Important issues. The reviewer requested ticket evidence and an explicit rationale for the `gpu/range-*` import edits; both are recorded above.

Integration refresh:

- No merge was performed in this worker because the hard rules for this run forbid merge/rebase/reset/switch operations, and this private workspace started from integration commit `a5cf66c`.

Lead integration verification, 2026-10-07:

- Independent standards and spec reviews found no code blocker. The architecture table ordering issue is corrected: range_view is above detection and below pipeline, consistent with the declared layer graph. The ten-file move commit `0b1a2ab` contains only byte-identical renames.
- Merged reviewed integration `653889e` into candidate `f971ce1`. Resolution preserves resource, motion, camera and inspection declarations, the relocated detection helper requirements, and range_view in the sustained freezer. Native worker's subsequent `3f4ef2f` changes only ticket evidence/status and was merged without changing the tested code.
- Integrated verification passed: three focused CPU range/snapshot/architecture targets; all 150 CPU targets; all 28 GPU-tagged targets; 30 publication unit tests; publication audit; layer audit; whitespace check. Parallax and wrapper/toolchain inputs are byte-identical to the native worker's candidate, whose 17 Parallax targets passed. Historical research files remain unchanged.
- Legacy tree-pin check reports expected migration impact and is not a passing historical receipt validation. Exact command/exit records and raw logs are in `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/range-verification/`. Native worker records remain in the sibling `runs/workers/sureal-semantic-19-20261007T092814Z/` directory. No new live scientific run is claimed.
