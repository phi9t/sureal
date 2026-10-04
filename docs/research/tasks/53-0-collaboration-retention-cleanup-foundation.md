# 53.0 — Landed retention and cleanup foundation

Milestone: P3.5. Implementation home: Sureal. Status: specified, not implemented.

**Goal:** land independently verified retention, cleanup and pilot-check capabilities before the overview and final concurrent pilot need them.

**Dependencies:** 52. This stage was introduced by the user's request to fix the Claude review. It preserves every final53/54 acceptance requirement and removes their implementation-order cycle.

**Spec:** [Full collaboration specification](../../superpowers/specs/2026-10-03-sureal-serial-collaboration-design.md).

**Implementation plan:** [Two-worker collaboration](../../superpowers/plans/2026-10-03-sureal-two-worker-collaboration.md#task530-landed-retention-and-cleanup-foundation).

## Deliverables

- Retain unsubmitted work, candidates, reports, raw evidence and exact project-only Kata export; use pinned host Waystone transfer plus independent fresh GET and live Insula archive verification/rehydration.
- Validate actual stopped identity and workspace ownership before Git worktree cleanup; preserve retained refs/common directory and another active seat.
- Implement HDFS/cleanup interrupted-effect recovery, without releasing unique data or uncertain ownership.
- Implement the precommitted pilot guide/runbook check manifests and fixture preparation; no additional model workers are launched by documentation checks.
- Commit X before live verification; independently audit/review its exact source/context, then manually fast-forward X before54 or pilot baseB is admitted.

## Verifiers

- Actual live Insula fixture checks for canonical/foreign/symlink/live/unknown cleanup refusal, retained unsubmitted work and candidates, source/runtime/materialization identity and interrupted cleanup.
- Fresh HDFS manifest/archive readback, live verify/rehydrate and independent exact inventory union; uncertain PUT acknowledgement reconciles actual LS/GET, never overwrites mismatching content.
- Scoped queue export/restore into a fresh isolated database; inspect actual project/issues/dependencies and reconcile retained attempt receipts before any restored-project admission.
- Dispose one stopped owned worktree while a second actual worker remains active; independently read its unchanged files/ref/process incarnation.
- Verify pilot checker fixture command exits and raw readbacks, escaping/link/credential checks and required coverage. Actual native-launch success examples are checked against independently retained live handoffs, not replayed as new workers.

## Acceptance

- Exact verified X is on canonical mainline before54; code is available in both pilot worktrees at their later baseB.
- Retention/cleanup effects are independently verified and safely recoverable; unknown outcomes preserve work and ownership.
- The final actual two-worker C/D/E pilot remains required under53. Closing53.0 does not close53,54 or the protocol program.

## Closure evidence

Retain X/B/tree/source/runtime pins, actual commands/logs/resource proofs, independent HDFS/queue recovery audits, cleanup/refusal/fault evidence, unchanged-other-seat proofs, exact landing/publication and evidence-backed Kata closure.
