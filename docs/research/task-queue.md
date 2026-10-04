# Research task queue policy

## Current mechanism and roles

At inspection on 2026-10-03, numbered Markdown files in `docs/research/tasks/` and the research task index define work. Execution order is documented in research notes and communicated to the worker with `codex queue`. The experiment tracker derives run status from receipts. Kata is installed, but the Sureal Git alias is not registered yet.

`codex queue` delivers a message to a worker session. It is not a dependency-aware work ledger. An experiment registry defines runs, not engineering ticket ownership. A design file describes the desired system, not what is ready to execute.

Proposed v1 uses Kata as the centralized operational task ledger, with the Sureal controller providing worker dispatch and exact-candidate verification/integration. This supersedes the earlier optional-Kata/file-only queue proposal. Kata is installed and its local daemon is healthy, but Sureal is not yet registered; this document does not claim initialization or implementation.

- Git mainline owns reviewed design specs, task acceptance, dependencies, implementation plans and versioned evidence manifests.
- Kata owns queue priority, dependency edges, current logical owner and operational stage. Issue metadata/comments link each assignment to its actual worker session, attempt, workspace and evidence.
- The controller owns durable launch/process/candidate/verification/integration receipts outside canonical source. These records reconcile Kata updates; they are not a competing task queue or separately assignable owner ledger.
- The experiment registry/tracker and immutable journal own recipes, observed run outcomes and research interpretation.
- Each Kata issue links to the stable Git task ID and pinned spec/plan revision rather than copying their detailed acceptance. Optional GitHub issues are additional discussion/views. Kata assignment reserves work, while actual dispatch and completion require controller receipts.

## Mainline task definitions and worker claims

Land reviewed task specs and required plans on `phi9t/mainline` before admitting their implementation. Each task keeps its existing stable ticket ID and path. Admission reads the spec at the exact mainline base B, retains its Git blob/content identity and the linked design/plan identities, and verifies dependencies from actual closure evidence. Draft-only or branch-only definitions cannot enter the managed ready queue. A later acceptance change must land explicitly and create a new admitted brief; it cannot silently change a running attempt.

A ready task becomes assigned through a Kata owner claim coordinated under the controller lock, before dispatch. Kata metadata links the assignment fields below; controller receipts retain their exact historical values:

| Field | Purpose |
| --- | --- |
| Project identity, task ID, spec path and revision | Identify the exact work and acceptance contract |
| Brief digest, exact base B, allowed scope/resources | Bind execution to its admitted inputs and authority |
| Claim ID/generation, attempt ID, worker seat | Identify the sole current owner and reject obsolete claims |
| Native session ID, exact primary thread ID, runtime instance and owned process handles | Session groups threads; thread ID addresses the worker. Capture/reconcile actual launch identity before RUNNING; server PID may be shared |
| Workspace kind/path, common Git directory, branch | Locate the owned source and record shared metadata |
| State, dispatch acknowledgement, progress/evidence references | Separate assigned, running, unknown, submitted and completed facts |

The lead/controller selects a task from Kata’s unowned ready queue, rechecks its landed spec and dependencies, and claims it using a unique attempt actor (`--as sureal/<attempt-id>`). Default human/user identity is insufficient because separate sessions would look like the same owner. The controller refuses an existing active/unknown claim for that task, an occupied seat, unmet dependencies or conflicting declared write/resource scope. The two v1 seats allow independent tasks concurrently, with only one active owner per task and distinct worktrees/branches. Reject a third active attempt, overlapping declared write scopes and conflicting shared resources. Scope checks use declared write sets and explicit shared-resource ownership; they do not prove that undeclared filesystem access is impossible.

The worker acknowledges the exact task/spec/brief/claim/attempt identities before implementation. If the launch adapter reveals its thread/session IDs only after launch, record STARTING, recover that identity and obtain the acknowledgement before marking RUNNING. A lost acknowledgement leaves the attempt unresolved, not available for reassignment. The detailed plan must specify the adapter and this handshake.

Every controller mutation, progress report, submission, repair and landing references the current Kata issue/owner plus claim generation and attempt, and verifies that they still match. Read-only status shows task, spec revision, state/blocker, owner session, attempt, workspace/branch, base/candidate and evidence. Messaging with `codex queue` carries those identities; delivery alone is not a claim or start receipt. This controller/status interface is proposed, not implemented today.

### Takeover

An inactive-looking conversation, elapsed time or missing heartbeat is insufficient to free ownership. Inspect the actual worker/process/workspace state, stop or reconcile the prior attempt and preserve commits, unsubmitted changes, checkpoints and logs before release. An unresolved effect keeps the task occupied.

Hold only the affected seat and conflicting scopes while reconciling; uncertainty in shared Git/resource state holds all affected project mutation. Under the lock, record the old attempt's disposition and invalidate its claim generation before releasing/transferring the Kata owner. Allocate a new Kata claim, attempt, session and workspace; carry forward an explicit handoff manifest of retained work/evidence and recheck the current base/spec. Accepted patches or checkpoints are explicit inputs with provenance, not implicit inheritance of the old attempt's verification. The replacement acknowledges its new assignment; old-session updates and submissions are rejected. These tokens fence controller operations, not arbitrary processes with filesystem access; confirmed stop and workspace separation remain necessary.

Specs, reviewed handoff/closure evidence and useful journal updates land as ordinary owned commits. Mutable queue stage/owner fields live in Kata, with execution receipts outside source, so each assignment does not dirty mainline. Retain those records through the established storage/recovery process; issue comments and checked-in status snapshots, if used, are derived views with an observation time.

### Broker and execution boundary

Use one existing local Kata daemon/project for all Sureal worktrees, with a committed `.kata.toml` binding. All workers connect to that same database through the daemon. A later remote daemon can serve multiple hosts; v1 has one local controller and initial capacity two, with separate writable task worktrees. Only short state transitions and mainline landing are serialized. HDFS retains project-scoped exports and evidence, not the live SQLite database.

Kata supplies ready/next queries, owner claims, priority, blocked-by edges, comments/metadata, events and human queue views. It does not launch workers, allocate GPUs or prove that a process is running. The controller provides that dispatch boundary and reports verified runtime facts back to Kata. Two worker sessions may execute concurrently, while GPU work remains serialized by the existing resource lock and each attempt has distinct writable output/cache paths. A RUNNING label without matching launch/acknowledgement evidence is a reconciliation discrepancy.

A claim, each pre-/post-thread metadata update, launch and issue comment are separate effects, keyed by operation ID and step. A reused ID with a different input digest is refused. Before them, persist a controller intent binding issue, spec, unique actor and attempt. Claim the issue, re-read owner/revision, then publish one assignment metadata object using supported revision-conditional metadata updates before launch. Use idempotency keys for issue creation and explicit event/receipt identities for updates. If a call fails or its acknowledgement is lost, inspect Kata and actual process state; retain ownership and mark pending reconciliation rather than dispatch twice or silently switch to a file-only queue. The [full v1 spec](../superpowers/specs/2026-10-03-sureal-serial-collaboration-design.md#kata-admission-and-dispatch-handshake) fixes durable ordering and readback/recovery contracts; the implementation plan supplies concrete adapter functions and executable crash tests. Raw `--force` or manual owner/metadata changes do not transfer a running process safely; the controller must detect and reconcile them.

The installed Kata v0.14.3 supports `claim`, `ready`, `--blocked-by`, `--as`, metadata `--if-match`, events and project-scoped export. Current upstream documentation has newer flags; implement against the admitted installed version or explicitly admit an upgrade. At inspection, `kata whoami` resolves to `philip.yang`, confirming the need for distinct attempt actors.

Sources: [Kata quickstart](https://github.com/kenn-io/kata/blob/main/docs/get-started/quickstart.md), [shared-project model](https://github.com/kenn-io/kata/blob/main/docs/workflows/sharing.md), and installed `kata version`, `quickstart` and command help. Runtime inspections are configuration evidence, not completed integration gates.

The [Codex runtime entity model](../superpowers/specs/2026-10-03-codex-runtime-domain-design.md) distinguishes native session grouping, exact worker thread, turn, item and thread-scoped goal. Claim/dispatch/summary joins require the thread ID; shared sessionId or daemon PID does not identify an owner.

## User-facing worker and queue overview

[Task54](tasks/54-worker-program-observability.md) provides the read-only view of both sessions, current issue/spec/workspace mappings, concise evidence-linked trace summaries, per-worker state graphs and the centralized queue. It displays source freshness and reconciliation discrepancies, not a new scheduling authority. Detailed task/spec outcomes remain linked to landed definitions and accepted evidence; historical unaudited research items remain explicitly unknown. Full-loop admission53 depends on this overview running during the actual concurrent pilot.

Worker operating state and progress health follow the [session-state contract](../superpowers/specs/2026-10-03-worker-session-state-design.md). Kata stage/owner do not substitute for native goal/runtime observation; stuck/hung suspicion preserves ownership and links to diagnostic evidence, while BLOCKED names the actual unblock condition.

## Queue lifecycle

| Stage | Required condition | Scheduling representation |
| --- | --- | --- |
| Specified | Goal, deliverable, dependencies, verifiers and acceptance written | Open issue, linked spec |
| Needs decision | Design/plan or scientific activation unresolved | Explicit review-gate predecessor; `needs-human` label |
| Blocked | A prerequisite is not verified complete | Explicit `blocked-by` relationship |
| Ready | No open prerequisite; execution conditions admitted | Available in filtered ready queue |
| Claimed | Kata owner reserved through controller before dispatch | Unique actor plus assignment metadata and durable attempt receipt |
| Running | Worker acknowledges assignment and actual execution starts | Matching claim/session/attempt plus dispatch and execution evidence |
| Needs verification | Candidate exists, required independent checks incomplete | `needs-verification` label; remains open |
| Needs landing | Required checks pass but integration incomplete | `needs-landing` label; remains open |
| Done | Ticket-specific acceptance and required integration pass | Evidence-backed close |

Status views and issue labels describe stage; they are not independent completion evidence. A gate closes only from its own proof. A finished fixed-batch negative can close a research investigation, while a timeout caused by failed resource admission leaves an implementation gate open.

## Initial queue and ordering

The full collaboration specification is user-approved. The [implementation plan](../superpowers/plans/2026-10-03-sureal-two-worker-collaboration.md) fixes code homes, interfaces, command flags, tests and live gates for49–54; it awaits plan review. This documentation decision does not claim Kata registration, worker dispatch or a pristine canonical checkout.

Preserve the existing [approved research execution order](../../experiments/waymo-perception/research/2026-10-03-approved-execution-order.md): resource admission, frozen sustained continuation, diagnostic 42 before 43, and isolated association 41.2. The new architecture lane does not silently reorder or mutate those experiments.

The models/training architecture lane is:

```text
current task + owned integration closeout
    -> pristine phi9t/mainline
    -> local protocol 49 -> 50 -> 51 -> 52 -> 53.0 -> 54 -> 53
    -> models/training 44 -> 45 -> 46 -> 47 -> 48
```

The user selected the [Sureal-local two-worker collaboration protocol](../superpowers/specs/2026-10-03-sureal-serial-collaboration-design.md) as the next supporting stage. Corenius is a design reference only. Models/training remains the first scientific architecture migration. Both workstreams require their written design/plan review before execution. Planning and read-only reference discovery may proceed while execution gates are open; active frozen inventories and the original scientific contracts remain preserved.

The protocol's initial scheduling uses Kata with capacity two: the lead selects up to two independent admitted ready issues; the controller coordinates its Kata claim, per-seat execution receipts and serialized landing. Kata is the operational queue; committed specs and independently reopened evidence remain acceptance authority. A closed issue alone cannot authorize landing or unblock actual execution without its required closure evidence.

After protocol admission, each managed task starts in its own task-scoped workspace (linked worktrees are recommended initially) and each verification uses a separately materialized immutable candidate. Existing worktrees remain part of the pre-protocol integration inventory; do not delete them without an explicit disposition. All actual GPU verification still shares the existing exclusive experiment lock.

When registering Sureal and importing Kata tasks, start with these scoped architecture items and the current relevant research follow-ups, not a bulk claim that all historical tickets have been reconciled. Import additional existing tickets after inspecting their latest acceptance and receipts; preserve old filenames/numbers.

## Kata operating procedure after admission

These commands apply after deliberate project setup and workspace binding; they are operational guidance, not evidence of completed setup. The implemented controller coordinates claims/assignment metadata and dispatch; below shows the underlying queue operations, not a complete crash-safe launch procedure.

```bash
kata ready --unowned --no-label needs-human --agent
kata show ISSUE_REF --agent
kata claim ISSUE_REF --as sureal/ATTEMPT_ID --agent
```

Before claiming: read the linked design, task spec and execution plan; verify prerequisites and live resource ownership. Do not treat a ready listing as permission to bypass an acceptance gate.

Record assignment identities in revision-checked metadata and append worktree/branch/session context in a comment. Read back both owner and assignment before dispatch. Update the issue with the exact candidate and independent verification artifacts. Land only ready owned changes; keep unrelated scratch/raw/auth files out of commits.

```bash
kata comment ISSUE_REF --body-stdin --agent < NOTE.md
kata close ISSUE_REF --done \
  --message 'State the scoped deliverable and actual independent verification.' \
  --commit LANDED_SHA \
  --evidence 'reviewed-paths:docs/research/tasks/TASK.md' \
  --evidence 'test:ACTUAL_LIVE_COMMAND' --agent
```

Use installed supported CLI options; `kata comment --help` is authoritative for comment text input. The inspected v0.14.3 supports `--body`, `--body-file` and `--body-stdin`. A close asserts completion. The message and linked evidence must cover this ticket's live Insula, retention and landing criteria; a commit hash alone does not prove them.

Use explicit `--blocked-by` relationships for execution ordering. Do not rely on project grouping or `related` links to block work. Search before creation and use stable idempotency keys. Workers claim ownership before making overlapping changes.

## Manual bootstrap before controller admission

Until tickets49–54 implement and verify the controller, the persistent lead serializes assignments manually. Retain a timestamped assignment/handoff record with task/spec revision, worker session, attempt/workspace, blockers and evidence, and send the matching assignment through `codex queue`. Confirm worker acknowledgement and actual stop before reassignment. This is a cooperative manual procedure, not an implemented atomic claim service. It does not bypass pristine-mainline, design/plan or live execution gates.

## Persistence and reconciliation

Controller records must be retained and independently restored before claiming recovery. Kata’s database is not automatically stored in Git or HDFS because `.kata.toml` is checked in. Retain a project-scoped export with the repository's established storage process when creating a recovery checkpoint; do not export unrelated projects. Independently verify restoration before claiming disaster recovery.

If the operational queue and a Git spec disagree, stop that affected execution, inspect the version/evidence, and correct the queue or revise the spec explicitly. Preserve evidence and record the decision; never weaken a task's acceptance to make its queue status look complete.

The user-requested review fixes introduce [53.0](tasks/53-0-collaboration-retention-cleanup-foundation.md) between52 and54. This lands retention/cleanup before54 verifies its display and before final53 launches the pilot. All final two-worker/HDFS/cleanup acceptance remains required. Task52 supplies evidence-backed closure; before its admission, the lead retains actual manual Kata close/readback evidence.
