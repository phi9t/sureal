# Actionable research task index

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

User requested every planned idea. The concrete written design and implementation plan are approved for inline execution; the original sweep is closed. Native grouping/range caches and CPU module contracts are admitted; all8 actual-frame CUDA architecture gates passed; native fitting and full closure remain pending. Separate implementation/overfit tickets:

- [36: Fine/coarse grid grouping](../../docs/research/tasks/36-grid-resolution.md)
- [37: Ragged dynamic pillars](../../docs/research/tasks/37-ragged-pillars.md)
- [38: Within-pillar attention](../../docs/research/tasks/38-point-attention.md)
- [39: Range-to-pillar feature fusion](../../docs/research/tasks/39-range-fusion.md)
- [40: Sparse multiscale BEV transformer](../../docs/research/tasks/40-sparse-bev-transformer.md)

## Experiment tracking and journal

[Live tracker](research/experiment-tracker.md) records24 experiment definitions, goals, recipes, verifiers, acceptance and evidence-derived status. [Research journal](research/research-journal.md) separates observations, hypotheses, decisions and follow-up work. Registry and journal snapshots are retained on HDFS with exact readback receipts. [Tracking CLI](tracking/README.md) documents refresh, watch, note, verification and publication.
