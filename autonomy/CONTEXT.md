# Perception research context

This glossary records the shared language for the research-program discussion.
Research choices remain in the linked charter and decision map.

- **Anchor paper:** a reference that motivates a mechanism or supplies a baseline;
  it does not by itself require a full paper reproduction.
- **Representation comparison:** a controlled experiment changing the encoding
  while declaring input evidence, supervision, head, compute and evaluation.
- **Scene understanding:** evidence-indexed geometry, semantic/instance state,
  relations and temporal state, with support/uncertainty and evaluable claims.
  A caption or a collection of boxes alone does not establish this capability.
- **Live implementation gate:** actual execution of the candidate in its locked
  dedicated Insula plus independently checked outputs and a verification receipt.
- **M0:** first milestone, proving the dedicated Insula itself works with
  synthetic computation/IO and real isolation checks; no Waymo data required.
- **Engineering fixture:** the acquired two-scene validation slice; useful for
  pipeline correctness, not training or a generalization benchmark.
- **Scientific gate:** preregistered held-out comparison and diagnostics beyond
  implementation correctness; live execution alone cannot prove a hypothesis.

Confirmed progression: representation comparisons, then a joint multimodal model,
then foundation-model transfer/distillation. Geometry precedes encoder work.
Perception anchors the program; Motion/E2E remain separate downstream suites.
No TensorFlow. Waystone owns HDFS/materialization. Every implementation milestone
requires live Insula verification, beginning with M0.

Confirmed 2026-09-30: independent detection and segmentation workstreams first,
then a SAM/SAM3 integration investigation. Scene understanding needs evaluation
and behavior-prediction/planning research before scope selection.

Open decisions: single-frame/history scope, operational scene-understanding
outputs, cohort and compute budgets,
initial models versus optional later mechanisms.

[Research charter](../docs/superpowers/specs/2026-09-29-waymo-research-program-design.md)
[Decision map](../docs/research/tasks/research-map.md)

Confirmed next directions: frozen predicted-detector-box mask refinement is the
first SAM integration experiment; controlled forecasting improvement is the
first downstream target. Planning follows its own later contract. See
[experiment contracts](../docs/superpowers/specs/2026-09-30-mask-refinement-and-forecasting-design.md).

[Actionable task index](research-task-index.md) records numbered goals, blockers,
verifiers and acceptance criteria. The [overall goal](../docs/research/tasks/program-goal.md) defines core closure and conditional follow-ons.

- **Tiny-subset overfit gate:** a training-only test requiring both declared loss reduction and independently scored detection quality; it does not establish generalization.
- **Architecture adaptation:** an explicit change to the reference model or task contract, distinguished from a faithful paper reproduction.
- **Training improvement:** a controlled gain in the declared task metric with support and resource evidence; a lower aggregate loss alone is insufficient.
- **Source pin:** the SHA-256 digest of one source file recorded in a receipt; the file is *pinned* by that receipt. Avoid: code hash, source hash, citation.
- **Source snapshot:** the frozen copy of the sources taken when a gate or study stage runs, which is what a source pin refers to. The working tree is not required to keep matching it.
