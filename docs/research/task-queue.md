# Research task queue policy

## Current mechanism and roles

At inspection on 2026-10-03, numbered Markdown files in `docs/research/tasks/` and the research task index define work. Execution order is documented in research notes and communicated to the worker with `codex queue`. The experiment tracker derives run status from receipts. Kata is installed, but the Sureal Git alias is not registered yet.

`codex queue` delivers a message to a worker session. It is not a dependency-aware work ledger. An experiment registry defines runs, not engineering ticket ownership. A design file describes the desired system, not what is ready to execute.

Recommended operational arrangement, pending the user's backend choice:

- Git owns design specs, task acceptance, plans and versioned evidence manifests.
- Kata owns current task status, owners, priorities and explicit dependency edges.
- The experiment registry/tracker and immutable journal continue to own recipes, observed run outcomes and research interpretation.
- A Git mapping records stable ticket number/spec path to Kata identity, without duplicating mutable status or ownership.

## Queue lifecycle

| Stage | Required condition | Scheduling representation |
| --- | --- | --- |
| Specified | Goal, deliverable, dependencies, verifiers and acceptance written | Open issue, linked spec |
| Needs decision | Design/plan or scientific activation unresolved | Explicit review-gate predecessor; `needs-human` label |
| Blocked | A prerequisite is not verified complete | Explicit `blocked-by` relationship |
| Ready | No open prerequisite; execution conditions admitted | Available in filtered ready queue |
| Claimed | One worker accepts responsibility | Atomic Kata claim; worktree/session context in comment |
| Running | Actual implementation/execution started | Owner plus `running` label and evidence/progress comments |
| Needs verification | Candidate exists, required independent checks incomplete | `needs-verification` label; remains open |
| Needs landing | Required checks pass but integration incomplete | `needs-landing` label; remains open |
| Done | Ticket-specific acceptance and required integration pass | Evidence-backed close |

Labels describe stage; they are not independent completion evidence. A gate closes only from its own proof. A finished fixed-batch negative can close a research investigation, while a timeout caused by failed resource admission leaves an implementation gate open.

## Initial queue and ordering

Preserve the existing [approved research execution order](../../experiments/waymo-perception/research/2026-10-03-approved-execution-order.md): resource admission, frozen sustained continuation, diagnostic 42 before 43, and isolated association 41.2. The new architecture lane does not silently reorder or mutate those experiments.

The models/training architecture lane is:

```text
current task + owned integration closeout
    -> pristine phi9t/mainline
    -> local protocol 49 -> 50 -> 51 -> 52 -> 53
    -> models/training 44 -> 45 -> 46 -> 47 -> 48
```

The user selected the [Sureal-local serial collaboration protocol](../superpowers/specs/2026-10-03-sureal-serial-collaboration-design.md) as the next supporting stage. Corenius is a design reference only. Models/training remains the first scientific architecture migration. Both workstreams require their written design/plan review before execution. Planning and read-only reference discovery may proceed while execution gates are open; active frozen inventories and the original scientific contracts remain preserved.

The protocol's initial scheduling is file-backed and serial: the lead selects one admitted Git task, and the local controller owns per-seat attempt/candidate state and serialized landing state, initially with capacity one. It does not require Kata initialization. If Kata is later enabled, it supplies ownership/priorities/dependencies without replacing exact-candidate admission or becoming a second authority for scientific outcomes.

After protocol admission, each managed task starts in its own task-scoped workspace (linked worktrees are recommended initially) and each verification uses a separately materialized immutable candidate. Existing worktrees remain part of the pre-protocol integration inventory; do not delete them without an explicit disposition. All actual GPU verification still shares the existing exclusive experiment lock.

When enabling Kata, start with these scoped architecture items and the current relevant research follow-ups, not a bulk claim that all historical tickets have been reconciled. Import additional existing tickets after inspecting their latest acceptance and receipts; preserve old filenames/numbers.

## Worker procedure with Kata

These commands apply once the workspace is bound; they are operational guidance, not evidence of completed setup.

```bash
kata ready --unowned --no-label needs-human --agent
kata show ISSUE_REF --agent
kata claim ISSUE_REF --agent
```

Before claiming: read the linked design, task spec and execution plan; verify prerequisites and live resource ownership. Do not treat a ready listing as permission to bypass an acceptance gate.

Record the worktree, branch and worker session in a comment. Update the issue with the exact candidate and independent verification artifacts. Land only ready owned changes; keep unrelated scratch/raw/auth files out of commits.

```bash
kata comment ISSUE_REF --body-file NOTE.md --agent
kata close ISSUE_REF --done \
  --message 'State the scoped deliverable and actual independent verification.' \
  --commit LANDED_SHA \
  --evidence 'reviewed-paths:docs/research/tasks/TASK.md' \
  --evidence 'test:ACTUAL_LIVE_COMMAND' --agent
```

Use actual supported CLI options; `kata comment --help` is authoritative for comment text input. A close asserts completion. The message and linked evidence must cover this ticket's live Insula, retention and landing criteria; a commit hash alone does not prove them.

Use explicit `--blocked-by` relationships for execution ordering. Do not rely on project grouping or `related` links to block work. Search before creation and use stable idempotency keys. Workers claim ownership before making overlapping changes.

## Git-only fallback

If Kata is not enabled, keep the same task specs and dependency graph. A checked-in queue ledger must record ticket ID, owner, worktree, blockers and evidence links; workers serialize claims through an agreed single queue owner before implementation. Do not pretend file edits provide Kata's atomic claim behavior. `codex queue` remains a delivery channel for the ledger owner's assignment.

## Persistence and reconciliation

The Kata database is not automatically stored in Git or HDFS because `.kata.toml` is checked in. Retain a project-scoped export with the repository's established storage process when creating a recovery checkpoint; do not export unrelated projects. Independently verify restoration before claiming disaster recovery.

If the operational queue and a Git spec disagree, stop that affected execution, inspect the version/evidence, and correct the queue or revise the spec explicitly. Preserve evidence and record the decision; never weaken a task's acceptance to make its queue status look complete.
