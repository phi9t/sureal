# 25: Studies batch: the 16-scene cohort study

**What to build:** The cohort study is dissolved the same way: training loops, losses, metrics, scoring and audits that are reusable live in their concept, the sustained controller stays a runnable tool, and the study's procedure records live under the study's own directory.

**Blocked by:** 22 (Concept batch: `resources`), 24 (Studies batch: the fixed-batch suites and the experiment catalog)

**Status:** ready-for-agent

- [x] Scope: the balanced and sustained training, scoring, admission, retention and audit code of the cohort study
- [x] The sustained controller, its workflow, state and admission remain runnable and tested
- [x] Procedure records of closed gates are exported as files and are not test targets
- [x] The one upward import from the fixed-batch suite into the cohort study is gone
- [x] Every module in scope lives in its concept directory and is imported by package path; no `sys.path` manipulation remains in the moved code
- [x] Each moved test sits beside its module as `foo_test.py` and is a Bazel test target
- [x] Bazel visibility lets only the concepts above this one depend on it
- [x] File digests and regular-file checks in the moved code come from the evidence module, not local copies
- [ ] The same test modules pass through the wrapper as before the batch, and the pin report for the batch is attached to the ticket
- [x] Files under `research/` are unchanged

## Comments

2026-10-07 worker/sureal-semantic-25 source handoff:

- Concept disposition implemented: reusable balanced/detection helpers moved to `autonomy/detection`, overfit points to `autonomy/dataset`, scoring/audit workers to `autonomy/evaluation`, retention inventories/publishers/locks to `autonomy/retention`, sustained controller/workflow/admission/state to `autonomy/training_execution`, fixed16 four-recipe sustained contract to `autonomy/detection`, independent sustained scoring budget to `autonomy/resources`, and closed procedure records to `autonomy/studies/balanced16/procedure_records`.
- Closed gate records are retained as exported study files and are not test targets. Deferred closed records remain under `autonomy/studies/balanced16/procedure_records`: `audit_selection.py`, `audit_targets.py`, `audit_targets_v2.py`, `close_balanced_study.py`, `coverage.py`, `diagnose_fit.py`, `finish_balanced_study.py`, `launch_balanced_study.py`, `loss.py`, `loss_balanced.py`, `overfit-box-worker.py`, `overfit-native-cache-audit.py`, and `scan_boxes.py`.
- Parent-review fixes included: `ResourceNativeBackend` now publishes and validates the resource checkpoint closure before native release, persists a resource-publication sidecar, recovers/validates the sidecar on resume, and fails closed on failed readback/admission/tampered retained proof/native release failure. Resource publication validation reopens chunk proofs, independent `retention_audit.py` proof, retained inputs/outputs/logs, exact command mounts, private-root readonly namespace, backend-bound resource source/runtime/rootfs/archive identities, and externally computed union output. Native release recovery now derives the exact 19-member release set from admitted final/train receipts and refuses partial, reduced, substituted, or uncompleted release evidence after payload files are deleted. `NativeBackend.publish_and_release` invokes `python -m retention.publish_sustained_checkpoint` from the autonomy package root with `PYTHONPATH` removed while preserving `pass_fds` and timeout. Evaluation depends downward on `detection.sustained_contract` and `resources.sustained_scoring_budget`, not the full training controller, and the rejected upward exceptions were removed. Active moved auditors now use `evidence.source_snapshot.file_sha256` and `require_regular_file` instead of local file digest/regular-file copies.
- Regression red/green evidence: the new coherent reduced native-release-plan test first failed because `ValueError` was not raised after payload deletion; after deriving the expected release inventory from admitted receipts, `//autonomy/training_execution:run_sustained_test` passed. The new coherent protected-descendant mount overlay case first failed because `ValueError` was not raised; after rejecting protected descendant mounts, the same target passed.

Verification:

- `./bazelw test //autonomy/training_execution:run_sustained_test --nocache_test_results --test_output=errors`: exit 0; 1 of 1 target passed; actual log count 13 test methods.
- `./bazelw test //autonomy/detection:sustained_contract_test //autonomy/resources:sustained_scoring_budget_test //autonomy/resources:checkpoint_test //autonomy/training_execution:run_sustained_test //autonomy/training_execution:sustained_controller_backend_test //autonomy:source_snapshot_targets_test --nocache_test_results --test_output=errors`: exit 0; 6 of 6 targets passed.
- `./bazelw test //autonomy/evaluation:metrics_sustained_v3_test --test_tag_filters=requires_live_gate --nocache_test_results --test_output=errors`: exit 0; 1 of 1 target passed; actual log count 3 test methods.
- `./bazelw test //autonomy/... --nocache_test_results --test_output=errors`: exit 0; 151 of 151 test targets passed.
- `./bazelw test --config=cuda --test_tag_filters=requires_gpu //autonomy/... --nocache_test_results --test_output=errors`: exit 1 before Bazel analysis or test execution; wrapper preflight raised `ValueError: GPU device not found: /dev/nvidia1`. Because this configured GPU gate did not execute, this ticket is not marked done.
- Moved CPU/live method counts from current uncached `test.log` files under `.bazel-cache/output-base/execroot/_main/bazel-out/k8-fastbuild/testlogs`: 102 executed methods total across the original 23 moved CPU/live targets, plus 13 methods in the added `run_sustained_test` runtime-composition regression target, for 115 methods recorded here. Per-target counts: `balanced_test` 6, `sustained_catalog_test` 4, `sustained_groundtruth_test` 4, `cache_inventory_test` 3, `checkpoint_retention_policy_test` 4, `checkpoint_retention_sources_test` 4, `pilot_retention_sources_test` 4, `retention_sources_test` 4, `sustained_checkpoint_inventory_test` 4, `sustained_controller_lock_test` 3, `sustained_pilot_inventory_test` 4, `sustained_contract_test` 8, `sustained_scoring_budget_test` 3, `admissions_test` 4, `balanced_gate_test` 3, `protocol_test` 6, `sustained_admission_test` 4, `sustained_control_test` 5, `sustained_controller_backend_test` 7, `sustained_sources_test` 5, `sustained_stage_inputs_test` 3, `sustained_workflow_test` 7, `metrics_sustained_v3_test` 3, `run_sustained_test` 13.
- GPU-tagged moved targets not executed because of the wrapper preflight blocker: `//autonomy/detection:sustained_literal_loss_test`, `//autonomy/detection:sustained_loss_test`, `//autonomy/training_execution:audit_sustained_transition_test`, `//autonomy/training_execution:sustained_chunk_reference_test`, `//autonomy/training_execution:sustained_loop_test`, `//autonomy/training_execution:sustained_reference_test`, `//autonomy/training_execution:sustained_state_test`, and `//autonomy/training_execution:sustained_worker_guard_test`.
- `python3 -m unittest tests.test_publication_audit`: exit 0; 30 tests passed.
- `python3 scripts/publication_audit.py --root .`: exit 0; status `pass`, 5,003 tracked files, 2 gitlinks.
- `python3 autonomy/tools/layers.py`: exit 0; `PASS: 0 layering problem(s) across 17 layers`.
- `python3 autonomy/tools/pins.py check --base c2f92f85dbd15c63976a576624230b1cad0aff8e`: exit 1, expected retained-receipt impact for 66 moved files from `cohort/*` to their concept destinations, including `cohort/sustained_contract.py -> detection/sustained_contract.py` and `cohort/sustained_scoring_budget.py -> resources/sustained_scoring_budget.py`; no retained research receipt was rewritten.
- `git diff --check`: exit 0.
- `git diff --quiet c2f92f85dbd15c63976a576624230b1cad0aff8e -- autonomy/research`: exit 0; retained research files unchanged.
- `git diff --quiet c2f92f85dbd15c63976a576624230b1cad0aff8e -- parallax bazelw .bazelrc .bazelversion MODULE.bazel MODULE.bazel.lock`: exit 0; Parallax and wrapper/toolchain inputs byte-identical to base, so the recorded 17-test Parallax pass is reused and `//parallax/...` was not rerun.
