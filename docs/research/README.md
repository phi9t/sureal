# Research work: specs, tickets, queue and evidence

The research program currently uses versioned Markdown task specifications, execution plans, an experiment registry and an append-only evidence journal. These are different records with different responsibilities.

| Record | Question it answers | Home |
| --- | --- | --- |
| Program goal | What scientific outcome are we pursuing? | [Program goal](tasks/program-goal.md) |
| Design spec | What behavior, ownership and constraints are agreed? | `docs/superpowers/specs/` |
| Task spec | What independently reviewable deliverable closes one work item? | `docs/research/tasks/` |
| Implementation plan | Which exact files, interfaces, tests and steps implement the spec? | `docs/superpowers/plans/` |
| Task queue | Which work is ready, blocked, owned or awaiting review? | [Queue policy](task-queue.md) |
| Experiment registry | Which scientific recipes and run identities are defined? | `experiments/waymo-perception/research/experiment-registry.json` |
| Experiment results | What did actual runs and their independent gates establish? | Evidence-derived tracker and immutable receipts |
| Research journal | What observations, hypotheses and decisions followed? | Append-only `research-journal.jsonl` and its rendered Markdown |

## Convert a direction into work

1. Write the design spec: goal, scope, scientific invariants, ownership and acceptance.
2. Decompose it into deliverables that can each pass an independent review. Give each a stable numbered task file.
3. In each task, record goal, dependencies, exact deliverables, verifier, acceptance and evidence required for closure. A proposed task is not permission to bypass design or execution-plan review.
4. Write a separate implementation plan after the design is agreed. The plan decides concrete interfaces, source mappings, tests and executable live commands; task specs remain the acceptance contract.
5. Put the accepted dependency graph and ownership in the operational queue. Link back to the Git task file; do not copy mutable scheduling status into several competing files.
6. Claim ready work, implement in isolation, run its live Insula gates, independently audit outputs and retain evidence. Land owned changes when ready.
7. Close only the scope proved by evidence. A finite, properly verified research negative can close an investigation; an execution failure cannot masquerade as a research result.

## Models and training: the next architecture workstream

The user selected a [Sureal-local serial collaboration protocol](../superpowers/specs/2026-10-03-sureal-serial-collaboration-design.md) as the supporting stage after pristine mainline and before this scientific migration. Corenius is a design reference only.

[Design proposal](../superpowers/specs/2026-10-03-first-class-models-training-design.md).

| Task | Deliverable | Dependency |
| --- | --- | --- |
| [44](tasks/44-models-training-reference-admission.md) | Frozen reference and migration verification admission | Protocol 53; design/plan review |
| [45](tasks/45-first-class-models-and-layers.md) | First-class `sureal.models` with equivalent architectures | 44 |
| [46](tasks/46-first-class-training-policy-and-state.md) | First-class losses, optimizer policy and explicit state formats | 45 |
| [47](tasks/47-shared-fixed-frame-producer.md) | One maintained producer for the tier1 and advanced fixed-frame studies | 46 |
| [48](tasks/48-models-training-retention-and-closeout.md) | Discoverable commands, HDFS evidence and integration closeout | 47 |

Every implementation milestone runs actual live Insula and retains independent verification evidence. These tasks establish scientific code ownership; they do not claim new model quality, held-out improvement, segmentation or forecasting results.

## Sureal-local collaboration workstream

All implementation and authoritative task/spec documents belong in this repository. The protocol uses one persistent lead, initially one worker seat, task-scoped workspaces (recommended linked worktrees), exact candidates, conditional fast-forward landing and explicit recovery/cleanup. Runtime records and disposable workspaces stay outside canonical source to keep it pristine.

| Task | Deliverable | Dependency |
| --- | --- | --- |
| [49](tasks/49-collaboration-project-admission.md) | Clean-base admission, local state and lock | Current closeout; design/plan review |
| [50](tasks/50-collaboration-worker-attempts.md) | One fresh bounded worker in a task worktree | 49 |
| [51](tasks/51-collaboration-candidate-verification.md) | Immutable candidates, exact verification and repair | 50 |
| [52](tasks/52-collaboration-landing-recovery.md) | Exact fast-forward landing and interrupted-effect recovery | 51 |
| [53](tasks/53-collaboration-cleanup-closeout.md) | Safe cleanup and two real serial-task cycles | 52 |

Execution remains gated on clean mainline and written design/plan admission. These are specifications, not completed protocol capabilities. Once admitted, the local protocol carries models/training44–48. Kata remains optional scheduling support rather than a runtime dependency.

[Full research task index](../../experiments/waymo-perception/research-task-index.md) · [Existing experiment tracker](../../experiments/waymo-perception/tracking/README.md)
