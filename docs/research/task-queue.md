# Research task queue policy

## Current mechanism and roles

At inspection on 2026-10-03, numbered Markdown files in `docs/research/tasks/` and the research task index define work. Execution order is documented in research notes and communicated to the worker with `codex queue`. The experiment tracker derives run status from receipts. Kata is installed, but the Sureal Git alias is not registered yet.

`codex queue` delivers a message to a worker session. It is not a dependency-aware work ledger. An experiment registry defines runs, not engineering ticket ownership. A design file describes the desired system, not what is ready to execute.

Proposed v1 ownership is file-backed through the Sureal controller. Kata remains an optional later queue backend; it has not been enabled by this proposal.

- Git mainline owns reviewed design specs, task acceptance, dependencies, implementation plans and versioned evidence manifests.
- The controller owns live claims, worker/session/attempt/workspace identities and candidate/integration state in durable project-local runtime records outside canonical source.
- The experiment registry/tracker and immutable journal own recipes, observed run outcomes and research interpretation.
- Optional issues in GitHub or Kata link to the stable Git task ID and spec revision. They are a discoverable view of work; issue assignment or closure alone does not grant a controller claim or establish acceptance.

## Mainline task definitions and worker claims

Land reviewed task specs and required plans on `phi9t/mainline` before admitting their implementation. Each task keeps its existing stable ticket ID and path. Admission reads the spec at the exact mainline base B, retains its Git blob/content identity and the linked design/plan identities, and verifies dependencies from actual closure evidence. Draft-only or branch-only definitions cannot enter the managed ready queue. A later acceptance change must land explicitly and create a new admitted brief; it cannot silently change a running attempt.

A ready task becomes assigned through one durable claim under the controller lock, before dispatch. Claim records contain:

| Field | Purpose |
| --- | --- |
| Project identity, task ID, spec path and revision | Identify the exact work and acceptance contract |
| Brief digest, exact base B, allowed scope/resources | Bind execution to its admitted inputs and authority |
| Claim ID/generation, attempt ID, worker seat | Identify the sole current owner and reject obsolete claims |
| Worker session/thread ID and owned process identity | Show which actual session is executing; capture both before dispatch where possible, or reconcile launch identity before RUNNING |
| Workspace kind/path, common Git directory, branch | Locate the owned source and record shared metadata |
| State, dispatch acknowledgement, progress/evidence references | Separate assigned, running, unknown, submitted and completed facts |

The lead selects a task; the controller refuses an existing active/unknown claim for that task, an occupied seat, unmet dependencies or conflicting declared write/resource scope. Future multiple seats still allow only one active owner per task. Scope checks use declared write sets and explicit shared-resource ownership; they do not prove that undeclared filesystem access is impossible.

The worker acknowledges the exact task/spec/brief/claim/attempt identities before implementation. If the launch adapter reveals its session ID only after launch, record STARTING, recover that identity and obtain the acknowledgement before marking RUNNING. A lost acknowledgement leaves the attempt unresolved, not available for reassignment. The detailed plan must specify the adapter and this handshake.

Every controller mutation, progress report, submission, repair and landing references the current claim generation and attempt. Read-only status shows task, spec revision, state/blocker, owner session, attempt, workspace/branch, base/candidate and evidence. Messaging with `codex queue` carries those identities; delivery alone is not a claim or start receipt. This controller/status interface is proposed, not implemented today.

### Takeover

An inactive-looking conversation, elapsed time or missing heartbeat is insufficient to free ownership. Inspect the actual worker/process/workspace state, stop or reconcile the prior attempt and preserve commits, unsubmitted changes, checkpoints and logs before release. An unresolved effect keeps the task occupied.

Under the lock, record the old attempt's disposition and invalidate its claim generation. Allocate a new claim, attempt, session and workspace; carry forward an explicit handoff manifest of retained work/evidence and recheck the current base/spec. Accepted patches or checkpoints are explicit inputs with provenance, not implicit inheritance of the old attempt's verification. The replacement acknowledges its new assignment; old-session updates and submissions are rejected. These tokens fence controller operations, not arbitrary processes with filesystem access; confirmed stop and workspace separation remain necessary.

Specs, reviewed handoff/closure evidence and useful journal updates land as ordinary owned commits. Mutable RUNNING/owner fields remain in runtime records so each assignment does not dirty mainline. Retain those records through the established storage/recovery process; issue comments and checked-in status snapshots, if used, are derived views with an observation time.

## Queue lifecycle

| Stage | Required condition | Scheduling representation |
| --- | --- | --- |
| Specified | Goal, deliverable, dependencies, verifiers and acceptance written | Open issue, linked spec |
| Needs decision | Design/plan or scientific activation unresolved | Explicit review-gate predecessor; `needs-human` label |
| Blocked | A prerequisite is not verified complete | Explicit `blocked-by` relationship |
| Ready | No open prerequisite; execution conditions admitted | Available in filtered ready queue |
| Claimed | Controller durably reserves task and seat before dispatch | Current claim/generation, attempt, session and workspace record |
| Running | Worker acknowledges assignment and actual execution starts | Matching claim/session/attempt plus dispatch and execution evidence |
| Needs verification | Candidate exists, required independent checks incomplete | `needs-verification` label; remains open |
| Needs landing | Required checks pass but integration incomplete | `needs-landing` label; remains open |
| Done | Ticket-specific acceptance and required integration pass | Evidence-backed close |

Status views and issue labels describe stage; they are not independent completion evidence. A gate closes only from its own proof. A finished fixed-batch negative can close a research investigation, while a timeout caused by failed resource admission leaves an implementation gate open.

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

## Optional future Kata integration

These commands apply only after a deliberate backend setup and workspace binding; they are operational guidance, not evidence of completed setup. If Kata is adopted, define one controller-backed ownership transition and reconciliation contract before dispatch; independent Kata and controller claims must not disagree.

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

## Manual bootstrap before controller admission

Until tickets49–53 implement and verify the controller, the persistent lead serializes assignments manually. Retain a timestamped assignment/handoff record with task/spec revision, worker session, attempt/workspace, blockers and evidence, and send the matching assignment through `codex queue`. Confirm worker acknowledgement and actual stop before reassignment. This is a cooperative manual procedure, not an implemented atomic claim service. It does not bypass pristine-mainline, design/plan or live execution gates.

## Persistence and reconciliation

Controller records must be retained and independently restored before claiming recovery. If Kata is later enabled, its database is not automatically stored in Git or HDFS because `.kata.toml` is checked in. Retain a project-scoped export with the repository's established storage process when creating a recovery checkpoint; do not export unrelated projects. Independently verify restoration before claiming disaster recovery.

If the operational queue and a Git spec disagree, stop that affected execution, inspect the version/evidence, and correct the queue or revise the spec explicitly. Preserve evidence and record the decision; never weaken a task's acceptance to make its queue status look complete.
