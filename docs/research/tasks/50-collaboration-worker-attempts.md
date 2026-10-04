# 50 — Two concurrent task-scoped worker attempts

Milestone: P1. Implementation home: Sureal.

**Goal:** run two fresh bounded worker sessions concurrently on independent admitted tasks, each from its exact brief/base in a distinct owned linked worktree.

**Dependencies:** 49.

**Spec:** [Sureal two-worker collaboration](../../superpowers/specs/2026-10-03-sureal-serial-collaboration-design.md).

**Implementation plan:** [Two-worker collaboration](../../superpowers/plans/2026-10-03-sureal-two-worker-collaboration.md); plan review precedes execution.

## Deliverables

V1 managed workers use bounded turns with no native goal. Exact-thread reports are corroborated by matching public item/report digest; CLI IDs alone are not authentication. Stop proof reads native goal/queue/turn and owned-process coverage twice; missing coverage holds ownership. The plan defines supervisor/approval/disconnect probes and lost-thread-creation reconciliation.

- Start claims Kata ownership under a unique attempt actor, pins the landed task spec/plan and captures task/brief/base/claim-generation/seat/workspace/attempt identity durably before dispatch. Capture/reconcile actual sessionId/primary-threadId/runtime-instance and owned tool/process handles and matching worker acknowledgement before RUNNING.
- Disposable linked worktree outside canonical source; unique `codex/<task-id>/<attempt-id>` branch. Record workspace kind/path and shared Git common-directory identity. Clone mode is an optional later implementation, not a prerequisite.
- Initial capacity two, with distinct task/session/seat/attempt/worktree/branch and writable output/cache/log identities; retained startup, exit and process disposition. Only short controller transitions are locked; worker execution overlaps.
- Normative dispatch handshake: prepared intent/seat → distinct-actor Kata claim/readback → revision-checked assignment → worktree receipt/base recheck → recorded fresh thread creation → matching work-turn acknowledgement. Lost creation/start acknowledgement never permits speculative redispatch.
- Explicit aborted/unknown attempt handling; lost launch acknowledgement never blindly starts another worker. Controlled takeover preserves old work/evidence, proves stop and invalidates the old claim; a subsequent task start creates the new acknowledged attempt/session/workspace.
- Task50 owns `task continue` and `refresh_task(..., runtime: Codex)`. Refresh retains prior work, proves stop, retires the old attempt and uses a fresh admitted base/claim/thread/worktree without inherited verification. `task takeover` only retires; replacement launch is a separate `task start`. The named refresh test and live gate case must pass before54 uses it.

**Runtime entity contract:** [Session/thread/turn/attempt model](../../superpowers/specs/2026-10-03-codex-runtime-domain-design.md).

## Verifiers

- Actual handoff to two worker sessions with the admitted briefs/bases and live Insula execution; independently prove overlapping active execution intervals and distinct primary thread/worktree identities and actual native session grouping/runtime/process handles; a shared app-server PID is allowed. Two sequential runs or two model-free subprocesses alone do not pass.
- In real Git fixtures, prove worktrees have separate files/index/HEAD and shared ordinary refs/objects; exercise owned-branch operations and canonical-mainline guard refusal. Record cooperative enforcement honestly; do not claim independent refs or OS isolation.
- Prove a turn can complete while the assigned goal/task remains active; multiple turns and resume preserve the same claim/attempt, while takeover/stale refresh bind fresh thread/attempt identities. Shared-session fork history never grants an owner or current-progress attribution.
- Exercise actual distinct-actor Kata claim contention and assignment metadata revision mismatch in an isolated fixture daemon/project; confirm unknown owner/metadata writes hold dispatch.
- Refuse a third start, duplicate task/seat/worktree/branch claims, overlapping declared write paths (including directory ancestry), conflicting output/resource ownership, foreign workspace, changed brief/base and unresolved process state. Exercise claim-write/launch/acknowledgement interruption and prove no duplicate dispatch after recovery.
- Run an actual worker handoff in live Insula: retain prior work, confirm stop, allocate replacement identities, acknowledge the new assignment, and reject old claim-generation progress/submission. Independently inspect ownership and session/workspace evidence.

## Acceptance

- Both workers receive their exact admitted briefs, start at their pinned bases and actively overlap; each writes only its owned scope and workspace. Canonical source remains clean and unchanged by worker execution.
- Kata is the single logical owner ledger; controller receipts bind its issue/actor/revision to the actual attempt. Duplicate queue claims are not maintained. No two active attempts occupy the seat or the same task; unknown effects retain occupancy until reconciled. Status identifies the actual owner session/attempt/workspace, and takeover cannot reuse an obsolete claim or verification.
- An unresolved isolated attempt occupies its seat/conflicting scopes without revoking known-safe work in the other seat. Unknown shared effects hold project mutation until reconciled. Shared GPU/resource ownership remains within existing limits.
- Worker permissions and actual launch adapter capabilities are recorded honestly; secrets are not stored in task records.
- Exiting a launcher is not assumed to stop all owned children. Attempt cleanup waits for actual stop evidence.

## Closure evidence

Retain task/brief/source/runtime pins, workspace/seat identity, dispatch/exit/process evidence, actual execution overlap and capacity/ownership-conflict refusal, independent live receipts and reviewed landed implementation.
