# 34 — Explain and improve rare-class fitting

Goal: identify whether weak rare-class detections are caused by target geometry/retained support, training gradients, or proposal ranking; establish a controlled improvement before larger training.

Dependencies:33's audited native curve and class-fit diagnostics; no heldout model selection.

Evidence motivating the task: balanced 16 has 4788 vehicle versus 56 cyclist positive anchors. After 2000 updates, baseline mean positive-anchor true-class scores are vehicle 0.504, pedestrian 0.157, sign 0.124, cyclist 0.072. This suggests a class-learning problem but does not prove its cause. Native geometry/coverage and target masking must be examined separately.

Work:
1. Report per-class positive/negative focal contributions and gradients, box/heading residual errors, actual retained point support for each eligible object, uncovered IDs, and losses versus time.
2. Reproduce the literal existing loss as a control. Separately investigate training-only class weighting/normalization, then geometry/grouping changes; do not confound both in one first experiment.
3. Audit proposal score thresholds, pre-NMS class composition and top-K survival without changing GT or reinterpreting diagnostic anchor scores as detection recall.
4. Freeze the comparison recipe and a storage plan before launching further checkpoints; current scientific retention is near its unchanged 15 GiB cap.

First-tier verifier: one fixed native batch must fit before the balanced 16 comparison, preserving every available target and reported uncovered target. Use independent live loss/gradient equations, exact inference replay and official export/metric audits. Measure and bracket updates and synchronized time to reach the declared task threshold.

Acceptance: the matched control is reproduced; each hypothesis has an independently verified diagnostic that can reject it; a promoted change satisfies all-four-class native APH>=0.8 at two consecutive balanced 16 checkpoint samples, with no removal of difficult/uncovered GT and resource caps respected. Weaker improvements remain diagnostic. Whole-segment heldout experiments remain separate and follow the fitting gate.

Status: specified; no new weighting/geometry treatment has been trained. Original detector implementation and the completed matched candidates remain unchanged.

Include the existing foreground-prior-bias hypothesis as its own one-factor control before combining it with class weighting. The original-source audit verified ordinary head initialization; a low prior is an experiment, not an author-code parity correction. Also record clipping frequency: baseline1472/2000 and residual1427/2000 steps were clipped at10. These measurements motivate gradient diagnosis, but do not establish clipping as the cause.

Measured baseline mean focal components at initialization: positive0.708445 and negative1558.205135; at2000: positive0.241722 and negative0.071834. The huge initial negative term explains why relative total-loss reduction alone is not a useful fit verifier. Full task-level causation remains unproven. Class diagnostics were run in live CPU Insula and re-admitted against every retained parent training artifact hash.

## Native full-GT target-support evidence (2026-10-03)

The [coverage controls](../../../experiments/waymo-perception/research/balanced16-coverage-oracle-status.md) use ideal annotation-derived boxes rather than detector outputs. Against unchanged full native GT, the covered-target sign APH is0.759399, versus0.868421 when all training-eligible ROI signs are predicted exactly. Target arrays and original ordered ID reports agree:29ROI signs and1pedestrian have no positive anchor. All three control exports and native scores were independently replayed in live Insula. This establishes missing positive supervision; it does not bound unconstrained predictions or demonstrate that a replacement assignment improves a trained model.

Next diagnostic: independently reconstruct original nearest-BEV overlaps and forced assignments for every uncovered object, distinguish zero overlap from collisions with other GT/classes, and inspect retained physical support and decoder/NMS losses separately. Any replacement assignment/grid is a distinct one-factor treatment with frozen rules and independent native target/model/export verifiers. Preserve the preregistered four optimization recipes and all-class gate; do not combine target changes silently or remove GT. The running0/19/35 GPU pilot proves execution/restart before sustained cases, not scientific readiness.

Completed assignment diagnostic: independent live reconstruction matched every label and target index across the full 16-frame grids. All 30 uncovered targets have positive overlap; 28 lose their maximizing anchors to strictly higher overlap, and two lose equal-overlap ties. Of these conflicts, 28 are within the same class. This rejects zero overlap as the explanation for this cohort and shows that class-restricted matching alone cannot resolve the existing same-class conflicts. Matching treatments remain unimplemented and unpromoted; preserve the original control and investigate coverage-preserving matching separately from grid/height/NMS changes. See the linked coverage report and `balanced16-coverage-causes-verified.json`.

## Specified association follow-up (2026-10-03)

[Ticket 41](41-prediction-target-association.md) turns the ownership diagnosis into
an A0–A3 controlled study: unchanged reference, global coverage with existing
BEV cost, 3D-aware cost and detached prediction-dependent cost. Its
[specification](../../superpowers/specs/2026-10-03-prediction-target-association-design.md)
and [implementation plan](../../superpowers/plans/2026-10-03-prediction-target-association.md)
define bounded candidate feasibility, independent target/oracle/gradient/restart
verifiers, fixed-batch before balanced16 fitting, per-object suppression traces
and HDFS retention. Every implementation milestone requires live Insula.
Loss allocation and NMS remain separate follow-ups. The study is specified only;
the existing optimization controls, target caches and generated tracker/journal
are unchanged.
