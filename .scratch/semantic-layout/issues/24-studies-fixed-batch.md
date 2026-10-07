# 24: Studies batch: the fixed-batch suites and the experiment catalog

**What to build:** The two fixed-batch architecture suites and the architecture experiment catalog are dissolved: their reusable code lives in the concept it implements, and each study's procedure records live under a directory named for that study.

**Blocked by:** 17 (Concept batch: `detection` variants and GPU workers), 18 (Concept batch: `segmentation`), 19 (Concept batch: `range_view`)

**Status:** done

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

Review-finding follow-up:

- Active architecture runner and harness drivers no longer mutate `sys.path` or carry local `hashlib` digest helpers. The runner supplies `PYTHONPATH` for frozen source-snapshot stage execution, and the runner/harness digest checks use `evidence.source_snapshot.file_sha256`; runner evidence regular-file checks now use `require_regular_file`.
- `autonomy/detection/scored_direction_test.py` uses package imports without test-local `sys.path` manipulation.
- `autonomy/resources/scientific_payload.py` now rejects symlink payload roots and symlink payload files instead of silently skipping them; ordinary directory traversal and hardlink inode deduplication are retained.
- `autonomy/studies:studies` no longer grants visibility to `//autonomy/resources:__pkg__`; resources remains a lower backend and does not depend on study code.

Pure structural moves preserved:

- `db2a04b` kept as the original byte-identical move that placed the suite under studies, later found incomplete by review.
- `402ec64` corrected reusable expanded-batch homes with a pure move into `detection/expanded_batch` and `dataset`.
- `2b455de` moved architecture idea records to `studies/architecture/ideas` with 14 100% renames and 0 insertions/deletions.
- `572c3fc` moved `autonomy/scripts/run-expanded-matrix.py` to `autonomy/studies/expanded_batch/procedure_records/expanded_matrix.py` as a 100% rename after `git show HEAD:autonomy/scripts/run-expanded-matrix.py | cmp - autonomy/studies/expanded_batch/procedure_records/expanded_matrix.py` exited 0.

Closed-gate procedure records retained/deferred as records:

- `studies/fixed_batch/procedure_records/fixed_batch_audit_proposals_v3.py`, `fixed_batch_audit_storage.py`, `fixed_batch_equivalence.py`, `fixed_batch_loss.py`, `fixed_batch_model_contract.py`, `fixed_batch_offline_closure.py`, `fixed_batch_packing.py`, `fixed_batch_prepare.py`, `fixed_batch_prepare_v3.py`, `fixed_batch_rescore_heading.py`, `fixed_batch_run.py`, `fixed_batch_state_contract.py`, `fixed_batch_train.py`, `fixed_batch_treatment_contract.py`, `fixed_batch_unit_contract.py`.
- `studies/expanded_batch/procedure_records/expanded_admit.py`, `expanded_cache_contract.py`, `expanded_close.py`, `expanded_matrix.py`, `expanded_model_contract.py`, `expanded_offline_closure.py`, `expanded_prepare.py`, `expanded_prepare_range.py`, `expanded_publish.py`, `expanded_range_cache_contract.py`, `expanded_run.py`, `expanded_train.py`.

Verification evidence:

- Red regression: after adding the symlink-root and symlink-payload-file tests plus a direct `unittest.main()` hook, `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-24-20261007T095731Z/tmp ./bazelw test --nocache_test_results //autonomy/resources:scientific_payload_test` exited 1 with 2 failures because symlinks were still skipped. After the fix, the same command exited 0: 1 test target passed.
- `python3 -m py_compile autonomy/studies/architecture/experiment_runner.py autonomy/studies/architecture/harness/*.py autonomy/detection/scored_direction_test.py autonomy/resources/scientific_payload.py autonomy/resources/scientific_payload_test.py` exited 0.
- `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-24-20261007T095731Z/tmp ./bazelw test --nocache_test_results //autonomy/studies:architecture__experiment_runner_test //autonomy/studies:all_tests //autonomy/detection:scored_direction_test //autonomy/resources:scientific_payload_test` exited 0: 4 test targets passed.
- Runner contract probes with `PYTHONPATH=autonomy` exited as expected: `python3 autonomy/architecture.py list` exited 0; `python3 autonomy/architecture.py show residual_bev` exited 0; `python3 autonomy/architecture.py run residual_bev --run-id review-dryrun --dry-run` exited 0 and printed the 7-stage plan only; `python3 autonomy/architecture.py verify residual_bev` exited 2 with argparse reporting required `--run-id`.
- Active review scan `rg -n "sys\\.path|hashlib|lambda .*sha|def sha|sha256\\(|file_digest" autonomy/studies/architecture/experiment_runner.py autonomy/studies/architecture/harness autonomy/detection/scored_direction_test.py` returned no matches. Visibility scan confirmed `//autonomy/resources:__pkg__` is absent from `autonomy/studies/BUILD.bazel`.
- `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-24-20261007T095731Z/tmp python3 autonomy/tools/layers.py` exited 0: `PASS: 0 layering problem(s) across 15 layers`.
- `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-24-20261007T095731Z/tmp ./bazelw test //autonomy/...` exited 0: 150 test targets passed.
- `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-24-20261007T095731Z/tmp ./bazelw test --config=cuda --test_tag_filters=requires_gpu //autonomy/...` exited 0: 28 GPU-tagged test targets passed.
- `git diff --quiet 247ae52 -- parallax bazelw MODULE.bazel MODULE.bazel.lock .bazelrc BUILD.bazel` exited 0, so Parallax and wrapper/toolchain inputs are byte-identical to base and the recorded 17-test Parallax pass is reused.
- `python3 scripts/publication_audit.py --root .` exited 0: `{"errors": [], "gitlinks": 2, "max_blob_bytes": 26214400, "schema_version": 1, "status": "pass", "tracked_files": 4998}`.
- `python3 -m unittest tests.test_publication_audit` exited 1 after running 30 tests: 29 passed and the one known read-only path assertion failed at `tests/test_publication_audit.py:465`.
- `git diff --check` exited 0.
- `git diff --quiet 247ae52 -- autonomy/research` exited 0; research files are unchanged.
- `python3 autonomy/tools/pins.py check --base 247ae52` exited 1 with expected retained-receipt impact: `FAIL: 52 changed file(s) pinned by retained receipts`. This is the pin impact report, not a green verification.

Unresolved limitation:

- `python3 -m unittest tests.test_publication_audit` exited 1 after running 30 tests, with one remaining failure at `tests/test_publication_audit.py:465`: the read-only test still asserts `autonomy/architecture/ideas/residual_bev.md` is a living markdown path. The corrected semantic location is `autonomy/studies/architecture/ideas/residual_bev.md`. Adding a compatibility living document under the old `autonomy/architecture` path would conflict with the approved semantic-layout disposition, and `tests/test_publication_audit.py` is outside this worker's allowed edit paths. The standalone publication audit script passes.

### 2026-10-07 parent integration acceptance

Accepted the reviewed implementation `903fb2b`, baseline test-entrypoint repair
`7e6a766`, and study test-entrypoint repair `bdec9a2` together at `a5d9a92`.
Independent spec and standards reviews found no remaining blockers. The study
repair worker exited 0 with a CLEAN supervisor verdict and a clean tree at the
exact reviewed commit. The earlier authorized-resume candidate-moved verdict
and baseline worker read-only `git merge-base` false positive remain preserved
with separate parent acceptance records; neither raw verdict was rewritten.

The publication assertion limitation above is resolved by `c18076a`: the test
uses the current architecture idea path, and the explicitly dated historical
assessment retains its original source paths. Historical source documents were
restored byte-for-byte in `1a1bacf`; living documents use current paths.

Earlier target-only passes did not establish assertion execution. An audit found
33 direct test modules containing 130 original methods without executable test
entrypoints. Repairs preserve those methods and their assertions, add ordinary
entrypoints, and repair two exposed fixture/import failures. On the combined
candidate, inspected uncached logs prove 25 restored CPU modules executed 94
methods and 31 restored modules in the broader GPU diagnostic executed 120
methods, all passing without skips. The latter includes two new symlink tests.
Two live-gated modules containing 12 original methods remain explicitly unrun
until live admission; they are not counted as passed.

Combined verification at `a5d9a92`:

- `./bazelw test --nocache_test_results --test_output=errors //autonomy/...`:
  exit 0, 150 fresh target passes.
- `./bazelw test --config=cuda --test_output=errors //autonomy/...`: exit 0,
  28 cached GPU-tagged target passes. All 28 also passed fresh in the broader
  diagnostic immediately before this check.
- The additional diagnostic using
  `--config=cuda --test_tag_filters=-requires_live_gate,-known_failure
  --nocache_test_results --test_output=errors //autonomy/...` exited nonzero:
  172/178 passed. Six CPU-only targets require pytest/jsonschema absent from GPU
  rootfs v6. This failure is retained, not relabeled a pass. Ticket 28 explicitly
  specifies the default CPU suite plus the GPU-tagged CUDA suite; the diagnostic
  does not alter that approved runtime split or justify changing locked images.
- `python3 -m unittest tests.test_publication_audit`: exit 0, 30 tests passed.
- `python3 scripts/publication_audit.py --root .`: exit 0, no errors.
- `python3 autonomy/tools/layers.py`: exit 0, zero problems across 15 layers.
- `git diff --check` and `git diff --exit-code 247ae52 -- autonomy/research`:
  exit 0.
- Study repair worker additionally ran uncached `./bazelw test //parallax/...`:
  exit 0, 17/17 passed. Parallax and wrapper inputs remain unchanged.

Detailed command logs, exact reviewed blob maps, testcase-count audit, original
supervisor verdicts, runtime-scope audit and parent acceptance records are retained
under `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/` in
`studies-verification/`, `test-execution-*-review.json`,
`24-parent-candidate-acceptance.json`, `test-execution-parent-acceptance.json`,
`study-test-execution-parent-review.json`, and `gpu-runtime-scope.json`.
The retained-receipt pin impact above remains expected and is not a successful
readmission. Production snapshot caller wiring and live readmission remain
separate tickets 26 and 27. No research experiment was launched by this ticket.
