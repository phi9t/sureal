# 07 — Freeze cohorts, budgets and statistical protocols

**Goal / what to deliver:** Turn engineering fixtures into a leakage-controlled, resource-bounded scientific study with decisions frozen before results.

**Blocked by:** [06](06-r0-closeout.md)

**Status:** preparing — all103 scenes /1,751 native sources admitted; full64 training-box replay, full103 semantic reconciliation, native shapes and camera lifecycles verified; full-support point/grid replay complete; scientific configuration and budget freeze remain open

**Lane:** core

**Verifier:** Independent audit of official split/source manifests and experiment preregistration; live loader verifies selected train/validation membership and coverage.

## Acceptance criteria

- [ ] Engineering validation scenes are excluded from training/tuning and identified separately from held-out scientific results.
- [ ] Record numerical scene/scenario counts, local storage cap, GPU-hours, memory/runtime limits and seed list after resource inventory.
- [ ] Freeze primary metrics, class maps, sampling, eligible support, bootstrap unit, 95% interval procedure and promotion rules before comparisons.
- [ ] Model comparisons use current-frame evidence initially; temporal treatments declare history separately.
- [ ] Whole segments/scenarios define split and uncertainty units; no adjacent-frame leakage.
- [ ] Independently validate live Insula receipt, candidate/input/runtime identities, required assertions, output hashes and measured resources; missing or failed checks prohibit closure.
- [ ] Publish a reviewable evidence summary with exact replay recipe, observed outcome and limitations; existing host tests or historical receipts alone do not close this ticket.

## Binding completion policy

[Program goal and evidence policy](program-goal.md) applies in full. Preparation may occur before blockers clear; candidate execution/promotion and completion require verified blockers. Scientific completion permits negative/inconclusive findings. Adoption requires the separately stated promotion rule.

## Observed label coverage

[Reconciled native label audit](../../../experiments/waymo-perception/research/scientific-label-coverage.json) covers all 64 training, 8 development and 16 validation segments for both segmentation families. LiDAR segmentation is populated in every selected scene. Camera segmentation is populated in 58/64 training, 6/8 development and only 1/16 validation scenes. Keep the full cohort denominator and annotation eligibility explicit. Before freezing the primary mask/camera comparison, establish an additional official-validation cohort selected by a declared coverage-only rule; one labeled held-out scene does not satisfy the intended scene-level comparison. No model outcomes have been used for selection.

## Additional camera held-out support

[Coverage-selected camera cohort](../../../experiments/waymo-perception/research/camera-validation-cohort.json) records the coverage-only rule, all 18 audited candidates, 16 selected validation scenes and two reserves. Native positive camera/LiDAR semantic support was verified before selection. The original LiDAR cohort is retained separately. Sensor manifests, alignment, budgets and final protocol acceptance remain open.

## Full scientific sensor acquisition

The [generation-pinned acquisition candidate](../../../experiments/waymo-perception/scientific-acquisition.candidate.json) requires all 17 families for 103 unique scenes (1,751 objects), mirrored through Waystone to HDFS. The [acquisition snapshot](../../../experiments/waymo-perception/research/scientific-source-acquisition-progress.json) and [partial key reconciliation](../../../experiments/waymo-perception/research/scientific-frame-join-progress.json) record current evidence and its scope. Counts are progress snapshots, not a reduced cohort or acceptance substitute. Payload alignment and independent full-source loader validation remain required.

[Bounded scientific preprocessing plan](../../../docs/superpowers/plans/2026-09-30-scientific-scene-preprocessing.md) specifies source admission, native sidecars, full sensor reconstruction, independent validation, immutable HDFS publication and replay. Its proposed derived working-set cap must be validated and frozen; raw staging remains subject to the existing combined 2 GiB limit. Acquisition completed with exit code 0. The shared staging lease still prevents overlapping raw transfers. [Complete source admission evidence](../../../experiments/waymo-perception/research/scientific-source-admission-complete.json) reconciles all 103 scenes / 1,751 source receipts; this does not substitute for payload-level preprocessing or protocol acceptance.

## Distinct supervision clocks

[Complete native frame-catalog audit](../../../experiments/waymo-perception/research/supervision-frame-alignment.json) covers all 103 scenes: all 3,118 LiDAR-labeled timestamps have camera measurements, while 437 also have camera segmentation annotations. Camera-native target support contains 2,735 timestamps. Do not narrow the primary point-semantic comparison to the joint-annotation intersection. Point transfer uses native point targets and available camera measurements; camera-native mask quality uses its separate camera target catalog. Missing measurement support remains explicit, and full scene/pixel/point eligibility still requires payload-level checks. Frame catalogs are fully audited; native payload eligibility and scientific freeze remain open.

## Scientific pilot evidence

The first training scene has independently checked native reconstruction, immutable HDFS point publication and two exact live loader replays. Seven decoded native sidecar families were independently published and mirrored, then verified local eviction retained immutable recovery metadata. See [point replay](../../../experiments/waymo-perception/research/scientific-training-replay-evidence.json), [sidecar publication](../../../experiments/waymo-perception/research/scientific-sidecar-publication-evidence.json), and [sidecar eviction](../../../experiments/waymo-perception/research/scientific-sidecar-eviction-evidence.json). Historical receipts retain original artifact inventories; evicted payloads require verified HDFS rehydration before reuse. These single-scene engineering checks do not close full-cohort coverage, task-specific camera inputs, numerical scientific protocol or model comparisons.

## Bounded full-cohort processing progress

[Current preprocessing snapshot](../../../experiments/waymo-perception/research/scientific-processing-progress.json) records only independently admitted point and camera lifecycle counts. The original 103-scene selection remains unchanged. Each completed queued scene requires separate live checkpoint admission reconciling current nested workers, runtime, all 17 source identities, retained artifacts and verified eviction lineage before snapshot promotion. Historical receipts retain pre-eviction artifact inventories; recovery manifests identify immutable HDFS publications. Full task coverage and scientific freeze remain open.

## Detector resource preparation

[Integrated synthetic GPU pilot](../../../experiments/waymo-perception/research/detector-gpu-resource-verified.json) and [native engineering frame integration](../../../experiments/waymo-perception/research/native-detector-gpu-verified.json) verify the complete pillar model's forward/backward path on the locked single-device Torch runtime. The synthetic 512×512 grid used 1,305,486,336 allocated bytes; warm forward/backward calls took about 45 ms. Native-frame integration used 1,193,811,456 allocated bytes. These are measured correctness/resource pilots with zero optimizer steps. Native scientific training I/O, target assignment, optimizer state, evaluation and total experiment cost remain unmeasured; these pilots do not freeze a training budget or justify extrapolating total GPU-hours.

### Observed preprocessing resource inventory

Locked live CPU audit reopened13 externally hash-pinned completed queued checkpoints, checked successful10-stage lifecycles and linked retained point/camera/sidecar publication receipts, and summarized actual stage durations, memory fields and immutable archive sizes. Observed total scene elapsed min447.774s, median615.024s, max690.634s, sum7864.896s. Evidence `experiments/waymo-perception/research/scientific-preprocessing-resource-verified.json` (repository-relative). This is completed-scene preprocessing cost only; manual pilots excluded, remaining87scene processing not extrapolated, no training/evaluation GPU budget or cap freeze. Scientific protocol remains open.

[Training-box distribution fixture evidence](../../../experiments/waymo-perception/research/training-box-statistics-verified.json) verifies native length/width/height/center-Z medians and explicit per-frame-object weighting, and rejects non-training membership/duplicate identities/bad geometry. This prepares anchor estimation; full64training-source coverage and cryptographic membership admission remain required before configuration adoption. No held-out anchor fitting or default class dimensions.

[Current native valid-range support inventory](../../../experiments/waymo-perception/research/scientific-semantic-support-progress.json) retains the full 103-scene denominator and separate official/research membership. Each admitted coverage receipt reconciles its histogram with an independent literal class-count loop and pins source, reconstruction, runtime, and current consumer identities. The inventory records lifecycle linkage separately for each capture: independently admitted checkpoints and immutable point publications are required for every captured scene. Further captures require the same linkage. Counts remain partial and cannot freeze task eligibility or close the scientific protocol. Read-only capture uses no raw staging or processing-driver modification. Previously evicted scenes require bounded immutable replay to recover their point-label eligibility.

[Full training-box replay input candidate](../../../experiments/waymo-perception/research/training-box-statistics-inputs.candidate.json) pins all 64 training-only source receipts, generations and payload hashes. Direct single-source replay avoids multi-GB sidecar archives; live payload statistics and independent distribution reconciliation remain required.

[Full training-box distribution replay plan](../../../docs/superpowers/plans/2026-09-30-training-box-distribution-replay.md) defines exact source admission, shared staging ownership, all64 source completion (including zero eligible rows), native center-Z statistics, separate live quantile verification and failure gates. Execution waits for the current processing queue; metadata inventory does not adopt anchors.

### Expanded measured preprocessing inventory

A fresh locked live Insula audit covers all 59 independently admitted completed scenes with comparable ten-stage driver timing at the 63-scene snapshot. Observed elapsed seconds: minimum 447.774, median 612.281, maximum 762.418, total 36205.072. [Expanded live resource receipt](../../../experiments/waymo-perception/research/scientific-preprocessing-resource-expanded-verified.json) pins the checkpoint set, snapshot, retained publication identities, stage durations, archive sizes and reported child-memory fields. Three manual pilots and one interrupted/recovered lifecycle are explicitly excluded from comparable timing; their processing evidence remains retained. This measures observed preprocessing only. It does not extrapolate remaining-cohort cost, measure training/evaluation GPU budgets, freeze the candidate decoded cap or close ticket 07.

### Native training-box source adapter preparation

[Live source-boundary and Parquet fixture evidence](../../../experiments/waymo-perception/research/training-box-sources-parquet-verified.json) supersedes the earlier adapter-only fixture candidate. Thirteen groups ran without skips in locked offline CPU Insula, proving empty/unknown-only source completion, full declared training source selection, native row accounting, duplicate/key/geometry rejection, late-read failure propagation and literal length/width/height/center-Z distributions. A streamed Parquet fixture exercises native flattened columns; TensorFlow is absent. The adapter consumes previously admitted decoded sources and does not establish manifest/receipt/payload cryptographic provenance itself. Actual64 source replay, source-integrity admission, independent complete quantile verification and measured real-cohort memory remain required. No anchors, sampling bounds or scientific budget were adopted.

### Independent native quantile checker preparation

[Live independent quantile and reopened Parquet fixture evidence](../../../experiments/waymo-perception/research/training-box-reference-parquet-verified.json) verifies23 groups without skips, including10 reference-checker groups. The standard-library checker independently parses native fields, checks complete source/row accounting, sorts each class/coordinate and linearly interpolates median/p10/p90. Standalone live import proves no producer, source adapter or NumPy is loaded; TensorFlow is absent. Producer and verifier reopen the same fixture Parquet independently with different batch sizes, including empty and unknown-only sources. Wrong quantiles, bottom-Z substitution, absent-class defaults, changed source measurements, duplicate unknown rows despite adjusted report counts, incomplete inventory and late read errors are rejected. This prepares the separate step6 consumer; all64 source provenance/replay, actual distributions and resource measurements remain open. Quantile numerical tolerance is1e-12 relative/absolute; this is verification precision, not a scientific promotion rule.

### Bounded training-source transport preparation

[Live verified byte-stream integration](../../../experiments/waymo-perception/research/training-box-wire-integration-verified.json) records32 targeted groups without skips, including9 wire groups. Raw Parquet bytes are independently SHA256/MD5 checked against external inventory before decoding; framing/schema/count/consumption faults prevent completion. Separate verified wire passes feed producer and reference on fixtures, including an empty source. The replay plan now specifies stdin acknowledgements so host staging can release each object before fetching the next. Actual HDFS-to-worker process handshake, all64 independent source reopens, real distributions and bounded resource measurements remain required. No raw staging was taken during preparation; no protocol budget or anchors adopted.


### Producer provenance admission regression (2026-10-01)

Live Insula reproduced acceptance of mathematically matching statistics with a mismatched producer role. The reference worker now checks producer role, acquisition/cohort manifest hashes, and the full source-receipt hash mapping before consuming payload bytes. Producer and reference job hashes differ by design because the reference job additionally pins the producer report.

Fresh live verification passed all 42 targeted training-box test groups, including separate producer/reference CLI processes and four provenance mutations. A separate reference-import check confirmed that the independent statistics verifier imports neither producer, adapter, NumPy, nor TensorFlow. Evidence: `experiments/waymo-perception/research/training-box-job-provenance-verified.json`, with retained failing-regression receipt and fresh candidate/log hashes.

This accepts only offline worker fixture readiness. Full real 64-training-scene HDFS replay, host staging/ACK orchestration, independent reread, measured resources, and experimental freeze remain open. The active scientific-processing queue retains staging ownership.


Host sender preparation: `pipeline/training_box_sender.py` retains the injected staging context until an exact scene/hash/row-count consumed ACK arrives, then releases it before the next source. Completion footer is emitted only after every ACK. `research/training-box-sender-process-verified.json` records45 passing targeted checks in locked live Insula, including a real separate worker consuming Arrow Parquet through bidirectional pipes (one nonempty source and one empty source). This verifies transport interoperation, not production HDFS staging, full-job orchestration, deadline handling or real64-source replay. Those gates remain open.

ACK deadline preparation: live Insula passes46 targeted groups, including real worker pipe success with a deadline and a partial-line stalled worker that times out and releases staging. Evidence: `research/training-box-sender-timeout-verified.json`. Host writes/transfer deadlines and production HDFS/full-job orchestration remain open.

Pipe-write deadline preparation: `research/training-box-sender-write-verified.json` records47 passing live Insula targeted groups. Successful worker pipes use both deadlines; a non-reading pipe times out, restores its blocking mode and releases staging. Deadlines bound each pipe write/ACK, not the entire source transfer. Production callers must supply both timeout values, exclusively own unbuffered worker pipes, verify process exit/report, and separately bound HDFS transfer. Full replay remains open.

Full-job preparation: original real64×17 metadata passes live admission (`research/training-box-producer-job-admitted.json`) with the pinned worker job candidate. Separately, `research/training-box-full-handshake-verified.json` records48 live targeted groups, including64 fresh synthetic raw readers per separate producer/reference CLI pass, timed writes/ACKs, and reference producer-import exclusion. These are metadata admission and synthetic process integration; actual HDFS payload replay and resource measurements remain required.

Production driver candidate: `pipeline/training_box_replay.py` now composes queue exclusion, runtime rehash, all-source identity checks, timed HDFS staging, owned producer/reference processes, fresh independent source readback, and time/RSS artifacts. Live Insula50 targeted groups verify its busy-queue refusal gate plus existing worker integration. Actual host invocation also refused the currently held queue lock before output creation. The driver full path is not accepted yet: execution-candidate external pinning, retained-raw recalculation, complete injected staging verification, source/report audit and real replay remain open.

Full production-driver fixture verification: `research/training-box-worker-resources-verified.json` records52 targeted live checks and two separate full64 synthetic mirror passes using actual staging leases, hash/MD5 checks, clean eviction and isolated producer/reference workers. The initial full-path run exposed missing `/usr/bin/time`; standard-library launcher timing replaces it. Launcher RSS is not worker memory evidence. In-worker RUSAGE_SELF now measures process peak explicitly: synthetic producer73368KiB and reference70304KiB, roughly4.85/5.05s including staged-source wait. These are fixture resources only, not scientific-cohort estimates. Actual full64 HDFS replay and independent final receipt audit remain open.

Real replay continuation armed: research/training-box-replay-pending-execution.json records one-shot session34090. It waits for all original103 independently admitted scene identities and queue completion, checks pinned code/inputs, then runs both full64 real HDFS passes. It stops on missing queue handle before full admission or changed pins; it never restarts processing or bypasses staging ownership. Pending execution is not replay acceptance or anchor adoption.

Independent retained audit: research/training-box-replay-audit-mutants-verified.json records live Insula acceptance of the unchanged full64×2 synthetic replay and rejection of8 rehashed corruptions (empty/missing quantile proof, checksum, omitted ACK, native rows, quantile values, invalid worker RSS, invented absent-class dimensions). A failing missing-quantile regression exposed an auditor gap and now requires all4 classes/all3 quantile fields. Actual HDFS replay acceptance remains open.

### Range input preservation and mask-geometry freeze gates

Range-view scientific readiness additionally requires full original103-scene
native shape recovery:203,850 expected return records, source-linked null/present
states, reconstructed-pixel bounds and independently reread dimensions. Engineering
extractor/source/reference fixtures pass live, but the full recovery remains
pending. Ticket13 and the2026-10-01native-range-shape-recovery plan preserve this
requirement; empty boundary extent must not be inferred from sparse point maxima.

Ticket18 now has live native camera-core and SAM incidence/boundary diagnostics.
Same-pixel nearest-measured depth leaves most singleton pixels untested for
occlusion. A mask interior requirement reduces engineering support but is not a
calibrated uncertainty bound. Scientific projection/visibility/mask-boundary rules
must be frozen from training/development evidence and held identical across the
support treatments; neither diagnostic automatically clears physical visibility.
Full eligible native point support and independent LiDAR fallback remain binding.

## Current data-gate reconciliation (2026-10-01)

This section supersedes the pending execution descriptions above; those retain
historical preparation context. The full64 real training-box replay and separate
live retained audit completed: [evidence](../../../experiments/waymo-perception/research/training-box-full64-replay-verified.json).
This admits training distributions, not an anchor configuration.

All103 semantic denominators were independently reconciled in live Insula:
478,579,462 eligible points across3,118 annotated frames:
[evidence](../../../experiments/waymo-perception/research/scientific-semantic-full103-verified.json).
Native shape recovery completed all203,850 return records; the aggregate host
rehash preserves links to individual live admissions:
[evidence](../../../experiments/waymo-perception/research/scientific-native-shape-full103-retained-audit.json).
All103 camera lifecycles passed a separate live aggregate audit:
[evidence](../../../experiments/waymo-perception/research/scientific-camera-full103-verified.json).

The [point/grid replay](../../../experiments/waymo-perception/research/scientific-point-grid-progress.json)
is still running. No partial count closes its all103-source gate. These receipts
do not establish model quality, calibrated camera visibility or forecasting
causality. All acceptance checkboxes above remain unchanged pending the complete
protocol and its independent live verification. No scientific optimizer updates
or held-out model comparisons are claimed.

### Training-only anchor candidate

[Candidate](../../../experiments/waymo-perception/research/training-anchor-templates.candidate.json) derives eight templates from audited full64 training medians: four native box classes, each at yaw0 and pi/2, preserving native LWH and center-Z. [Live preparation verifier](../../../experiments/waymo-perception/research/training-anchor-candidate-verified.json) checks exact summary/audit lineage, class/yaw ordering and analytic non-square XY layout. This is a candidate, not protocol adoption. Statistics weight frame/object rows equally; cyclist support is only38 unique tracks. ROI, sampling, assignment/loss rules, update budgets and training overfit gates remain open.

### Optimizer-inclusive synthetic resource preparation

[Live GPU fixture](../../../experiments/waymo-perception/research/detector-optimizer-resource-verified.json) measured the512×512,20,000-pillar,32-slot, four-class/eight-anchor model through three synthetic Adam updates. The first bias update matched the analytic Adam equation; all parameter gradients and optimizer moments were finite. [Separate live retained audit](../../../experiments/waymo-perception/research/detector-optimizer-resource-audit-verified.json) verified source/output hashes, the head parameter-count delta and exact Adam state-byte equation. Peak allocated memory was1417361920 bytes; warm full steps took[0.033657166990451515, 0.03281902399612591] seconds. These are synthetic costs, not native scientific training, quality, full training/evaluation budgets or protocol acceptance. No scientific optimizer updates are claimed.

## PointPillars scientific protocol candidate

[Draft numerical protocol](../../../experiments/waymo-perception/research/pointpillars-scientific-protocol.candidate.json) specifies current-frame five-LiDAR/two-return physical inputs,128m square half-open ROI,512-cell grid,20,000 pillars/32 points, eight training-median anchors, scalar assignment and existing loss/NMS adaptations. It declares seeds17/29/43,20,000 updates, development-only checkpoint selection, a16-training-frame overfit gate, full native held-out GT including outside-ROI targets, segment-level pooled-metric uncertainty, and explicit resource caps. The24 reserved device-hours per seed is a proposed hard cap, not an extrapolated runtime estimate.

[Independent live structural audit](../../../experiments/waymo-perception/research/pointpillars-protocol-candidate-structure-verified.json) checks exact source/code hashes,64/8/16 disjoint cohorts, physical-feature exclusion, measured resource-layout compatibility and six malformed-candidate refusals. This admits draft structure only. Native observation/target joins, target exclusions, assignment/optimizer/export resource pilot, tiny overfit and full protocol admission remain gates before the main scientific run. Neither ticket is closed, and no encoder comparison or held-out quality is established.

## Completed point/grid data gate (2026-10-02)

All103 selected scenes completed the two-pass full-support point/grid replay.
The [retained aggregate](../../../experiments/waymo-perception/research/point-grid-full103-and-overfit-box-retained-audit.json) records203,850 returns,3,513,295,187 points and478,579,462 eligible semantic points. Its progress hash, all103 evidence hashes and summed denominators were rechecked against current files. This is a host reconciliation of individual live admissions; scientific protocol acceptance and held-out model comparisons remain open. Earlier running-state descriptions are historical.
