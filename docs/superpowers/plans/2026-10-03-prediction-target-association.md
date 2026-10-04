# Prediction–Target Association Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task in the existing tracer worktree. This documentation update does not execute the plan. Respect the current session's execution and delegation restrictions.

**Goal:** Establish globally verified target coverage and determine whether ownership,3Dgeometry or prediction-aware matching improves native all-class fitting and time-to-fit.

**Architecture:** Add a separate association package and immutable run namespace. Reuse the frozen baseline and original loss/decoder, build shared bounded candidate graphs, reserve one slot per GT globally, then preserve legacy positives on unreserved slots. Independently verify target/oracle/model evidence before stage advancement.

**Tech Stack:** Torch GPU runtime, NumPy/SciPy CPU runtime, official C++ Waymo metrics, existing live Insula launch/admission and Waystone HDFS mechanisms. No TensorFlow.

**Spec:** [association design](../specs/2026-10-03-prediction-target-association-design.md). [Ticket41](../../research/tasks/41-prediction-target-association.md). [Experiment handbook](../../../experiments/waymo-perception/research/prediction-target-association-study.md).

## Global constraints

- All implementation milestones run live Insula and obtain independent source/input/runtime/output-bound admission. The solver must be available in both CPU preparation and Torch training roots. If SciPy is absent in either, admit a separately versioned execution root first; do not mutate active roots. All A0–A3 runs share the same training root.
- Add new modules; do not modify active/historical pipeline,tier1,advanced or sustained-controller sources. Reuse pinned baseline exports in the new runner.
- A0–A3 share initial model tensors, seed17, GN8/PFN-BN, observations, lattice, templates, eligibility, loss, Adam1e-4/betas(.9,.999)/eps1e-8/wd0/foreachFalse, clip10 and correctedV3 decode. FP32,TF32off,deterministic,noaugmentation.
- Preserve73eligible objects in the fixed-batch fixture and1,053eligible/all1,279native evaluation GT in balanced16. GT information stays outside observation features. No metric denominator changes.
- Candidate neighborhoods grow radius1→2→3 only for deficient components; use all8slots/cell plus declared inherited legacy positives. Freeze the resulting prediction-independent graph for A1–A3. A1 cost1-nearestBEVIoU; A2 costmean-absolute-six-encoded-residuals+1-rotated3DIoU.
- A3 alpha0through completed update64, linear64→256, then1. Detached prediction cost uses positive-minus-background focal +2localization+.2direction+1-3DIoU; retain the original target coder and loss parameters.
- Fixed-batch scores:0,25,50,100,200,300,500,750,1000,1500,2000,3000,4000,6000,8000,10000. Balanced16:0,1000,2000,4000,8000,12000,16000,24000,32000 with the declared1,000-update/next-grid confirmation rule. All four nativeLEVEL2APH>=.8 at consecutive samples includingterminal.
- GPUlock is the existing architecture-experiments lock. Caps:GPU8GiB,RSS16GiB,raw2GiB,scientific15GiBunique-inodepayload,reserve2GiB/case. Fixed-batch maximum10,000updates; balanced16maximum32,000updates; both have a7,200synchronizedstep-second cap. Native scoring14,400seconds/host14,700seconds. Report solver and audit overhead separately.
- HDFS upload, exact readback and independent live recovery precede declared local release. Preserve existing archives, historical bytes and negative evidence. Failure retains local artifacts and blocks budget-exceeding work.

## File structure

All paths below are relative to`experiments/waymo-perception/` unless prefixed`docs/`.

- `association/contract.py`: exact recipe/input/runtime/schema validation and phase/checkpoint rules.
- `association/candidate_graph.py`: bounded immutable graphs and feasibility diagnostics.
- `association/matching.py`: minimum-cost distinct reservations on declared edges.
- `association/targets.py`: final ownership/residual/direction arrays with legacy-extra preservation.
- `association/costs.py`: static and detached prediction-dependent costs, with term diagnostics.
- `association/audit_worker.py`: independent graph/ownership/geometry/loss/oracle reconstruction; must not import producer graph,matcher,target or cost functions.
- `association/train.py`, `association/replay.py`: source-frozen optimizer and exact assignment/model/Adam/RNG replay.
- `association/run.py`, `association/close.py`: operator stages, locks, resumable source identity, retention and whole-run admission.
- `association/test_*.py`: meaningful fixtures for the module each test owns.
- Existing `tracking/` integration and registry: add this study only when its frozen runtime/input/source contract and gates are executable. Generated dashboards/journal remain derived.

## Review focus

- An object can lose its sole positive after local conflict resolution: test shared-best-slot and same-class competition in Task2.
- Equal-cost and shuffled inputs can change ownership: test canonical IDs/indices and minimum-cost equality in Task2.
- Thin or vertically separated boxes can produce zeroIoU and misleading coverage: test finite residual-based costs and explicit zero-overlap diagnostics in Task3.
- Dynamic resume can use the wrong phase or owner while restoring model/Adam correctly: test completed-update64/256 boundaries and uninterrupted next-update equality in Task4.
- Perfect assigned boxes can still be suppressed by BEVNMS: test a vertically separated ideal-head pair and keep its result distinct from the annotation-only oracle in Task5.

## Task1 / 41.1: Freeze the study and admit its runtime

**Files:** Create`association/contract.py`,`association/test_contract.py` and the new run's immutable manifest; no registry/dashboard mutation yet.

**Interfaces:** `validate_contract(candidate: dict, *, inputs: dict, runtime_locks: dict) -> dict` returns a validated deep copy. `prediction_alpha(completed_updates: int) -> float` implements the exact schedule. The manifest contains schema_version1, A0–A3 recipes, canonical frame/GT/input hashes, graph policy, baseline/optimizer/loss/decoder pins, checkpoint grids, budgets and runtime/solver identities.

- [ ] Write `test_contract_rejects_changed_frames_gt_sources_and_budgets`, `test_alpha_boundaries` and `test_absent_solver_requires_new_runtime_admission`; assert alpha(64)=0,alpha(160)=.5,alpha(256)=1 and rejection of negative/noninteger steps.
- [ ] Run`python -m pytest association/test_contract.py -q` in the locked CPU Insula with the package mounted read-only; retain failing fixtures before implementation. Expect contract failures until the interface exists.
- [ ] Implement validation and check SciPy in both locked CPU preparation and Torch training runtimes. Admit a new versioned M0 root wherever absent, with Torch/driver execution regression checks if the training root changes. Keep every A0–A3 case in the same admitted training root; historical A0 cannot be reused across a changed runtime identity without a separate equivalence admission.
- [ ] Run the complete contract fixtures live; independently rehash frames,1,053eligible/1,279native scope and73-object fixture, sources, roots and assertions. Expect all fixtures passing and no optimizer execution.
- [ ] Review the frozen manifest and retain its live admission. Commit only this completed unit during an authorized execution workflow.

## Task2 / 41.2: Build globally covered static targets

**Files:** Create`association/candidate_graph.py`,`association/matching.py`,`association/targets.py`,`association/test_matching.py`,`association/test_targets.py`; start`association/audit_worker.py`.

**Interfaces:**

- `build_graph(anchors, gt_boxes, gt_ids, legacy_target_indices, legacy_positive_mask, *, initial_radius=1, max_radius=3) -> dict` returns sorted int64`edges[E,2]` as(anchor_index,canonical_target_index), sorted`target_ids`,`canonical_to_input`,`radius_by_target`,`legacy_exceptions` and`feasibility`. Convert legacy indices to canonical order; cost/target callers reorder GT boxes using`canonical_to_input`.
- `reserve(graph: dict, costs, *, n_anchors: int, n_targets: int) -> dict` returns status, reserved anchor/target index vectors, objective and deficiency report. Any infeasible status prevents target admission; absent edges cannot be selected.
- `assemble_targets(anchors, gt_boxes, legacy: dict, reservations: dict) -> dict` returns full labels,target_indices,box_targets,direction_targets,reserved_mask and coverage report. Unreserved legacy labels/owners remain exact; reserved slots are positive and use the reserved GT.

- [ ] Write fixtures: two GT share their best slot but have a feasible lower-total-cost global solution; same-class ownership conflict; tied costs; canonical input permutations; empty GT; duplicateIDs; insufficientslots; radius expansion joining components; reservedslot cannot be overwritten. Assert complete unique coverage and original unreserved arrays.
- [ ] Run`python -m pytest association/test_matching.py association/test_targets.py -q` live and retain the expected failing results.
- [ ] Implement the bounded graph, SciPy rectangular assignment and final target assembly, reusing pinned eligibility/coder/direction semantics without changing the legacy module. Compute A1's existing-geometry costs and record zero-overlap reservations.
- [ ] Run green fixtures inside CPU Insula. The independent worker uses exhaustive enumeration on tiny graphs to establish cardinality/objective, independently reconstructs all16legacy grids and30uncoveredIDs, then checks every A1owner/residual/direction/mask and all1,053eligibleIDs. Its audit may accept a different tied optimum only if constraints and objective agree; producer repeat/permutation checks still require canonical equality.
- [ ] Admit versioned A0/A1target artifacts and full annotation-only ROIoracle, including native protobuf reread/metric replay and signAPH0.868421±1e-6. No model or NMS success claim. Review and retain this unit's receipts.

## Task3 / 41.3: Implement 3D and learned matching costs

**Files:** Create`association/costs.py`,`association/test_costs.py`; extend the independent`association/audit_worker.py`.

**Interfaces:** `reservation_costs(treatment: str, anchors, gt_boxes, graph: dict, *, outputs: dict | None=None, completed_updates: int=0) -> dict` returns float64`costs[E]`, individual term arrays and alpha. Prediction outputs are`logits[A,4]`,`boxes[A,7]`encodedresiduals,`direction_logits[A,2]`; gather only candidate slots before transfers. Matching consumes detached values. `outputs` is required only for the prediction-dependent phase.

- [ ] Write `test_center_z_separates_bev_identical_boxes`, `test_zero_iou_has_finite_residual_cost`, `test_a1_cost_is_original_similarity`, `test_prediction_cost_is_detached`, `test_direction_wrap_and_alpha_boundaries`, and invalid-dimension/nonfinite-output fixtures. Assert A1geometry is unchanged and A2uses center-Z, not bottom-Z.
- [ ] Run numerical fixtures with`python -m pytest association/test_costs.py -m 'not gpu' -q` in CPU Insula and Torch/detachment fixtures with`python -m pytest association/test_costs.py -m gpu -q` in GPU Insula, first red then green. Keep Torch imports inside the prediction path/test fixtures so CPU collection does not require Torch. Implement exactly the spec's coefficients and schedule; independently reconstruct classification-background difference, SmoothL1/sine/direction and rotated3Dgeometry on analytic fixtures.
- [ ] Replay A2on all16frozen graphs; verify complete owners/targets/oracle and term distributions. For A3 run a real73-object CUDA forward/backward and a bounded multi-update assignment pilot with independent losses and no-grad assignment checks. The actual task loss must remain the original loss after target selection.
- [ ] Independently inspect all30originalmissing objects, height-separation count, positivecounts/normalizers and retained physical point support. Report impl/geometry admission separately from fitting quality.
- [ ] Admit source/cost/graph/output-bound live receipts and retain rejected/nonfinite variants. Review this unit before continuing.

## Task4 / 41.4: Run and replay the first-tier study

**Files:** Create`association/train.py`,`association/replay.py`,`association/test_replay.py`; add the fixed-batch branch of`association/run.py`.

**Interfaces:** `train(manifest: dict, *, treatment: str, tier: str, resume_checkpoint: str | None) -> dict` emits the complete sampled trajectory and stop reason. `replay(manifest: dict, checkpoint: str) -> dict` independently checks exact initial/model/Adam/RNG/head/next-assignment state. Each sample pins graph,costs,owners,completedupdate,phase,source,input,runtime and loss equations.

- [ ] Write tests rejecting changed graph/cost/source/decoder/cursor/RNG, missingAdam, phaseoffbyone and unconfirmedterminalpass. Add uninterrupted/resumed next-assignment/update equality at completedupdates64and256.
- [ ] Run replay fixtures and a bounded live CUDA continuation pilot. Expect exact shared initial weights and uninterrupted/resumed tensors/owners; a changed pin must refuse resume, not silently restart.
- [ ] Implement A0–A3fixed-batch runs with the stated score grid,2,000primary/10,000extended ceilings,7,200-step-second cap, strict four-class gate, explicit GPU lock and source snapshot. Score a time-censored terminal sample and report unconfirmed terminal passes explicitly. Retain historicalA0; a historical curve is reusable only with exact inputs/recipe/decoder/nativeGTsource equivalence. Otherwise train a new matchedA0.
- [ ] At every sample run independent assignment/head/loss/gradient/proposal/export/native audits and exact trajectory replay. Retain sparse static overrides and A3per-update reserved vectors/cost-and-target digests, rebuilding full arrays during replay rather than duplicating full grids. Matching uses the actual loss forward's detached outputs; diagnostic passes must preserve model/Adam/RNG state. Record per-object positive churn, cost margins, clipping and measured update/frame-exposure/time brackets; record A3phaseactuallyreached.
- [ ] Close admitted fit or finite-negative cases independently, retaining full curves and artifacts. A failed fixed-batch case does not enter balanced16. Review this unit before promotion.

## Task5 / 41.5: Balanced16 signal and suppression attribution

**Files:** Extend`association/run.py`,`association/audit_worker.py`; create`association/test_admission.py` and suppression-probe fixtures. Reuse pinned V3 proposal/export/native metric interfaces without editing their source.

**Interfaces:** `admit_case(manifest: dict, case: dict, receipts: list[dict]) -> dict` returns engineering status, fit/censor status, class-complete curve, bracketedfit, per-object failure traces and evidence bindings. A balanced16case requires its treatment's admitted fixed-batch fit.

- [ ] Write admission fixtures rejecting missing/extraGTorframe, missingclass, alteredmetric, missingtargetreplay, pre-NMS-onlysuccess and nonconsecutivepassingterminal. Add two vertically separated exact boxes with overlappingBEV to demonstrate the unchangedNMSpath can suppress an ideal prediction.
- [ ] Run fixtures live; verify the annotation-only oracle bypasses NMS while the ideal-head probe exercises encode/V3decode/filter/top-K/NMS. Mark both probes as label-derived diagnostics, never model outputs.
- [ ] Train eligible A0–A3cases serially on the exact16frames with32,000updates/7,200stepseconds and fixed/confirmation scoring rules. Include matcher construction/solver time in synchronized step wall time; report its portion separately. Keep native scoring4hours and host4h5m distinct from training.
- [ ] Independently replay all assignments, native GT/export/metrics and complete trajectories at every sample. Trace all30originalmissing objects and newlymissedobjects through support,localization,score,top-K,NMS. Report per-class precision/recall/nativeAPH and finite failures without weakening the gate.
- [ ] Produce a matched decision table: correctness, fixed-batch/cohortfit, bracketedlearningcost, resources, confounds and needs-more-evidence limits. A query head or NMS change requires its own later specification. Review and retain this unit.

## Task6 / 41.6: Operator, tracking and durable closeout

**Files:** Complete`association/run.py`; create`association/close.py`,`association/test_run.py`,`association/test_retention.py`; add the separately versioned study to`research/experiment-registry.json` through its existing schema and corresponding tracking fixtures. Update the handbook's runnable status only after live operator admission.

**Interfaces:** CLI`list`, `prepare --run-id`, `run --run-id --treatment --tier`, `verify --run-id`; global`--cache-root`; explicit`--resume` for source-identical continuation. Run metadata lives at`<cache>/insula/association-runs/<run-id>/`; scientific outputs live in a distinct association namespace. `close_run(manifest, case_admissions, retention_receipts) -> dict` emits an independently bound comparison and closure status, never a held-out claim.

- [ ] Write operator fixtures for lockcontention,invalid/reusedrunID,changedsource,input/runtimehash,partialstage,timeoutdescendants,missingTier1admission and missingclass. Write retention fixtures refusing release on badupload/readback/recoveryhash or invalidreceipt and preserving source-pinned negative evidence.
- [ ] Run red→green fixtures live. Admit sourcefrozenprepare, boundedCUDApilot, independentverify and explicitresume; do not register unimplementedCLIcommands as runnable.
- [ ] Register planned/admitted stages through the existing tracker schema; verify projection distinguishes implementation failure, running, finite negative, unconfirmedpass and sustainedfit. Use existing journal API/CLI for evidence-bound hypotheses, observations, decisions and follow-ups; never edit deriveddashboard or append-onlyjournal bytes directly.
- [ ] Exercise one actual result bundle's HDFSupload/exactreadback/separateInsularecovery, then independently admit allretainedcontents and release only declared new local payloads under the existing15GiBcap. An unavailableHDFSsession blocks release; do not modify authconfiguration.
- [ ] Independently reconcile the whole study, tracker/journal entries and retained evidence. Update ticket41/handbook with verified outcomes and open held-out work; review the complete documentation/source diff. Land only ready, live-admitted units using the authorized main execution workflow.

## Documentation review completed for this plan

This plan maps the design's runtime, solver, target, geometry, loss/gradient, restart, native metric, suppression, retention and tracking requirements to41.1–41.6. It does not run them. Its proposed interfaces are absent until implementation; every checkbox remains open and generated tracking state is unchanged.
