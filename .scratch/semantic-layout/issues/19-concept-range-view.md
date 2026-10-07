# 19: Concept batch: `range_view`

**What to build:** Range-image models live under `range_view`.

**Blocked by:** 16 (Concept batch: `detection` core)

**Status:** ready-for-agent

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
