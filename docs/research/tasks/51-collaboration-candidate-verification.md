# 51 — Immutable candidates and exact verification

Milestone: P2. Implementation home: Sureal.

**Goal:** freeze a single-commit candidate and bind lead review, live verification and repair to its exact content and task context.

**Dependencies:** 50.

**Spec:** [Sureal two-worker collaboration](../../superpowers/specs/2026-10-03-sureal-serial-collaboration-design.md).

**Implementation plan:** [Two-worker collaboration](../../superpowers/plans/2026-10-03-sureal-two-worker-collaboration.md); plan review precedes execution.

## Deliverables

- Submission requires one candidate C with exactly one parent B and clean owned workspace state.
- Immutable task/brief/base/attempt/commit/tree identity, report and controller-owned candidate-object retention.
- Separate immutable verification materialization with declared input/output paths, runtime and artifact identities.
- Explicit repair produces C2 and preserves C1/history; still-live WAITING-for-review attempts can use a new authorized turn, while terminal attempts receive a fresh claim/thread/workspace at the admitted brief/base; old candidate evidence never authorizes the new candidate.

## Verifiers

- Real Git probes cover zero/two commits, merge commits, wrong base, dirty index/tracked/untracked state and foreign task identity.
- Live Insula verifies the actual separately materialized candidate; independent audit reopens outputs and evidence bindings.
- Deliberately swap C/tree/brief/base or mutate the worker checkout; prove invalid evidence cannot authorize the current candidate.
- Verify one frozen candidate while the other worker continues in its own worktree; prove source/output identities and evidence cannot be mixed across attempts.

## Acceptance

- The candidate is identified by immutable content/context, not its branch name or worker report.
- Verification runs against C, with no mutable worker/build leftovers affecting its source; required mathematical/artifact checkers remain independent.
- Candidate retention survives worker amendment or disposable workspace removal.
- Review findings return to the worker; the lead never repairs C in place. Verification identity changes invalidate acceptance.

## Closure evidence

Retain all candidate objects/reports, exact verification materialization, commands/logs/exits, corruption/refusal results, independent live receipts and reviewed landed implementation.
