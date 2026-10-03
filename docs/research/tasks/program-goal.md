# Overall actionable and verifiable research goal

## Goal

Build and evaluate a TensorFlow-free, geometry-correct Waymo perception research pipeline in locked live Insula runtimes, then deliver reproducible held-out evidence answering: (1) which pillar/window/range encodings improve efficient detection; (2) whether frozen detector-prompted SAM masks improve native point-semantic support over box transfer; and (3) whether supported causal sensor features improve forecasting beyond native tracks and maps. Include independent segmentation and camera localization/distance studies. Finish with explicit adopt/reject/needs-more-evidence decisions, not a required positive result.

## Overall acceptance

- [x] Tickets 01–06 prove live Insula and the real two-scene geometry tracer; both full runs independently validate. See [R0 evidence](../../../experiments/waymo-perception/research/r0-geometric-insula.md).
- [ ] Ticket 07 freezes scientific cohorts, resource budgets and statistical protocols before model comparisons.
- [x] Ticket 08 proves the locked single-device Torch GPU runtime with independent live validation.
- [x] Ticket 09 proves TF-free native 3D AP/APH and LiDAR semantic evaluation, plus explicitly diagnostic camera-semantic scoring; camera 2D, LET and panoptic tracking require their later gates.
- [ ] Tickets 10–16 establish independent detection/segmentation/camera baselines and controlled encoding/distance findings.
- [ ] Tickets 17–18 deliver same-prompt mask comparisons and geometry-aware point-transfer findings on identical eligible support.
- [ ] Tickets 19–21 establish native causal Motion ingestion/evaluation and matched forecasting feature comparisons.
- [ ] Ticket 22 audits/replays the primary comparisons and publishes results, uncertainty, coverage, runtime/memory and adoption decisions.
- [ ] Every implemented ticket has a candidate-specific independent live receipt; every scientific comparison has a preregistration and held-out report. No host-only pass, skipped assertion, TensorFlow dependency, future-observation leakage or heuristic cross-dataset join satisfies completion.

The program is complete when all required core acceptance criteria pass and the evidence package answers the stated questions. It is not complete merely because code runs, a visualization looks plausible, or a model improves on two engineering scenes. Negative results complete research when methods and evidence meet the frozen protocol.

## Evidence package and verifier contract

For each ticket, retain: input/cohort and code/runtime/checkpoint hashes; exact replay command; UTC start/end and exit code; live logs; required assertion outcomes; independently validated output hashes; measured resource usage; and a short outcome/limitations report. Keep large artifacts in managed storage, with small manifests and summaries in the repository.

The independent checker must reopen artifacts and derive checks from native inputs, analytic fixtures or pinned metric expectations. It cannot merely trust a producer's `passed` flag. It may run inside a separate invocation of the same locked Insula. A changed candidate invalidates prior closure until relevant checks run again. Failure records remain separate from successfully promoted artifacts.

Scientific preregistration in ticket 07 must freeze exact numerical cohort/resource limits, optimization/seed protocol, eligibility and class mappings, metric settings, overfit targets and numerical tolerances before the affected run. These values are outputs of resource/protocol selection, not hidden discretion during result analysis. If a requirement cannot be met, report the exact limitation and leave the gate open rather than silently shrinking support or changing the metric.

Primary mask-transfer and forecasting comparisons report paired effects with 95% intervals resampled by segment/scenario. Adoption requires a positive lower interval bound for the primary improvement and compliance with the frozen runtime/memory budget. Other studies publish declared outcome-specific decision rules before comparison. Inconclusive evidence means needs-more-evidence, not successful adoption.

## Dependencies and activation

The initial execution gate was ticket 01. Tickets 01–06 are now verified complete; tickets 07–09 and 19 can proceed against their verified prerequisites. Ticket preparation can proceed while prerequisites are unresolved, but execution/promotion requires verified blockers. M0 is the first milestone; GPU readiness cannot substitute for it. Model research requires verified R0.

Tickets 23–27 are conditional task specifications, not required core deliverables or execution authorization. Their activation criteria are stated individually. Evidence may justify a new hypothesis, but activating it requires recording the hypothesis and decision before running the treatment.

[Task index](../../../experiments/waymo-perception/research-task-index.md)
[Detailed mask/forecasting contract](../../../docs/superpowers/specs/2026-09-30-mask-refinement-and-forecasting-design.md)
[Live Insula contract](../../../docs/superpowers/specs/2026-09-30-live-insula-verification-design.md)
