# Multimodal perception research program

Labels: wayfinder:map
Status: open
Tracker: local Markdown; parent map and child filenames identify local issues.

## Destination

A shared research charter anchored in PointPillars, SWFormer, RSN, camera-BEV/
LET and R4D, with scientific questions, common protocols, measurable gates and
self-contained implementation tickets. Resolve program decisions before treating
the anchor papers as separate reproduction projects.

## Notes

Use ask-matt → wayfinder with grilling/domain-modeling for decisions, then
 to-spec → to-tickets. Existing source reviews and research-program draft are
inputs, not a substitute for the user's scientific priority decision.
Perception is primary; Motion/E2E are separate downstream suites. No TensorFlow;
Torch/JAX allowed. Waystone owns HDFS/local storage. Two validation scenes and
native-table tracer are engineering evidence; geometric dedicated-Insula R0
remains a prerequisite. Work stays in the existing isolated worktree.

## Decisions so far

Prior constraints and evidence are recorded in the
[existing program draft](../../../docs/superpowers/specs/2026-09-29-waymo-research-program-design.md)
and linked source reviews.

- [Choose the first scientific result](first-scientific-result.md) — controlled representation comparisons first; joint model and foundation-model transfer follow.

## Not yet specified

Representation comparison, joint-task architecture, temporal state and
uncertainty protocols, foundation-model role, research compute/data budgets,
and the progression from verified engineering fixtures to held-out evaluation.
Sharpen these after the first-result decision.

## Out of scope

Autonomous-driving deployment, full production-stack replication, automatic
cross-dataset scene joins, treating qualitative views as benchmark results.

## Latest steering

User requires the mathematical geometry foundation before encoder work; see
[geometry contract](../../../docs/superpowers/specs/2026-09-29-perception-geometry-foundation-design.md).
Independent detection/segmentation is confirmed. The full single-frame/history
research scope remains open; the geometry steering did not answer that question.

## Discussion decisions — 2026-09-30

- [Establish separate task baselines before SAM integration](task-baselines-and-sam.md) — independent detection and segmentation first; investigate SAM/SAM3 combinations afterwards.

Controlled forecasting is selected as the first downstream target following
[evaluation research](scene-understanding-evaluation.md); wider scene-understanding scope remains open.
[SAM integration research](sam-integration-mechanisms.md) informs the later combination decision.
M0 live Insula verification is already a binding prerequisite.

Approved progression: predicted-box frozen mask refinement first, controlled forecasting before planning. [Detailed contracts](../../../docs/superpowers/specs/2026-09-30-mask-refinement-and-forecasting-design.md).

## Executable task specifications

[Overall goal and acceptance policy](program-goal.md) and [numbered task index](../../../experiments/waymo-perception/research-task-index.md) translate the selected directions into 22 core and five conditional tickets. M0 is the first execution frontier. This decision map remains open for broader choices; it is not closed by creating task specifications.
