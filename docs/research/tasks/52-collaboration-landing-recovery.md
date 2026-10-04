# 52 — Exact fast-forward landing and recovery

Milestone: P3. Implementation home: Sureal.

**Goal:** land the exact reviewed candidate onto unchanged canonical mainline and recover interrupted effects without rewrites, duplicate execution or false completion.

**Dependencies:** 51.

**Spec:** [Sureal two-worker collaboration](../../superpowers/specs/2026-10-03-sureal-serial-collaboration-design.md).

## Deliverables

- Prepared landing record binds expected main B, candidate C, admitted brief and verified evidence under the exclusive controller lock.
- Fast-forward-only checkout integration and exact post-effect HEAD/tree/index/working-state verification.
- Separate publication and cleanup outcomes; uncertain push acknowledgement is reconciled by observing the configured remote ref.
- Recovery reads actual Git/candidate/process state rather than replaying uncertain launch/integration effects.

## Verifiers

- Live Insula real Git fixtures prove exact B→C integration and unchanged-base, wrong-candidate and dirty-mainline refusal.
- Interrupt before/after the Git effect and before result acknowledgement; recover correctly when main equals B, C or neither.
- Exercise publication acknowledgement loss against an owned fixture remote; refuse divergence and force operations.
- Independently verify resulting refs/trees and prepared/result evidence, not a controller `passed` flag.
- In a real Git fixture, construct two candidates from the same B. After landing one, prove the other is stale and cannot reuse its former verification. Also exercise serialized landing while an unrelated worker remains active in its distinct worktree; acceptance freezes only the submitted candidate and refuses shared-state uncertainty.

## Acceptance

- Reviewed C is the exact landed commit. Landing never rebases, merges divergent history, squashes, cherry-picks or fixes C after verification.
- `update-ref` alone is not used to move a checked-out canonical branch and leave stale working files.
- Shared unknown effects hold affected project mutation; demonstrably isolated attempt uncertainty holds its seat/conflicting scopes while unrelated known-safe work can continue. C already landed is reconciled without rerunning worker work or pretending cleanup/publication succeeded.
- Existing history is preserved; no forced remote update or rollback. Advisory locking is documented as cooperative, not exclusion of every external Git process.

## Closure evidence

Retain prepared/result/recovery records, exact refs/trees, fault/refusal fixtures, actual live commands/logs/exits, independent receipts and reviewed landed implementation.
