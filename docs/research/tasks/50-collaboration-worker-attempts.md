# 50 — Serial task-scoped worker attempts

Milestone: P1. Implementation home: Sureal.

**Goal:** start exactly one fresh bounded worker attempt from an immutable task brief and exact mainline base in a task-scoped Git workspace, initially a linked worktree.

**Dependencies:** 49.

**Spec:** [Sureal serial collaboration](../../superpowers/specs/2026-10-03-sureal-serial-collaboration-design.md).

## Deliverables

- Start captures task/brief/base/workspace/attempt identity before dispatch.
- Disposable linked worktree outside canonical source; unique `codex/<task-id>/<attempt-id>` branch. Record workspace kind/path and shared Git common-directory identity. Clone mode is an optional later implementation, not a prerequisite.
- Initial capacity one, with seat/task/attempt ownership recorded separately to permit later capacity expansion; fresh task thread/process; retained startup, exit and process disposition.
- Explicit aborted/unknown attempt handling; lost launch acknowledgement never blindly starts another worker.

## Verifiers

- Actual subprocess handoff inside live Insula with the admitted brief/base; independently reopen process and workspace evidence.
- In real Git fixtures, prove worktrees have separate files/index/HEAD and shared ordinary refs/objects; exercise owned-branch operations and canonical-mainline guard refusal. Record cooperative enforcement honestly; do not claim independent refs or OS isolation.
- Refuse a second start, foreign workspace, changed brief/base and unresolved process state.

## Acceptance

- Worker receives the exact admitted brief and starts at B; canonical source remains clean and unchanged.
- No two active attempts occupy the seat; unknown effects retain occupancy until reconciled.
- Worker permissions and actual launch adapter capabilities are recorded honestly; secrets are not stored in task records.
- Exiting a launcher is not assumed to stop all owned children. Attempt cleanup waits for actual stop evidence.

## Closure evidence

Retain task/brief/source/runtime pins, workspace/seat identity, dispatch/exit/process evidence, concurrent-start refusal, independent live receipts and reviewed landed implementation.
