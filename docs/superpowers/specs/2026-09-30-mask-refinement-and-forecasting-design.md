# Mask refinement and downstream forecasting research contracts

Date: 2026-09-30. Status: selected research directions; execution prerequisites below.

## Intent and confirmed choices

Establish independent detection and segmentation baselines, then test whether frozen detector-prompted masks add useful spatial information. Test downstream representation value through controlled forecasting before planning. These choices were approved in the discussion on 2026-09-30. They do not require reproducing every anchor paper or building a joint network first.

Perception is the primary sensor research suite. Motion forecasting uses its own Scenario records and supported historical sensor extensions. E2E and closed-loop planning are later suites. TensorFlow is excluded throughout acquisition, processing, training and evaluation. Torch is the verified SAM route; other encoders may use Torch/JAX. Waystone manages HDFS and bounded local materialization.

## Prerequisite gates

M0 proves the dedicated Insula itself works. M1–M5 then establish native data replay, mathematical geometry, sensor reconstruction, inspection and reproducible R0. Their acceptance contract is [live Insula verification](2026-09-30-live-insula-verification-design.md). Host tests or existing data acquisition do not close these gates.

The two acquired validation scenes are engineering fixtures. Never train or tune on them and then report their scores as held-out performance. Before scientific execution, record a versioned official train/validation cohort manifest, source identities, segment/scenario partitions, available supervision and sensor extensions, evaluator configuration, runtime identity and resource budget. Select numerical cohort and compute limits after resource inventory; no model training or checkpoint download is implied by this specification.

A GPU runtime needs its own live Torch/JAX device-computation and isolation gate. Checkpoint version/access, package closure and evaluator parity must pass before running the affected experiment. A GPU device listing alone is insufficient.

## P1 — Independent detection and segmentation baselines

Keep task results and models independent initially. The detection track starts with the PointPillars anchor; SWFormer and RSN are later controlled representation comparisons. The segmentation track retains native TOP point semantics and full-scene background/support. An RSN foreground selector cannot replace semantic supervision.

Detector-to-mask refinement requires a native **2D camera detector** baseline in addition to the LiDAR 3D detection track. Its predicted camera boxes provide spatial prompts and category identities. Projected ground-truth LiDAR boxes are not substitutes for predictions. Camera-only 3D detection and LET remain separate camera research contracts.

Record native label coverage, ignored regions and missing versus annotated-empty status. Establish TF-free evaluator behavior against pinned fixtures before calling exports benchmark-compatible. Detection reports native task AP/APH as applicable; point semantics reports class IoU/mIoU on eligible TOP points. Camera masks use explicitly mapped native camera segmentation support, not inferred correspondence between panoptic and box IDs.

Start encoder comparisons with current-frame inputs as a bounded proposed control. Historical context is a separately declared treatment, not an implicit addition to one encoder. The full temporal research scope remains open.

## P2 — Frozen predicted-box mask refinement

### Question and treatments

Does a frozen promptable segmenter improve spatial support beyond identical detector boxes, and does that improvement survive transfer to measured 3D points?

Use identical frozen detector predictions, score thresholds, image preprocessing and native category mapping in all treatments:

| Treatment | Spatial support | Purpose |
|---|---|---|
| B0 | Rectangle from predicted camera box | Prompt/source baseline |
| B1 | SAM mask from that predicted box | Frozen spatial refinement |
| B2 | SAM 3 mask in explicitly enabled spatial instance mode | Same-prompt model comparison |
| S0 | Independent native-label segmentation baseline | Task reference, with its own training budget |
| Oracle appendix | Ground-truth spatial prompts | Prompt-quality ceiling; excluded from main result |

Pin code and checkpoint identities. SAM 3 concept exemplars can retrieve all matching objects; they are not interchangeable with spatial instance prompts. SAM 3 concept discovery is a later, separately named experiment with a frozen phrase-to-taxonomy mapping. Do not silently use SAM 3.1 for a SAM 3 result.

### Data and geometry interface

Each prompt record carries source segment/frame/camera, predicted box in original image coordinates, detector class/score, prompt origin and preprocessing transform. Each mask artifact adds segmenter/checkpoint identity, prompt mode, candidate selection policy, confidence and source image hash. Keep predicted artifacts separate from native supervision.

Mask-to-point association consumes source point identity `(frame, laser, return, row, column)`, calibrated timing-aware projection, visibility/depth checks and explicit conflict rules. Output carries point identity, proposed class/instance support, mask identity, validity/conflict reason and provenance. Preserve all original points; unsupported and conflicting assignments remain unknown.

Use measured LiDAR only in the declared multimodal transfer treatment. A mask alone supplies rays, not metric depth or a 3D box. Predicted camera depth and oracle depth are distinct future controls; optical depth and radial range must remain distinct. Do not equate panoptic IDs, camera-box IDs and LiDAR-box IDs.

### Evaluation and decision

Report prompt coverage and false prompts, full end-to-end eligible-pixel class scores, and matched-object mask quality separately. Detector misses must count in the end-to-end result. For transfer, compare B0/B1/B2 using identical points, projection, visibility and class mapping; report eligible-point IoU, coverage and conflict counts. Evaluate on native labeled support and publish denominators. Stratify distance, occlusion and thin objects without selecting only successful prompts.

The primary scientific test is paired change in eligible-point semantic mIoU for mask versus box support, accompanied by coverage and camera-mask diagnostics. No gain may be attributed to masks when input evidence or eligible support differs. Resample whole segments for uncertainty; adjacent frames are not independent samples. Report effect sizes and uncertainty, including negative results. The engineering fixture cannot support this scientific conclusion.

Promotion to distillation or joint training requires a reproducible held-out benefit with acceptable measured runtime/memory under the preregistered budget. An inconclusive result does not become a joint-model implementation requirement.

Live gate: replay predicted prompts, mask inference and geometric transfer inside the locked GPU Insula; independently validate artifact identities, original-image coordinates, retained point identities, missing/conflicting assignments, deterministic candidate selection and complete timing. Include failed/checkpoint-mismatch inputs that prohibit promotion.

## F1 — Controlled forecasting utility

### Question and evidence contract

Do additional causal sensor-derived scene features improve future-agent forecasting beyond native historical tracks and maps?

Use Motion's own scenario IDs and version-supported corresponding sensor extensions. Never join acquired Perception scenes to Motion by timestamp or similar names. Camera-token extensions are not raw RGB, so SAM masks are not directly available there. This experiment tests the representation hypothesis with supported features; it does not automatically transfer P2 artifacts. Moving a Perception-trained encoder into Motion requires a separately verified compatible sensor adapter.

All observations must be available at or before `current_time_index`. Future track states are targets only. Store scenario ID, current index, actual feature timestamps, source extensions, feature/checkpoint identity and availability masks. A causal-access validator rejects future observations and sequence-refined/offboard teacher inputs presented as online measurements.

### Predictor and comparisons

Use a reproduced TF-free forecasting baseline informed by MTR or Wayformer. Select one implementation after dependency, input-interface and live-runtime audits; paper citations alone do not establish a runnable baseline.

| Treatment | Inputs | Interpretation |
|---|---|---|
| F0 | Native historical tracks + map | Strong common-input baseline |
| F1 | F0 + fixed LiDAR scene features | Added geometric evidence |
| F2 | F0 + supported camera-token features | Added appearance evidence |
| F3, later | F0 + fused scene features | Fusion beyond individual branches |

Keep forecast horizon, candidate count K, target agents, evaluator configuration and decoder capacity fixed. Compare on the same extension-eligible scenarios; additionally report availability over the full chosen cohort. Use explicit missing-feature masks rather than treating unavailable evidence as an observed empty scene.

A frozen-head probe measures immediate usability only when the trained baseline exposes a compatible feature interface; do not insert new arbitrary dimensions into a frozen model. The main learnable-value comparison uses matched retraining with identical seeds, optimization budget and decoder/interface capacity, including a no-extra-evidence adapter control. Representation construction and training costs are recorded separately. Oracle native tracks are a control, not a detector result. Predicted-track degradation is a subsequent error-propagation experiment.

### Evaluation and decision

Report official configured minADE, minFDE, miss rate and mAP-family results; lock horizon, K, target selection and probability handling. Use mAP as the preregistered primary metric and report the others as complementary outcomes. Report paired per-scenario effects, scenario-level uncertainty, class/distance/extension-coverage breakdowns and probability diagnostics. Any alternative primary selection is recorded before examining comparison results.

A forecasting gain establishes utility under this input and evaluator contract. It does not establish a better ego planner or closed-loop safety. Planning remains a distinct later contract with explicit simulator dynamics, reactive-agent assumptions and observation interfaces.

Live gate: run feature creation, causal-access validation, baseline and added-feature inference, export and TF-free scoring inside the locked Insula. Independently validate scenario/target identity, future-access rejection, candidate count, probability validity, missing-feature handling and evaluator fixtures. Scientific completion also requires the declared training/retraining and held-out runs; a small live smoke run proves only implementation.

## Deliverables and dependency order

1. Verified M0, then verified R0 and separate scientific cohort/evaluator/GPU readiness.
2. Independent native task baselines with exports, coverage reports and receipts.
3. P2 same-prompt mask comparison and controlled geometric transfer report.
4. F1 compatible Motion data/feature interface and reproduced forecasting baseline.
5. Paired forecasting feature study; then decide whether distillation, fusion, temporal memory or planning is warranted.

P2 and F1 can be investigated independently once their prerequisites exist; successful P2 is not a fabricated dataset correspondence for F1. Every implementation deliverable needs its own live receipt. Keep planned, implemented, awaiting-live and verified status distinct.

## Sources and decision trail

- [SAM mechanisms, controls and runtime review](../../../experiments/waymo-perception/research/sam-integration-pathways.md)
- [Native metrics and forecasting/planning review](../../../experiments/waymo-perception/research/scene-understanding-evaluation-pathways.md)
- [Geometry foundation](2026-09-29-perception-geometry-foundation-design.md)
- [Research program](2026-09-29-waymo-research-program-design.md)
