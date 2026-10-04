# Trunk development and reduced human steering

Authority: the user's October 4, 2026 direction. Source base at recording:
`a553645ef22761aa7708abf1ee109952a6cd2c38` on `phi9t/mainline`.

This records a standing development instruction and the desired operational
outcome for MAC. It does not claim the remaining MAC implementation is complete
or change a running experiment's acceptance, resource budget, or admitted brief.
The user requested temporary feature branches, prompt integration of coherent
work without a line-count constraint, and fresh mainline-based worktrees for
every new scoped assignment, including scouts.

## Standing development rules

1. **Start every new assignment from current mainline.** The lead records the
   exact `phi9t/mainline` base and creates a distinct worktree and temporary
   `codex/<task-or-attempt>` branch. Documentation, analysis and scout work obey
   this rule too. A continuation of an existing admitted attempt keeps its
   recorded identity; a new unrelated assignment does not reuse its branch.
2. **Scope by a coherent outcome.** Each assignment names its question or goal,
   permitted write/resource scope, deliverable, verifier, acceptance or research
   decision rule, and stop condition. Line count does not determine scope.
   A large coherent change can be appropriate; bundling unrelated work is not.
3. **Land verified coherent work promptly.** The lead owns integration rather
   than waiting for another human request or the whole program to finish.
   Preserve required reviews, live Insula gates and exact-candidate checks for
   the relevant ticket. Preparation and useful negative results can land with
   their actual status; they must not imply an unfinished implementation gate
   is closed. Do not invent GPU tests for documentation-only changes.
4. **Serialize landing, preserve concurrent development.** Each worker has its
   own mutable workspace. The integration controller is the sole mainline
   writer. A stale candidate is refreshed into the admitted current-base
   attempt and reverified under the existing contract before landing. Workers
   do not modify another worker's branch or silently change a pinned brief.
5. **Retire temporary branches deliberately.** After integration, confirmed
   writer/process stop, required retention and cleanup checks, record the
   attempt disposition and remove its disposable branch/worktree. Preserve
   history and evidence through the prescribed retention path. Unique legacy
   source and unresolved attempts require explicit disposition; this policy
   does not authorize discarding them.
6. **Bound scouts as work items.** Give each scout one question, source scope,
   time/resource limit, output and decision criterion. Land its report or
   accepted reusable code promptly. Classify a negative, inconclusive or
   rejected direction explicitly; avoid indefinite exploratory branches.

Until the controller is admitted, the persistent lead performs these actions
through the existing manual bootstrap procedure. The instruction applies now;
it is not a claim that automation or branch cleanup has been implemented.

## Concrete examples motivating the policy

| Observed example | Bounded next action and proof |
|---|---|
| The user repeatedly asked for implementation-worker status and how to send messages to it. | The lead maintains an issue/spec/attempt/thread/worktree mapping, reports the last verified outcome and next action, and sends identity-bound handoffs itself. An overview reconciles its claims against actual source receipts. |
| One implementation thread carried acquisition, training, storage, review, integration and MAC foundations. It recorded 960 turns and 60 compactions at the retrospective cutoff. | Use fresh bounded attempts with durable input, outcome and recovery briefs. A replacement starts from the brief and retained evidence. These counts establish history size, not waste or the cause of service overload. |
| The installed daemon's transport differed from the planned byte proxy; ticket49 audit and closure wrappers also needed corrections. | Freeze an adapter after a bounded installed-capability probe proves its transport, identities and stop coverage. Land the capability findings and corrective change with exact-source checks. |
| Single-frame fitting passed at 500 updates and confirmed at 750; balanced16 had only 125 visits per frame at 2,000 total updates. | Record exposure per frame before comparing learning difficulty. Keep normalization, supervision and exposure interventions separate; a matched-exposure comparison needs an explicitly admitted recipe. |
| Thirty training-eligible objects lacked positive assignments, while a GN backbone still retained pillar BN with an evaluation/batch-statistics loss gap. | Execute object-failure ledger42 before frozen-weight normalization diagnostic43; keep association41.2 separate. Reopen exact checkpoints and native per-class outcomes rather than selecting an architecture from total loss alone. |

The scientific examples and their limitations are recorded in the
[initial experiment analysis](../../experiments/waymo-perception/research/2026-10-03-initial-experiments-analysis.md).
The adapter/auditor example is recorded in the
[ticket49 closeout](reviews/2026-10-04-collaboration-ticket49-closeout.md).
The session retrospective is a separately reviewed candidate at
`4ae822b755d95df416d544ffaac131ba9a76a584`; its integration is independent of
this policy. None of these examples establishes a held-out architecture winner.

## Human MTS toil is an operational outcome

MAC should let the human MTS spend attention on scientific questions and
interpretation. The lead owns routine task selection within admitted priority,
dispatch, message relay, progress reconciliation, continuation within authority,
review repair, resource waiting, verification, retention and prompt landing.
The human should not need to repeatedly say "status", "proceed", "send this to
the worker", or "land it" to advance already authorized work.

Human decisions remain appropriate for new scientific objectives, changed
acceptance or resource authority, genuine access requirements, and unresolved
tradeoffs outside the admitted plan. A routine resource wait or failed check
with an authorized repair path belongs to the lead. New acceptance still lands
and is readmitted explicitly; reduced prompting never bypasses a verifier.

Every worker summary should answer: what task and question; last meaningful
verified result; current action; next safe action; and whether a particular
human decision is required. Include freshness and evidence links. Escalations
state the decision, available evidence, recommended choice and consequence of
waiting. Avoid repeated unchanged status notifications. Public summaries and
durable decisions support recovery without routine raw-transcript reading.

## Measuring the benefit

Use the existing MAC pilot and subsequent admitted research tasks to establish
a baseline and observed outcome. These are evaluation recommendations, not
silently amended acceptance for pinned tickets49–54:

- Count human operational interventions per accepted work item and experiment;
  distinguish requested scientific judgment from avoidable status, relay,
  continuation, recovery and landing prompts.
- Record the trigger, lead-owned remedy and human-required decision for each
  escalation. Repeated requests about the same unresolved operation remain
  separate interventions rather than being hidden by deduplication.
- Measure time waiting for an operational human response where timestamps
  support it. Do not infer human labor minutes from conversation duration.
- Exercise routine dispatch, continuation, correction of a failed check,
  integration and recovery within existing authority without human relay.
  Reopen receipts to prove the work advanced and the required gates held.
- Report accepted scientific outcomes alongside coordination counts. Fewer
  prompts without correct evidence, useful decisions and prompt landing is not
  success. No reduction or speedup has been measured yet.

If implementation requires new schemas, UI fields or closure criteria, land a
scoped spec/plan revision and update its admitted Kata binding before executing
those changes. The initial next step is to honor the standing lead duties while
finishing the already scoped MAC foundation, rather than expanding it into a
new infrastructure project.
