# 10 — Establish independent PointPillars detection

**Goal / what to deliver:** Establish a reproducible current-frame LiDAR 3D detection reference for representation comparisons.

**Blocked by:** [07](07-scientific-protocol.md), [08](08-gpu-runtime.md), [09](09-perception-evaluators.md)

**Status:** planned — blocked by prerequisite verification

**Lane:** core

**Verifier:** Live training/forward/backward/export/scoring, tiny training-only overfit, independently validated held-out predictions and per-seed metrics.

## Acceptance criteria

- [ ] Freeze the [pinned implementation contract](../../../experiments/waymo-perception/research/pointpillars-implementation-contract.md) under ticket 07, including physical sensor features, ROI, sampling, padding, anchor estimates, assignment, NMS, update budget and checkpoint selection. Training-only statistics determine dataset adaptations.
- [ ] Independently check live PFN decorations, padding and singleton shapes, point-order invariance without sampling, and metric XY-to-scatter orientation against analytic fixtures.
- [ ] Independently check anchor encode/decode, center-Z convention, yaw wrapping and direction correction; assignment thresholds, ties, no-overlap and empty-target cases; loss normalization; deterministic NMS ties.
- [ ] Sensor inputs exclude label IDs, no-label-zone encoder features and box-derived target metadata.
- [ ] Finite loss/gradients and preregistered tiny-subset overfit target pass.
- [ ] Held-out AP/APH, errors, distance breakdowns and total resource costs are reported for frozen seeds.
- [ ] Exact implementation deviations from PointPillars are documented; results are not claimed as paper reproduction without matching protocol.
- [ ] Independently validate live Insula receipt, candidate/input/runtime identities, required assertions, output hashes and measured resources; missing or failed checks prohibit closure.
- [ ] Publish a reviewable evidence summary with exact replay recipe, observed outcome and limitations; existing host tests or historical receipts alone do not close this ticket.

## Representation-comparison control

First establish the anchor-head PointPillars adaptation. A pillar-plus-center-head bridge is a separately named treatment: hold pillar inputs and backbone fixed while evaluating the head change, then hold the center-head contract fixed for encoding comparisons where required. Changing targets, assignment, losses or decoding together with an encoder cannot isolate an encoding effect. The common-head models are adaptations; matching their interfaces does not establish reproduction of published full-model results.

## Binding completion policy

[Program goal and evidence policy](program-goal.md) applies in full. Preparation may occur before blockers clear; candidate execution/promotion and completion require verified blockers. Scientific completion permits negative/inconclusive findings. Adoption requires the separately stated promotion rule.

## Mathematical implementation preparation

[Live encoder fixtures](../../../experiments/waymo-perception/research/pillar-encoder-preparation-verified.json) cover exact nine-channel decorations, padding, singleton/permutation behavior, finite CPU gradients, XY scatter and invalid-input refusal in the locked Torch Insula. This is preparation only. GPU model execution, statistical protocol, ROI/sampling, full padded-slot BN parity, anchor/head/loss/export and held-out research acceptance remain required.

Additional independently audited live preparation now includes [padded-slot BN and GPU parity](../../../experiments/waymo-perception/research/pillar-gpu-verified.json), [center-Z box coding](../../../experiments/waymo-perception/research/box-coding-verified.json), [deterministic overlap assignment](../../../experiments/waymo-perception/research/anchor-assignment-verified.json), and [nearest-IoU/enclosing-NMS geometry](../../../experiments/waymo-perception/research/detector-geometry-verified.json). These establish mathematical reference components. Trainable box head/losses, complete GPU model execution, anchor statistics, frozen ROI/sampling/budgets, export and held-out comparisons remain required.

[Actual prediction-to-native-score engineering evidence](../../../experiments/waymo-perception/research/native-prediction-scoring-verified.json) verifies native GPU outputs through diagnostic decoding, independently recomputed measured point-count/NLZ metadata, protobuf handoff and native scoring. Zero optimizer steps; one engineering frame, fixture settings, no scientific quality or held-out result. Scientific training/overfit/configuration and comparison criteria remain open.

## PointPillars scientific protocol candidate

[Draft numerical protocol](../../../experiments/waymo-perception/research/pointpillars-scientific-protocol.candidate.json) specifies current-frame five-LiDAR/two-return physical inputs,128m square half-open ROI,512-cell grid,20,000 pillars/32 points, eight training-median anchors, scalar assignment and existing loss/NMS adaptations. It declares seeds17/29/43,20,000 updates, development-only checkpoint selection, a16-training-frame overfit gate, full native held-out GT including outside-ROI targets, segment-level pooled-metric uncertainty, and explicit resource caps. The24 reserved device-hours per seed is a proposed hard cap, not an extrapolated runtime estimate.

[Independent live structural audit](../../../experiments/waymo-perception/research/pointpillars-protocol-candidate-structure-verified.json) checks exact source/code hashes,64/8/16 disjoint cohorts, physical-feature exclusion, measured resource-layout compatibility and six malformed-candidate refusals. This admits draft structure only. Native observation/target joins, target exclusions, assignment/optimizer/export resource pilot, tiny overfit and full protocol admission remain gates before the main scientific run. Neither ticket is closed, and no encoder comparison or held-out quality is established.

## Fixed tiny-overfit frame identities

[Selection candidate](../../../experiments/waymo-perception/research/pointpillars-overfit-frames.candidate.json) chooses exactly16 frame keys by the preregistered hash rule from12,676 unique native training frame keys across all64 training scenes. [Independent live metadata audit](../../../experiments/waymo-perception/research/pointpillars-overfit-selection-verified.json) reopens source-linked native shape artifacts and their live admissions, validates ten sensor/return records per frame and reconstructs the entire hash ordering. Validation substitution, duplicate frame, altered timestamp and ordering mutants are refused. No box labels, semantic coverage or model outcomes determine this selection.

Next materialize these exact frames from immutable point publications under shared queue/raw leases and the unchanged working cap, independently verify source identity and physical/target namespace separation, then join native lidar_box by frame keys with explicit zero-target/absence handling. Selection metadata does not prove sensor/box payload joins, overfit or held-out quality.

## Native target materialization preparation

[Streamed Parquet fixture](../../../experiments/waymo-perception/research/overfit-box-worker-fixture-verified.json) passed producer and independent literal source reread in separate live Insula calls. Native center-Z boxes, unknown categories and nullable difficulty are preserved; missing box rows remain coverage-unresolved. Test-first checks refuse full-source duplicate, geometry, identity, point-count, difficulty and row-count faults.

[Queued target input candidate](../../../experiments/waymo-perception/research/overfit-box-extraction-inputs.candidate.json) pins13 actual HDFS lidar_box sources for the16 fixed frames, runtime and code. [One-shot execution](../../../experiments/waymo-perception/research/overfit-box-extraction-pending-execution.json) waits for the exact point/grid owner to terminate with all103 admissions, then uses the existing queue/raw leases, full-byte SHA256/MD5 checks, separate full-source producer/reference reads and a third retained live audit. Its log stays outside the accounted scientific working root. Armed execution is not source admission; no point join or model training has run. Preserve its pinned scratch workers while it is live.

## Selected physical frame extraction preparation

[Live archive fixture](../../../experiments/waymo-perception/research/overfit-point-worker-fixture-verified.json) validates complete source replay and selected physical-frame output against independent literal archive reconstruction. Test-first live checks cover physical-only XYZ/intensity, native laser/return/pixel identities, evaluation-only NLZ, absent versus present-empty returns, ordering and refusal of incomplete/duplicate/misaligned records.

[Queued point inputs](../../../experiments/waymo-perception/research/overfit-point-extraction-inputs.candidate.json) pin13 immutable training point publications covering the16 fixed frames. [One-shot execution](../../../experiments/waymo-perception/research/overfit-point-extraction-pending-execution.json) waits for native box owner termination with13 independent admissions, then performs two complete live source passes and independent retained frame/target joins. Serial archive I/O is42,230,835,200 bytes; selected payload cap1GiB is inside the unchanged15GiB working cap. No simultaneous staging or source-pin changes are authorized. Queued acquisition does not establish actual payload/target admission, packing, overfit or scientific quality. Preserve its pinned scratch workers while live.

## Native target-assignment preparation

A target-only preparation layer applies the declared unknown-class/zero-point/half-open-center-ROI filters, pinned nearest-BEV assignment and center-Z encoding. It reports eligible objects with no positive anchor rather than dropping them, and uses canonical native heading in[-pi,pi) with direction bin1 iff strictly positive. Live test-first checks cover duplicate/foreign targets, invalid geometry/metadata, exact exclusions, center-Z and zero-overlap support.

[Independent full-layout fixture](../../../experiments/waymo-perception/research/overfit-target-layout-fixture-v2-verified.json) checks all524,288 anchors for the eight-template512-cell grid. Its separate literal reference imports none of the grid/IoU/assignment/coding helpers; labels, matched targets, residuals and direction bins agree within1e-13, including negative headings and2pi-equivalent headings. Synthetic positive-anchor counts are vehicle8, pedestrian4, sign4, cyclist4. This establishes preparation equations only; actual native frame positive/uncovered support, exclusion counts, memory/runtime and tiny overfit remain required.

## Integrated cache preparation and yaw correction

[Latest live integrated fixture](../../../experiments/waymo-perception/research/native-overfit-preparation-fixture-v3-verified.json) checks physical-only observations separately from point lineage and box targets. Independent literal references verify source-index alignment, padding/scatter and all524,288 target assignments/residuals, including decoded-heading equivalence. [Edge-case audit](../../../experiments/waymo-perception/research/native-overfit-preparation-edgecases-v3-verified.json) admits a valid all-background ROI example, retains an eligible but uncovered object and refuses unresolved annotation coverage before writing training arrays.

A live round-trip regression exposed a mismatch in earlier scratch target helpers: direction labels used canonical heading but residuals retained an unwrapped heading, making +pi decode as zero. [Correction evidence](../../../experiments/waymo-perception/research/overfit-yaw-roundtrip-correction-verified.json) preserves the failing and passing logs. The versioned v2 target helper canonicalizes GT heading before overlap, encoding and direction labels; the v3 cache worker uses it. Earlier fixture receipts remain historical equation checks and must not authorize the old helper for native training. This changes target representation only; native source box records remain intact. No optimizer updates or held-out comparisons have run.

The [fresh yaw-correction receipt](../../../experiments/waymo-perception/research/overfit-yaw-correction-live-receipt-verified.json) adds exact live replay/audit commands, UTC execution times, runtime identity and externally checked helper/test/decoder hashes. Six boundary headings at two anchor orientations pass physical roundtrip within1e-12 radians. A separate live invocation reopens the retained log and current code identities. This verifies exact encoded-target roundtrip, not arbitrary model predictions or scientific accuracy.

## Queued native16-frame cache preparation

[Reusable literal cache checker](../../../experiments/waymo-perception/research/overfit-native-cache-auditor-fixtures-verified.json) passed positive, valid-background and uncovered-target cases in live Insula. It reconstructs packing from physical source values and PCG64 sampling, then independently computes all524,288 assignments and residuals in bounded8192-anchor chunks without importing production math helpers.

[Native cache candidate](../../../experiments/waymo-perception/research/overfit-native-cache-inputs.candidate.json) freezes the corrected v3 cache worker/v2 yaw target helper,16 fixed frame IDs and per-frame tiny-overfit packing seeds before optimization. It uses a1.25GiB prepared-payload cap within the unchanged15GiB scientific working cap,16GiB worker address-space cap and64MiB output-file cap. [One-shot execution](../../../experiments/waymo-perception/research/overfit-native-cache-pending-execution.json) waits for the selected-point owner to terminate with13 independent admissions; each frame then needs a separate live source/packing/all-anchor reference. Pending execution is not cache admission, GPU feasibility, overfit or scientific protocol closure. Preserve its pinned helper/worker files while it is live.

The [full16 retained cache audit](../../../experiments/waymo-perception/research/overfit-native-cache-full16-retained-audit.json) now reconciles completed independently live-admitted native caches for all16 fixed frames. It reports actual point retention, positive anchors by class, uncovered native targets and observed CPU resources. Pending execution descriptions above are historical. Native GPU optimizer/resource execution and the preregistered overfit score/export gate remain open.

## Native optimizer/resource pilot

[Live native pilot](../../../experiments/waymo-perception/research/native-optimizer-pilot-verified.json) completed16 accepted diagnostic updates using independently admitted fixed training caches. It checked finite gradients/parameters, clip10 and exact model-output/Adam-state checkpoint restoration. [Separate live retained audit](../../../experiments/waymo-perception/research/native-optimizer-pilot-audit-verified.json) independently reconciled source hashes, native positive-anchor counts, loss arithmetic and saved optimizer steps. Peak allocated GPU memory1,415,641,088 bytes; native pilot time3.291s includes I/O/checkpoint operations and does not estimate full-study cost. Earlier failed checkpoint-admission execution also performed16 updates and is retained. Tiny-overfit loss/APH acceptance, prediction export/scoring and main scientific protocol admission remain open.

## Failed overfit score and architecture investigation

The fresh2000-update fixed16 run passed [independent checkpoint/loss replay](../../../experiments/waymo-perception/research/native-overfit-training-audit-verified.json), but the live native scorer returned mean LEVEL2 APH.0056932515 versus required.8. Independent scoring admission is still pending; this is no successful overfit. [Deep-dive draft](../../../experiments/waymo-perception/research/pointpillars-training-deep-dive.md) records architecture, source deviations, observed head diagnostics and D1–D7 goals/verifiers. Keep the failed checkpoint and original primary score; resolve convention, positive-learning, normalization, support and suppression questions before changing the recipe.

## One-batch diagnostic result

[Independently checked result](../../../experiments/waymo-perception/research/native-one-batch-overfit-result.json): first fixed training frame,2000 updates, unchanged4.85M model. Vehicle/pedestrian LEVEL2 APH.998079/.988051; signs.226459. All17 eligible boxes retained. Mean.7375296666666666 fails the unchanged.8 gate. Separate live audits cover checkpoint/loss, literal decode/NMS, original measurement metadata, eligible GT, protobuf fields and native metric replay. Next isolate thin-sign localization, anchor coverage and uncovered-target effects; do not infer that low parameter count is the cause of the16-frame failure. No heldout claim or ticket closure.

## Mandatory Tier1 architecture verifier

[Batch-overfit verifier](../../../experiments/waymo-perception/research/tier1-batch-overfit-verifier.md) is now the first model-architecture development gate. Require full-class fixture coverage, native per-class quality, independently live-checked inference/export, and checkpoint-bracketed update/time-to-fit with separate training/evaluation/resource accounting. Existing historical primary gates remain unchanged. Current one-batch fixture has no cyclists and signs fail; it is not whole-model Tier1 admission. Learning-curve replay is required before attributing difficulty to iteration count or model capacity.

## Verified learning-speed investigation

[Result](../../../experiments/waymo-perception/research/tier1-one-batch-learning-investigation-result.json) independently checks11 sampled checkpoints. Vehicle/pedestrian quality first passes between500 and750 updates; mean criterion between1000 and1500, then regresses by2000. Per-class Tier1 remains failed. A zero-update frozen-weight BN refresh raises meanAPH.737530→.864156, proving inference statistics contribute to the final gap; signs remain.595564. Next audit/fix sign assignment coverage and centimetre-scale localization, then run matched BN and initialization experiments with the same timing/quality verifier. Preserve original failed outputs and allGT; no heldout result or scientific ticket closure.

## Normalization-only ablations

[Preregistered study](../../../experiments/waymo-perception/research/normalization-ablation-spec.md) compares GN8 backbone, GN8+point-LN and no norm against auditedBN with identical initialized convolution weights, batch/targets/optimizer/update/checkpoint/native-scoring contracts. Live tests verify axes and mode behavior. Complete training, loss/checkpoint and native prediction audits before declaring a fixed-batch result; no main-study or all-class adoption follows from this batch.

## Completed matched normalization investigation

[Audited comparison](../../../experiments/waymo-perception/research/normalization-ablation-results.md) reports11 checkpoints per treatment, independent live Insula scoring/audits and retained recipe/source evidence. GN backbone final meanAPH.878552; GN+point-LN.856792, with earlier sampled mean pass; originalBN.737530. No-norm primary decoder failure is retained; separately versioned score-first decoder is exactly equivalent on all33 normalized exports and admits independently audited no-norm meanAPH.621318. Every variant still fails sign per-class≥.8; fixture has no cyclists. Candidates only, no main-study adoption or ticket closure.

## Architecture first cohort admitted

All8variants have live native2000update execution, independent loss checks, strict initial/final head/Adam replay and all11checkpoint geometry/export/native metric audits (88total). Final1529artifacthash reconciliation passes. ResidualBEV meanAPH.907812 and maskedpool.886386 are candidates for broader evaluation; allsignperclassgates fail and cyclists absent. Windowattention/control are essentially baseline quality; retention recovers source measurements without improving fixedrecipe fitting. [Results](../../../experiments/waymo-perception/research/architecture-first-cohort-results.md) and machine-readable receipts preserve scheduler failure/exclusive repeat and reviewed verifier fixes. No fullclass/heldout adoption or overallgoal closure.
