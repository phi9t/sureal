# 50 — Serial task-scoped worker attempts

Milestone: P1. Implementation home: Sureal.

**Goal:** start exactly one fresh bounded worker attempt from an immutable task brief and exact mainline base in an independent Git clone.

**Dependencies:** 49.

**Spec:** [Sureal serial collaboration](../../superpowers/specs/2026-10-03-sureal-serial-collaboration-design.md).

## Deliverables

- Start captures task/brief/base/workspace/attempt identity before dispatch.
- Independent disposable clone outside canonical source; task branch uses `codex/` prefix. No linked worktree/shared Git refs in v1.
- One serial worker seat and fresh task thread/process; retained startup, exit and process disposition.
- Explicit aborted/unknown attempt handling; lost launch acknowledgement never blindly starts another worker.

## Verifiers

- Actual subprocess handoff inside live Insula with the admitted brief/base; independently reopen process and workspace evidence.
- Change private clone refs and prove canonical refs remain unchanged; do not claim OS isolation merely from independent Git metadata.
- Refuse a second start, foreign workspace, changed brief/base and unresolved process state.

## Acceptance

- Worker receives the exact admitted brief and starts at B; canonical source remains clean and unchanged.
- No two active attempts occupy the seat; unknown effects retain occupancy until reconciled.
- Worker permissions and actual launch adapter capabilities are recorded honestly; secrets are not stored in task records.
- Exiting a launcher is not assumed to stop all owned children. Attempt cleanup waits for actual stop evidence.

## Closure evidence

Retain task/brief/source/runtime pins, clone identity, dispatch/exit/process evidence, concurrent-start refusal, independent live receipts and reviewed landed implementation.
