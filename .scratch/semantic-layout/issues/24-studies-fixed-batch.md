# 24: Studies batch: the fixed-batch suites and the experiment catalog

**What to build:** The two fixed-batch architecture suites and the architecture experiment catalog are dissolved: their reusable code lives in the concept it implements, and each study's procedure records live under a directory named for that study.

**Blocked by:** 17 (Concept batch: `detection` variants and GPU workers), 18 (Concept batch: `segmentation`), 19 (Concept batch: `range_view`)

**Status:** ready-for-human

- [x] Scope: the fixed-batch overfit suite, the expanded suite, and the architecture catalog, runner and harness
- [x] Reusable models, catalogs, packing, contracts and losses move to their concept; the experiment runner stays a runnable, tested tool
- [x] Procedure records of closed gates are exported from the build graph as files and are not test targets
- [x] Each module name that existed in more than one directory now has one home, or two clearly different names
- [x] Every module in scope lives in its concept directory and is imported by package path; no `sys.path` manipulation remains in the moved code
- [x] Each moved test sits beside its module as `foo_test.py` and is a Bazel test target
- [x] Bazel visibility lets only the concepts above this one depend on it
- [x] File digests and regular-file checks in the moved code come from the evidence module, not local copies
- [x] The same test modules pass through the wrapper as before the batch, and the pin report for the batch is attached to the ticket
- [x] Files under `research/` are unchanged

## Comments

### 2026-10-07 worker/sureal-semantic-24 candidate

Corrected disposition after review:

- Reusable expanded-batch catalog/model/packing/point/sparse/spatial code lives under `autonomy/detection/expanded_batch`.
- Expanded-batch observation loading lives under `autonomy/dataset/expanded_batch_observations.py`.
- Fixed-batch reusable catalog/model code lives under `autonomy/detection/fixed_batch_catalog.py` and `autonomy/detection/fixed_batch_models.py`.
- Shared digest, regular-file, artifact-lifecycle and scientific payload helpers live under `autonomy/evidence` and `autonomy/resources`.
- `autonomy/studies/expanded_batch` and `autonomy/studies/fixed_batch` keep study READMEs, verifiers, and filegroup-exported `procedure_records`; procedure records are not test targets or reusable libraries.
- `autonomy/studies/architecture` keeps the active architecture runner, harness, registry and idea documents. The top-level `autonomy/architecture.py` wrapper remains the runnable command surface.

Boundary decision: `autonomy/detection/expanded_batch` is a split detection composition package. Lower-level point, sparse, packing and model factory code belongs with detection. The expanded model factory is allowed one documented layer exception to compose `range_view.RangePillar` without making `range_view` depend back on detection. The retained fixed-batch `fixed_batch_prepare_v3.py` procedure record keeps its historical cohort import as a documented legacy exception because its bytes are evidence and it is filegroup-exported only.

Pure structural moves preserved:

- `db2a04b` kept as the original byte-identical move that placed the suite under studies, later found incomplete by review.
- `402ec64` corrected reusable expanded-batch homes with a pure move into `detection/expanded_batch` and `dataset`.
- `2b455de` moved architecture idea records to `studies/architecture/ideas` with 14 100% renames and 0 insertions/deletions.
- `572c3fc` moved `autonomy/scripts/run-expanded-matrix.py` to `autonomy/studies/expanded_batch/procedure_records/expanded_matrix.py` as a 100% rename after `git show HEAD:autonomy/scripts/run-expanded-matrix.py | cmp - autonomy/studies/expanded_batch/procedure_records/expanded_matrix.py` exited 0.

Closed-gate procedure records retained/deferred as records:

- `studies/fixed_batch/procedure_records/fixed_batch_audit_proposals_v3.py`, `fixed_batch_audit_storage.py`, `fixed_batch_equivalence.py`, `fixed_batch_loss.py`, `fixed_batch_model_contract.py`, `fixed_batch_offline_closure.py`, `fixed_batch_packing.py`, `fixed_batch_prepare.py`, `fixed_batch_prepare_v3.py`, `fixed_batch_rescore_heading.py`, `fixed_batch_run.py`, `fixed_batch_state_contract.py`, `fixed_batch_train.py`, `fixed_batch_treatment_contract.py`, `fixed_batch_unit_contract.py`.
- `studies/expanded_batch/procedure_records/expanded_admit.py`, `expanded_cache_contract.py`, `expanded_close.py`, `expanded_matrix.py`, `expanded_model_contract.py`, `expanded_offline_closure.py`, `expanded_prepare.py`, `expanded_prepare_range.py`, `expanded_publish.py`, `expanded_range_cache_contract.py`, `expanded_run.py`, `expanded_train.py`.

Verification evidence:

- `python3 autonomy/tools/layers.py` exited 0: `PASS: 0 layering problem(s) across 15 layers`.
- Focused moved-module wrapper check `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-24-20261007T095731Z/tmp ./bazelw test //autonomy/detection/expanded_batch:all_tests //autonomy/dataset:expanded_batch_observations_test //autonomy/studies:all_tests` exited 0: 3 CPU-visible tests passed. GPU-tagged moved tests were covered by the CUDA run.
- `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-24-20261007T095731Z/tmp ./bazelw test //autonomy/...` exited 0: 150 tests passed.
- `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-24-20261007T095731Z/tmp ./bazelw test --config=cuda --test_tag_filters=requires_gpu //autonomy/...` exited 0: 28 tests passed, including `dataset:expanded_batch_observations_test`, `detection/expanded_batch:models_test`, `point_modules_test`, and `sparse_sets_test`.
- `git diff --quiet 247ae52 -- parallax bazelw MODULE.bazel MODULE.bazel.lock .bazelrc BUILD.bazel` exited 0, so Parallax and wrapper/toolchain inputs are byte-identical to base and the recorded 17-test Parallax pass is reused.
- `python3 scripts/publication_audit.py --root .` exited 0: `{"errors": [], "gitlinks": 2, "max_blob_bytes": 26214400, "schema_version": 1, "status": "pass", "tracked_files": 4998}`.
- `git diff --check` exited 0.
- `git diff --quiet 247ae52 -- autonomy/research` exited 0; research files are unchanged.
- `python3 autonomy/tools/pins.py check --base 247ae52` exited 1 with expected retained-receipt impact: `FAIL: 52 changed file(s) pinned by retained receipts`. This is the pin impact report, not a green verification.

Unresolved limitation:

- `python3 -m unittest tests.test_publication_audit` exited 1 after running 30 tests, with one remaining failure at `tests/test_publication_audit.py:465`: the read-only test still asserts `autonomy/architecture/ideas/residual_bev.md` is a living markdown path. The corrected semantic location is `autonomy/studies/architecture/ideas/residual_bev.md`. Adding a compatibility living document under the old `autonomy/architecture` path would conflict with the approved semantic-layout disposition, and `tests/test_publication_audit.py` is outside this worker's allowed edit paths. The standalone publication audit script passes.
