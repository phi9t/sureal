# Actionable research task index

Current user override:[MAC happy path before comprehensive hardening](../../docs/research/2026-10-05-mac-happy-path-first.md).
[58](../../docs/research/tasks/58-mac-happy-path-perception-pilot.md) prioritizes
two bounded perception-preparation workers, useful artifacts, live functionality
checks and reviewed landing before complete MAC admission. Manual lead support
is explicit. This provisional use does not close scientific or MAC milestones.

The [remaining full-admission backlog](../../docs/research/task-queue.md#historical-full-admission-sequence-october-4-2026)
retains MAC50–54/53 and persistent-lead55–57 contracts. It does not block58
provisional use. Independently admitted models/training44–48 retain their
scientific dependencies;57 adds none. No new lead automation is accepted by
this index.

[Overall goal and evidence policy](../../docs/research/tasks/program-goal.md). One local task specification per ticket; core execution starts at 01. Tickets 01–06 are verified complete: [R0 evidence](research/r0-geometric-insula.md). Tickets 08 and 09 are also verified complete: [single-device Torch GPU runtime](research/gpu-runtime-verified.json) and [Perception evaluators](research/perception-evaluators-verified.json). Remaining core tickets are planned or preparing scientific readiness. Per-ticket files and linked candidate-specific receipts are authoritative; previous partial implementation/evidence does not automatically satisfy later gates. Conditional tickets require a later activation decision.

| Ticket | Deliverable | Blocked by | Lane |
|---|---|---|---|
| [01](../../docs/research/tasks/01-insula-runtime.md) | M0: prove the dedicated Insula runtime | — | core |
| [02](../../docs/research/tasks/02-native-replay.md) | M1: replay the complete native slice | 01 | core |
| [03](../../docs/research/tasks/03-geometry-math.md) | M2: verify the mathematical geometry foundation | 01 | core |
| [04](../../docs/research/tasks/04-sensor-reconstruction.md) | M3: reconstruct real calibrated sensors | 02, 03 | core |
| [05](../../docs/research/tasks/05-inspection-views.md) | M4: inspect range, BEV and camera scene views | 04 | core |
| [06](../../docs/research/tasks/06-r0-closeout.md) | M5: close the reproducible sensor-to-scene tracer | 02, 03, 04, 05 | core |
| [07](../../docs/research/tasks/07-scientific-protocol.md) | Freeze cohorts, budgets and statistical protocols | 06 | core |
| [08](../../docs/research/tasks/08-gpu-runtime.md) | Verify a locked GPU model runtime | 01 | core |
| [09](../../docs/research/tasks/09-perception-evaluators.md) | Verify TF-free Perception evaluation | 06 | core |
| [10](../../docs/research/tasks/10-pointpillars-detection.md) | Establish independent PointPillars detection | 07, 08, 09 | core |
| [11](../../docs/research/tasks/11-point-segmentation.md) | Establish independent point-semantic segmentation | 07, 08, 09 | core |
| [12](../../docs/research/tasks/12-swformer-comparison.md) | Compare pillar encoding with SWFormer mechanisms | 10 | core |
| [13](../../docs/research/tasks/13-rsn-range-study.md) | Evaluate the RSN range-view pathway | 10 | core |
| [14](../../docs/research/tasks/14-camera-box-mask-baselines.md) | Establish camera box and semantic baselines | 07, 08, 09 | core |
| [15](../../docs/research/tasks/15-camera-3d-let.md) | Establish camera-only 3D and LET evaluation | 07, 08, 09 | core |
| [16](../../docs/research/tasks/16-r4d-distance.md) | Investigate reference-object distance estimation | 15 | core |
| [17](../../docs/research/tasks/17-sam-mask-refinement.md) | Compare frozen SAM spatial refinement | 14 | core |
| [18](../../docs/research/tasks/18-mask-to-lidar.md) | Test geometry-aware mask transfer | 17, 11, 04 | core |
| [19](../../docs/research/tasks/19-motion-ingestion-evaluation.md) | Verify Motion ingestion and forecasting evaluator | 06 | core |
| [20](../../docs/research/tasks/20-motion-baseline.md) | Establish tracks-and-map forecasting reference | 07, 08, 19 | core |
| [21](../../docs/research/tasks/21-forecast-feature-study.md) | Measure sensor-feature forecasting utility | 20 | core |
| [22](../../docs/research/tasks/22-program-synthesis.md) | Close the core program with an evidence-backed decision | 12, 13, 16, 18, 21 | core |
| [23](../../docs/research/tasks/23-sam-concept-discovery.md) | Evaluate SAM 3 concept discovery | 17 | conditional |
| [24](../../docs/research/tasks/24-teacher-distillation.md) | Test camera-teacher to LiDAR-student distillation | 18 | conditional |
| [25](../../docs/research/tasks/25-joint-multimodal-model.md) | Test a joint multimodal detector and segmenter | 10, 11, 14, 18 | conditional |
| [26](../../docs/research/tasks/26-temporal-uncertainty.md) | Test temporal memory and uncertainty | 11, 18 | conditional |
| [27](../../docs/research/tasks/27-planning-contract.md) | Specify and verify the next planning study | 21 | conditional |

## Current execution order for remaining data gates

Training-box replay has independently admitted all64 training sources:
[full64 receipt](research/training-box-full64-replay-verified.json).
Semantic recovery is complete; the separately live-audited aggregate reconciles
all103 scenes and478,579,462 eligible point labels:
[full103 semantics](research/scientific-semantic-full103-verified.json).
Native shape recovery independently admitted203,850 return records across103
scenes; its aggregate is a host rehash of the individual live admissions:
[shape evidence](research/scientific-native-shape-full103-retained-audit.json).
A separate live aggregate audit reconciles all103 camera lifecycles, including
the pilot and both recovered gaps:
[camera evidence](research/scientific-camera-full103-verified.json).

The full-support point-to-native-grid replay has admitted all103 selected scenes,
203,850 return records,3,513,295,187 points and478,579,462 eligible semantic
points. The [retained aggregate](research/point-grid-full103-and-overfit-box-retained-audit.json)
is a host rehash of the individually independent live admissions. Current
receipt hashes and summed denominators were rechecked on2026-10-02; this does
not claim a new live aggregate audit or model quality.
These data gates supply ticket07's evidence; they do not close its protocol.
Next freeze scientific model configurations, training-only anchor choices,
sampling and loss rules, overfit acceptance thresholds, resource budgets and
comparison decisions before optimization. Camera geometry/visibility rules and
causal Motion ingestion require their own task-specific evidence.
Detection, segmentation, camera and Motion training, controlled held-out
comparisons, uncertainty/resource reports and synthesis decisions remain required
by the original program goal. Engineering receipts do not replace those outcomes.

## First-tier model development gate

Every model architecture begins with the [fixed-batch overfit verifier](research/tier1-batch-overfit-verifier.md): task-appropriate native quality, full support/masks, independently live-checked inference/export, and bracketed time/update-to-fit with resource/evaluation overhead. Successful loss minimization alone does not pass. Historical first-frame diagnostics lacked cyclists. Ticket35 now uses a separately admitted all-class frame and the corrected periodic-heading verifier; its matched sweep is closed with all15 treatments passing and the cap control proven. Segmentation and forecasting tickets must declare their own fixed-batch metric/coverage thresholds under ticket07 before training, preserving their independent task contracts. This gate precedes tiny-cohort and heldout experiments.

## Architecture directions (authorized2026-10-02)

[Study spec](../../docs/superpowers/specs/2026-10-02-perception-architecture-study-design.md) and [execution plan](../../docs/superpowers/plans/2026-10-02-perception-architecture-study.md). Tickets28–32 cover pillar encoders, BEVbackbones, retention/grid, range/pointattention, and fullclass/heldoutpromotion. Firstcohort runs independent deeperPFN/contextPFN/residualBEV variants, then64pointretention. Every milestone requires liveInsula plus separate replay/admission; none closes the original detection/segmentation/forecasting goals on a single batch.

## Balanced all-class fitting continuation

[33: balanced cohort fitting](../../docs/research/tasks/33-balanced-cohort-fitting.md) defines the matched baseline/residual experiment and native promotion gate. Both2000-update runs passed exact16-frame checkpoint/Adam replay and48 independent loss equations; their independently audited final native scores fail the all-class gate. All three checkpoint audits are complete; [comparison results](research/balanced16-fitting-results.md) close ticket33 with a negative result. [34: rare-class learning diagnosis](../../docs/research/tasks/34-rare-class-learning-diagnosis.md) defines the next controlled investigation. Data coverage is stronger, but it does not establish detector readiness or close the original research program.

## All-class single-batch sweep

[35: fixed-batch fitting sweep](../../docs/research/tasks/35-all-class-single-batch-sweep.md) runs all15runnable training treatments plus a cap-equivalence control on one all-class frame. All15 treatments passed sustained all-class native overfit with exact full-trajectory/model/Adam/RNG replay. Terminal cap equivalence and final live Insula closure passed; [closed comparison](research/tier1-overfit20261002b-results.md) and [full curves](research/tier1-overfit20261002b-results.json) are authoritative. Versioned decoderV3 repairs a proven periodic-heading correction defect; preserve and distinguish historicalV2 scores. Full-cohort/heldout promotion and the original research goals remain open.

## Expanded fixed-batch architecture scope

User requested every planned idea. The concrete written design and implementation plan are approved for inline execution; the original sweep is closed. Native grouping/range caches, CPU module contracts and all8 actual-frame CUDA gates are admitted. The independent full closure now reconciles384 stage receipts: seven cases sustain fitting, while the sparse transformer has a valid negative result at10,000 updates. Held-out comparisons remain open. Separate implementation/overfit tickets:

- [36: Fine/coarse grid grouping](../../docs/research/tasks/36-grid-resolution.md)
- [37: Ragged dynamic pillars](../../docs/research/tasks/37-ragged-pillars.md)
- [38: Within-pillar attention](../../docs/research/tasks/38-point-attention.md)
- [39: Range-to-pillar feature fusion](../../docs/research/tasks/39-range-fusion.md)
- [40: Sparse multiscale BEV transformer](../../docs/research/tasks/40-sparse-bev-transformer.md)

## Experiment tracking and journal

[Live tracker](research/experiment-tracker.md) records24 experiment definitions, goals, recipes, verifiers, acceptance and evidence-derived status. [Research journal](research/research-journal.md) separates observations, hypotheses, decisions and follow-up work. Registry and journal snapshots are retained on HDFS with exact readback receipts. [Tracking CLI](tracking/README.md) documents refresh, watch, note, verification and publication.

## First-class models and training workstream

The user selected first-class `sureal/models/` and `sureal/training/`, starting with duplicated fixed-frame producers while preserving the specialized sustained loop. [Design proposal](../../docs/superpowers/specs/2026-10-03-first-class-models-training-design.md) and [research work guide](../../docs/research/README.md) define the scope. Implementation remains gated by written design/plan review, active implementation closeout and fresh live admission. These supporting tasks do not close the original scientific comparisons.

| Ticket | Deliverable | Blocked by |
| --- | --- | --- |
| [44](../../docs/research/tasks/44-models-training-reference-admission.md) | Frozen reference and independent migration comparison admission | Review gates, admitted local protocol 53 |
| [45](../../docs/research/tasks/45-first-class-models-and-layers.md) | Installed scientific models, neural layers and equivalent detector assembly | 44 |
| [46](../../docs/research/tasks/46-first-class-training-policy-and-state.md) | Losses, optimizer policy and explicit checkpoint formats | 45 |
| [47](../../docs/research/tasks/47-shared-fixed-frame-producer.md) | One maintained fixed-frame producer and thin experiment adapters | 46 |
| [48](../../docs/research/tasks/48-models-training-retention-and-closeout.md) | Discoverability, HDFS recovery evidence and landed closeout | 47 |

[Queue policy](../../docs/research/task-queue.md) records scheduling responsibilities. Existing numbered task files define acceptance; experiment state remains evidence-derived. Preserve the prior approved research order and active frozen packages during migration.

## Sureal-local two-worker collaboration protocol

After the current worker's full owned integration closeout and a verified pristine `phi9t/mainline`, the user selected a minimal local lead–worker protocol before models/training migration. Corenius is a design reference; no Corenius implementation or runtime is required. [Design proposal](../../docs/superpowers/specs/2026-10-03-sureal-serial-collaboration-design.md) and [queue policy](../../docs/research/task-queue.md) preserve existing scientific evidence and execution contracts.

| Ticket | Deliverable | Blocked by |
| --- | --- | --- |
| [49](../../docs/research/tasks/49-collaboration-project-admission.md) | Pristine canonical base, local records and exclusive controller lock | Current closeout, written design/plan review |
| [50](../../docs/research/tasks/50-collaboration-worker-attempts.md) | Two concurrent sessions in distinct owned worktrees | 49 |
| [51](../../docs/research/tasks/51-collaboration-candidate-verification.md) | Exact immutable candidate submission, verification and repair | 50 |
| [52](../../docs/research/tasks/52-collaboration-landing-recovery.md) | Conditional exact fast-forward landing and recovery | 51 |
| [53.0](../../docs/research/tasks/53-0-collaboration-retention-cleanup-foundation.md) | Landed retention/cleanup and pilot-check foundation | 52 |
| [54](../../docs/research/tasks/54-worker-program-observability.md) | Worker summaries, state graphs and queue/spec overview | 49–52; landed53.0 |
| [53](../../docs/research/tasks/53-collaboration-cleanup-closeout.md) | Retained evidence, concurrent pilot and stale-candidate refresh | 52; 54 |

## Persistent lead and human-steering reduction

[Written design](../../docs/superpowers/specs/2026-10-04-persistent-research-lead-design.md).
All three tickets have P0 priority and preserve the MAC controller as effect
authority. Drafting/review can proceed before53; implementation waits for its
independent closeout and new written-spec/plan admission.

| Ticket | Goal and deliverable | Execution blocked by |
|---|---|---|
| [55](../../docs/research/tasks/55-lead-authority-action-policy.md) | Explicit authority and deterministic next-action eligibility | 53; reviewed landed spec/plan |
| [56](../../docs/research/tasks/56-persistent-lead-execution.md) | Automatic dispatch/continuation/repair/verification/landing with recovery | 55 |
| [57](../../docs/research/tasks/57-lead-human-toil-acceptance.md) | Clear decisions and zero required routine human prompts in the live pilot | 56 |

All implementation milestones require independent live Insula receipts. These tickets are specified, not completed. Stage order is pristine mainline → 49–52 → 53.0 → 54 → 53 → models/training44–48; no historical worktree or frozen scientific artifact is discarded by adopting that order.

## Motion native source pilot progress (2026-10-03)

Separate generation-pinned training/validation shards and extensions are HDFS-mirrored and independently live-inventoried. Native filename-key linkage,11-step causal prefixes, future/key/duplicate refusal and observation-only camera codebook features pass for both selected pilot IDs. [Native oracle metric handoff](research/motion-real-metric-handoff-verified.json) matches separately derived errors/counts and rejects corruption. These oracle diagnostics are not baseline forecasts. Native LiDAR decoding/calibrated XYZ, camera codebook lookup and fresh foundation/evaluator replay now have separate live evidence. Ticket19 aggregate acceptance/closeout remains open; tickets20/21 still require their independent scientific protocol/model/held-out comparisons. The training raw shard is locally evicted with exact HDFS recovery proof; selected truth and causal slices remain local.

## Expanded closeout and current fitting gates (2026-10-03)

Tickets36–40 have independently verified fixed-batch closeout: seven treatment/control cases sustain fitting, and the transformer has a valid10,000-update negative result. All384 stage receipts are reconciled. [Expanded HDFS retention](research/advanced-expanded20261002a-hdfs-retention-index.json) preserves every payload; the [native input-cache retention](research/native-cache-hdfs-retention-status.md) makes the two-GiB pilot reservation possible without removing historical model cases. These engineering closures do not close tickets10–22.

The original balanced16 baseline0/19/35 GPU pilot ended at a confirmed600-second native score35 timeout, with19of21 gates admitted. Exact restart/full0→35 trajectory, all16 heads, literal losses, proposals and full native GT pass through35. A separately pinned scoring-only recovery now passes all21 stages, including independent native metric replay. A separately mounted GPU transition verifier also passes19→35 exact state and all16 heads. Pilot HDFS retention and pilot-only local release are complete:57 files /1,242,670,817 bytes across25 chunks, with75 live archive/verify/recovery stages and a separate whole-union admission rejecting5 corrupt copies. Fresh host reconciliation restores2,872,821,397 free scientific-storage bytes. Sustained-controller/rolling-retention admission and the four optimization cases remain open. The user-authorized scoring default is now4hours per native invocation (host4h5m), distinct from the unchanged2-hour training budget; active frozen recovery retains its earlier bound. [Ideal coverage controls](research/balanced16-coverage-oracle-status.md) independently show29ROI signs without positive anchors: perfect covered-target sign predictions score0.759399 under unchanged full native GT. Assignment/grid/support diagnosis remains part of ticket34; loss weighting is not a substitute for missing target supervision.

## Rolling checkpoint HDFS interface (2026-10-03)

The checkpoint-only publisher now has [actual live retention evidence](research/sustained-checkpoint-hdfs-closeout-reconciled.json):19 original admitted checkpoint files /411,001,906 bytes,8 HDFS chunks,24 live archive/verify/recovery stages, exact global readback and independent full-union admission with5 corrupt-copy refusals before checkpoint-only release. The source/identity/path preparation passes85 live CPU tests. This proves the arbitrary-step storage interface on the original35-update checkpoint; no new model updates or scores were generated. The four-case controller, keep-two/retire-older orchestration, native extended trajectories and all scientific comparisons remain open.

## Prediction–target association study (specified 2026-10-03)

[41: association and supervision coverage](../../docs/research/tasks/41-prediction-target-association.md)
is a dedicated follow-up under ticket 34. The [design](../../docs/superpowers/specs/2026-10-03-prediction-target-association-design.md),
[implementation plan](../../docs/superpowers/plans/2026-10-03-prediction-target-association.md)
and [experiment handbook](research/prediction-target-association-study.md) specify
A0 legacy, A1 globally covered nearest-BEV ownership, A2 3D-aware matching and
A3 detached prediction-dependent matching. Each work package has live Insula
verifiers and acceptance criteria. The target gate requires all 1,053 eligible
balanced16 objects covered; native evaluation retains all 1,279 GT boxes.
Fixed-batch fitting precedes balanced16, with the unchanged sustained all-four-class
APH >=0.8 gate. HDFS exact recovery precedes any declared local release.

Status is specified, not implemented or runnable. This documentation update does
not register runs, alter active four-case optimization controls, change historical
targets, update generated tracking/journal state or claim new execution evidence.
Positive quota, object-balanced loss, NMS and query-head changes are conditional
follow-ups with separate controls; held-out and broader program goals remain open.

## Separate target-coverage follow-up

[Ticket41 — prediction–target association](../../docs/research/tasks/41-prediction-target-association.md) is the existing authoritative study for the independently observed missing-target problem. Its numerical design, six implementation gates and A0–A3 treatments cover ownership, geometry and detached prediction-aware matching. It is specified only; the active sustained16 optimization recipes keep their original assignment unchanged. No second ticket41 is created.

## User-approved initial-experiment investigation priorities

Keep compact pillar/dense-GN CNN and clipped Adam as reference; complete the active four-recipe sustained16 controls unchanged. [42: object failure ledger](../../docs/research/tasks/42-object-failure-ledger.md) specifies measurement/assignment/geometry/ranking/suppression/native-match evidence. [43: frozen normalization diagnostic](../../docs/research/tasks/43-frozen-normalization-diagnostic.md) tests pillarBN state with frozen weights and identical full-native-GT decoding before any separate pillarLN treatment. Existing41 isolates supervision ownership/geometry. Residual/masked pooling and controlled point attention form the initial follow-up shortlist; range and sparse mechanisms remain exploratory. Scientific promotion requires held-out multiseed quality/resource evidence; one-frame saturation and historical reanalysis are not adoption.
