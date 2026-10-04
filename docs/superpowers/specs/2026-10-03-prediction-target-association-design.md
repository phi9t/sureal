# Prediction–target association study

Status: specified; implementation and training evidence are pending. User requested this specification and experimentation-document update after reviewing the public-research and first-principles recommendation. This document does not change an active run, historical recipe, target cache, evaluator, or experiment registry.

## Goal and research decision

Give every training-eligible object distinct, geometrically plausible prediction responsibility, then establish whether improved association reduces updates/time to sustained native detection fit. Separate assignment correctness from model fitting and held-out benefit. The first deliverable is a coverage-preserving matcher on the existing dense head, not a new backbone.

The engineering goal is zero uncovered targets among the 1,053 eligible objects in balanced16, with independently reconstructed ownership, targets and coverage. The fitting goal is native LEVEL2 APH >=0.8 for each of vehicle, pedestrian, sign and cyclist at two consecutive scored checkpoints, including terminal, against unchanged full native GT. Scientific adoption additionally requires a later frozen, segment-disjoint, multi-seed held-out comparison; this study alone cannot establish it.

Parent: [ticket 34](../../research/tasks/34-rare-class-learning-diagnosis.md). Study ticket: [41](../../research/tasks/41-prediction-target-association.md). Execution: [implementation plan](../plans/2026-10-03-prediction-target-association.md). Operator entry: [experiment handbook](../../../experiments/waymo-perception/research/prediction-target-association-study.md).

## Measured problem and provenance

The independently live-replayed [coverage controls](../../../experiments/waymo-perception/research/balanced16-coverage-oracle-status.md) and [literal cause audit](../../../experiments/waymo-perception/research/balanced16-coverage-causes-verified.json) establish:

- Native evaluation retains 1,279 boxes. Training eligibility remains 533 vehicles, 255 pedestrians, 231 signs and 34 cyclists, totaling 1,053; existing assignment covers 533/254/202/34.
- All 30 uncovered objects have positive maximum nearest-BEV overlap. In 28 cases another GT wins every maximizing anchor by strictly higher overlap; two signs lose ties. There are 27 sign-to-sign, two sign-to-vehicle and one pedestrian-to-pedestrian conflicts. Class restriction alone does not repair 28 same-class conflicts.
- `pipeline/anchor_assignment.py` marks a best-for-some-GT anchor positive, but uses the anchor's independently computed `argmax` owner to construct its target. Positivity and ownership are inconsistent with an every-object coverage contract.
- Ideal covered-target predictions yield sign APH 0.759399; ideal predictions of all eligible ROI objects yield 0.868421 under the same full native GT. These bypass model/NMS errors and are not a mathematical ceiling on unconstrained detector predictions.
- Inspection of recorded winner pairs finds 25/30 center-height separations greater than 0.5m. The study must reproduce this derived count; it suggests a 3D geometry treatment, not proof of the cause of every conflict.

The current lattice has 256x256 cells at 0.5m spacing, eight templates per cell, and 524,288 slots. Each slot predicts all four classes and one 7-DoF box; template class metadata does not impose a hard class restriction. Native boxes use center-Z. The representative sign template includes a roughly 0.094m dimension, so strict center-inside and IoU-only selection can be restrictive; this is a geometric inference, not a measured ATSS result.

## First-principles contract

For binary reservation edges x[a,g], solve minimum total cost subject to at most one object per prediction slot and exactly one reserved slot per eligible object. Reserve coverage globally, then add positives without overwriting reservations. One box output must never regress multiple objects. Do not greedily repair an uncovered object by stealing another object's only positive.

Coverage is conditional on candidate-graph feasibility. A large total slot count is insufficient: every object subset needs at least as many collective candidate slots as objects. Emit maximum-cardinality matching and deficient-cluster diagnostics before optimizing cost. If the bounded graph remains infeasible, report a candidate/capacity failure; never hide GT or assign arbitrary remote slots.

Coverage does not establish measurement support, useful gradients, localization, score ranking, NMS survival, or generalization. Those require separate verifiers. Training association, inference suppression and the official metric's matching are different contracts.

## Fixed comparison and treatment matrix

All values below are preregistered starting recipes, not claims of optimal settings. A parameter change creates a new manifest/configuration ID and a matched control; never retune a failing case in place.

| ID | Treatment | Controlled question |
| --- | --- | --- |
| A0 `legacy` | Current nearest-BEV matcher and loss | Reproduce current coverage, ownership and native fitting behavior. |
| A1 `coverage_bev` | Global one-per-object reservations using current overlap geometry; retain legacy positives on unreserved slots | Does preserving object ownership improve fitting? |
| A2 `coverage_3d` | A1 with a declared center/size/3D-overlap reservation cost | Does height-aware geometry improve the quality and learnability of matches? |
| A3 `coverage_prediction` | A2 warm-up followed by detached prediction-dependent reservation costs | Does adapting ownership to current class/box quality improve fitting time? |

The legacy extra-positive policy, negative/ignore policy, native eligibility, model, initialization, measurements, head lattice, box coder, loss equations/normalization, optimizer and corrected V3 decoder stay fixed across A0–A3. Reserved slots override their legacy label/owner and become positive. For unreserved slots preserve legacy label/owner exactly, including forced legacy positives. Recompute residual/direction targets from final ownership. Report changed positive counts, owner changes and background normalizers as effects of this ownership treatment, not hidden loss changes.

Follow-ups are conditional, outside the initial executable matrix: A4a changes extra-positive quota only; A4b changes per-object positive-loss normalization only; A5 changes NMS only; A6 introduces a query head. Each requires its own frozen values, control and live gates before registration. Do not combine these changes with A1–A3.

## Candidate graph and deterministic reservations

Build one prediction-independent graph per frame and freeze it for A1–A3. Map each GT center to its nearest head-cell center; exact half-cell ties use the smaller row/column. Initial candidates are all eight slots in the clipped Chebyshev-radius-one neighborhood plus every legacy positive slot already owned by that GT. Include zero-overlap local alternatives so thin geometry cannot eliminate all edges. If matching is incomplete, expand the affected connected component through radius two, then three; additions can merge components, so recompute feasibility. Keep previously admitted edges. If radius three is still deficient, stop that frame with explicit failure. This physical bound is 1.5m in cell-center offsets, plus the center quantization offset; inherited legacy positive slots outside it remain declared exceptions.

Canonicalize GT by stable source object ID and candidate anchors by original flattened slot index; retain a `canonical_to_input` GT index mapping. Internal edge, reservation and target indices refer to canonical GT order. Translate legacy indices when validating a permuted fixture; producer cost/target callers supply canonically ordered GT boxes. Permutation checks compare canonical arrays and owner object IDs, not raw input positions. IDs are used only for reproducible training bookkeeping, never as model inputs. Pin the solver/library/runtime and require permutation tests plus repeat-run equality. For tied optimum costs, compare canonical outputs; the independent oracle also checks minimum total cost and constraints. Use float64 costs and finite validated edges; absent edges are forbidden, not merely high-cost alternatives. Reject duplicate IDs, invalid boxes, nonfinite costs and out-of-range indices. Empty GT produces the original all-background result.

Use a rectangular integer assignment solver on the candidate union, not all 524,288 columns. SciPy `linear_sum_assignment` is the production solver choice. Its exact installed version is bound by the source/runtime manifest. The Torch training process calls this CPU solver directly on detached candidate costs; the solver must therefore be present in the locked Torch runtime as well as the CPU preparation runtime. If absent in either root, admit a separately versioned execution root under ticket 01 before use; do not install into or mutate an active root. All A0–A3 runs use the same admitted training root, so a runtime change cannot be hidden in a matching comparison. A separate bounded exhaustive oracle provides implementation independence on fixtures.

## Reservation costs

Let q[a,g] be the unchanged nearest-BEV IoU. A1 cost is 1-q, with no added center, height, class or learned term. The graph makes zero-overlap local alternatives available, but their use and encoded residuals must be reported; structural coverage alone cannot promote such a match as useful.

For A2, compute the six existing encoded center/size residuals between GT and the static anchor: XY offsets divided by anchor BEV diagonal, Z offset divided by anchor height, and log L/W/H ratios. Let D be their mean absolute value. Use C2 = D + (1 - rotated_3d_iou(anchor, GT)), coefficients 1.0/1.0. Independently verify center-Z, rotation, positive dimensions and boundaries. Distance remains informative when overlap is zero. The rotated overlap is a matching cost only; it does not replace the model's existing regression loss or official evaluator.

For A3, use C3(t) = (1-alpha(t))*C2 + alpha(t)*Cpred. Alpha is zero through completed update 64, linear from 64 to 256, and one from update 256 onward; matching for the next update uses the completed-update count. If a case stops before alpha reaches one, explicitly record that it did not test the fully prediction-dependent phase.

Compute Cpred from detached current outputs: the full sigmoid-focal classification cost for assigning the GT class minus the all-background focal cost, plus 2.0 times the existing seven-component SmoothL1/sine localization cost, plus 0.2 times direction CE, plus 1.0 times (1 - predicted rotated 3D IoU). Use the existing alpha/gamma, SmoothL1 beta and canonical direction rule. Compute classification from finite logits using stable BCE, not an unstable probability logarithm. Decode predicted boxes with corrected V3 heading before IoU. Invalid/nonfinite decoded geometry fails the stage; no silent clipping, edge pruning or GT dropping. Record each cost term's distribution and match margins. These weights align the initial experiment with existing loss units; later coefficient sweeps are separate treatments.

Reservations in A3 may change at each optimizer update; the candidate graph and extra-positive policy remain fixed. Use detached outputs from the same training forward pass that supplies the loss; an extra training forward for matching must not update BN state or consume RNG. Checkpoint replay includes pre-update outputs, completed update, alpha, graph identity and assignment arrays, not just model/Adam state. A3 resume must recreate exactly the uninterrupted next assignment and update.

## Frozen optimization, evaluation and budgets

Use the admitted GN8 BEV baseline with original pillar BN, seed17, unchanged packing/head/templates, FP32, TF32 off and deterministic algorithms. Verify identical initial model tensors across A0–A3. No augmentation. Adam lr1e-4, betas(.9,.999), eps1e-8, wd0, foreachFalse; clip10. Keep original focal, box and direction losses and their positive-count normalization. No GT IDs, NLZ, annotation masks or label-derived values in observation features. TensorFlow forbidden; model work uses Torch. NumPy/SciPy and official C++ metrics run in independently locked roots.

First run each case on ticket35's fixed 73-eligible-object/all-class frame. Score updates 0,25,50,100,200,300,500,750,1000,1500,2000,3000,4000,6000,8000,10000, stopping on an admitted consecutive passing pair. The primary ceiling is 2,000 updates; continue the same trajectory to 10,000 if needed, within 7,200 synchronized training seconds. Score a time-censored terminal sample even if it lies between scheduled checkpoints; such an extra terminal pass alone cannot confirm fitting. Preserve all native GT for evaluation, independently of the 73-object training scope. A finite negative is an admitted diagnostic, not permission for balanced16 promotion.

Only a case passing the fixed-batch gate proceeds to the exact admitted sixteen balanced frames, deterministic round-robin one-frame updates. Maximum32,000 updates or7,200 synchronized training seconds per case. Score at0,1000,2000,4000,8000,12000,16000,24000,32000; after the first pass, score a confirmation1,000 updates later unless the next fixed sample is earlier. Stop at two consecutive passes including terminal or a finite cap. Preserve terminal scoring and distinguish time/update censoring and unconfirmed terminal passes. Keep all1,279 native GT; training eligibility and their ordered IDs remain unchanged.

GPU training is serial under the existing shared architecture-experiments lock. Caps: allocated GPU8GiB, processRSS16GiB, raw staging2GiB, scientific unique-inode payload15GiB; reserve2GiB for one active case. Synchronized training seconds are step wall time from pre-forward synchronization through matching, backward, optimizer update and post-update synchronization; include CPU solver time inside the update. Native scoring:14,400 seconds per invocation, host watchdog14,700 seconds, separate from the7,200-second training budget. Record each budget separately. Do not mutate the running optimization controls or reuse their checkpoint under a changed assignment contract.

Retain versioned source/input/runtime/manifests, graphs, assignments, native outputs, curves, terminal model/Adam/RNG and verifier receipts. Reuse admitted legacy arrays read-only and serialize static reservation overrides plus complete reconstructed-array hashes; do not duplicate every full target grid per treatment. Each A3 update retains reserved slot/owner vectors, completed update, alpha, cost/assignment digests and graph/source identity. Reconstruct complete targets and cost arrays during independent trajectory replay; do not persist a 524,288-slot target grid per update. Declare serialized sizes and replay/reconstruction rules in the storage reservation before training.

Large artifacts use the admitted Waystone HDFS upload, exact readback and independent live recovery/admission before any declared local release. HDFS failure keeps local bytes and blocks budget-exceeding next work. Do not modify HDFS auth configuration or existing archives as part of implementation. The existing current runtime/retention gates must be valid for each new frozen source snapshot.

## Live gates, acceptance and diagnostics

Every implementation milestone runs actual locked Insula workers and obtains a separate admission receipt. Host-only tests, producer assertions and documentation are not live evidence. A newly versioned runtime first proves M0; existing runtime receipts must still match its immutable identity.

1. **Contract and solver:** CPU Insula fixtures for ownership conflicts, same-class overlap, equal costs, input permutations, empty GT, invalid/nonfinite inputs, isolated targets, insufficient slots and bounded expansion. A separate exhaustive solver verifies tiny-graph maximum cardinality and minimum cost. Corrupted owner/class/target and graph/hash copies must be refused.
2. **Real targets:** independently reconstruct all legacy labels/indices for524,288 slots on each of16 frames and reproduce the30 uncovered IDs. For A1–A3 verify every final label, owner, residual, direction and mask; zero uncovered among1,053 eligible objects, no shared reservation, preserved eligibility and exceptions reported. Count height separation and report retained physical point support independently of matching.
3. **Coverage oracle:** annotation-only predictions of assigned eligible objects must reproduce the admitted ROI control against all1,279 GT: APH vehicle0.917384,pedestrian0.947955,sign0.868421,cyclist0.918919 within1e-6, with exact native object/box/export reconciliation. This bypasses decoder/NMS and proves coverage only.
4. **Actual loss/gradients:** live Torch forward/backward on the admitted frame; independently reconstruct focal/localization/direction equations and selected gradient fixtures. Report positives/object/class, positive and negative focal terms, normalizers, clipping and per-class gradient norms. Diagnostic passes must leave the producer model/Adam/RNG state unchanged, verified before/after. In A3 measure same-frame per-object positive-set churn and reservation-owner changes; avoid an all-slot percentage dominated by background.
5. **Optimization/replay:** exact initial weights and complete sampled head/model/Adam/RNG replay, including A3 assignments/warm-up state; uninterrupted/resumed equality. Report sampled update/frame-presentation/time-to-fit brackets, synchronized GPU time, cost/solver time, scoring/audit/HDFS overhead and resource maxima. Shared-GPU timings are observations, not isolated throughput measurements.
6. **Native predictions and suppression:** independently replay V3 decode, score floor, top-K, BEV NMS, source/measurement/GT metadata, protobuf exports and official native metrics. Per-object traces distinguish no assignment, weak input support, localization error, low score, top-K loss and NMS suppression. An annotation-derived ideal-head probe exercises encode/decode/filter/NMS separately and never counts as a model prediction or coverage-oracle pass.
7. **Closure/retention:** receipt hashes, whole-run class-complete curves, negative/censored outcomes and HDFS exact recovery are admitted independently before a case closes. A fit pass needs all four classes >=0.8 at two consecutive scored checkpoints including terminal. Scientific adoption remains open until separately frozen multi-seed held-out evidence exists.

## Public research and limits of transfer

| Primary source | Transferable idea | Limitation or implication for this study |
| --- | --- | --- |
| [ATSS](https://arxiv.org/abs/1912.02424), [official assigner](https://github.com/sfzhang15/ATSS/blob/master/atss_core/modeling/rpn/atss/loss.py) | Per-object adaptive overlap thresholds and local candidates | Center-inside gating and per-anchor conflict resolution need independent coverage checks; do not copy 2D geometry onto thin 3D signs without measurement. |
| [FreeAnchor](https://arxiv.org/abs/1909.02466) | Candidate bags and classification/localization likelihood | A distinct objective; not the first ownership-only control. |
| [TOOD](https://arxiv.org/abs/2108.07755) | Joint confidence/localization quality for positives | Useful later extra-positive selection; its 2D exponents are not frozen here. |
| [OTA](https://arxiv.org/abs/2103.14259) | Global foreground/background transport | Our inference: positive continuous mass does not guarantee a positive anchor after largest-mass hard decoding. |
| [YOLOX](https://arxiv.org/abs/2107.08430), [SimOTA code](https://github.com/Megvii-BaseDetection/YOLOX/blob/main/yolox/models/yolo_head.py#L506) | Adaptive positive counts and prediction-dependent costs | Our code inference: min-one candidate selection precedes conflict resolution, which has no coverage repair. |
| [DETR](https://arxiv.org/abs/2005.12872) | Global distinct prediction ownership | Full coverage requires sufficient feasible slots. Matching can be used with the current convolutional backbone. |
| [TransFusion](https://arxiv.org/abs/2203.11496), [3D matcher](https://github.com/XuyangBai/TransFusion/blob/master/mmdet3d/core/bbox/assigners/hungarian_assigner.py) | Class, normalized BEV center and3D-overlap costs; 3D query-head reference | Cost scale can affect convergence. This is an adaptation, not a reproduction or evidence of camera-fusion benefit here. |
| [DN-DETR](https://arxiv.org/abs/2203.01305) | Matching instability diagnostics and auxiliary denoising | Measure churn now; denoising needs a separate training-only input contract. |
| [Hybrid Matching](https://arxiv.org/abs/2207.13080), [DEIM](https://arxiv.org/abs/2412.04234) | More useful supervision alongside one-to-one ownership | One reservation may still be insufficient for fast learning. Auxiliary branches or image augmentation are separate changes, not automatic Waymo transfers. |
| [CenterPoint](https://arxiv.org/abs/2006.11275) | BEV center-based prediction | Our representation inference: two boxes assigned to one shared quantized regression slot collide; audit actual center collisions before replacing the head. |

## Decision rule and scope

Keep A0 immutable. Prefer a fully admitted coverage treatment as an engineering candidate only when it preserves the complete target contract and reports assignment quality honestly. A1 failure to fit despite full coverage motivates A2 and gradient/support diagnosis; A2/A3 fitting gains motivate later matched cohort/held-out work. A flat or worse result is retained evidence. Coverage improvement alone does not establish architecture superiority.

Initial scope ends with A0–A3 evidence and an adopt-for-further-study/reject/needs-more-evidence decision. Loss weighting/quota, NMS changes, query-head replacement, segmentation matching, SAM integration, camera fusion, Motion and planning remain separately scoped work. Detection fitting does not close the overall multimodal research program.
