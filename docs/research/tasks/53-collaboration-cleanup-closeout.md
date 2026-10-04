# 53 — Safe cleanup and concurrent-loop admission

Milestone: P4. Implementation home: Sureal.

**Goal:** admit the complete local lead–worker loop through two real concurrent bounded tasks, serialized exact landing, stale-candidate recovery, retained evidence and safe disposable-workspace cleanup.

**Dependencies:** 52; all 49–52 required receipts independently admitted.

**Spec:** [Sureal two-worker collaboration](../../superpowers/specs/2026-10-03-sureal-serial-collaboration-design.md).

## Deliverables

- Cleanup retains brief/candidate/report/verification/landing history and required scientific artifacts before removing only owned disposable state.
- Confirmed stopped attempts and refusal of canonical, foreign, symlinked or unresolved workspace deletion. Linked-worktree cleanup uses Git and preserves the common Git directory, retained candidate refs and other worktrees.
- Two actual worker sessions actively overlap on independent tasks T1/T2, in distinct worktrees/branches, both starting at B. T1 produces reviewed C and lands first; T2's retained D with parent B is refused as stale. Explicitly refresh T2 through a new claim/attempt/worktree at C, produce E with parent C and obtain fresh review/live verification before E lands. Select concrete independent task scopes in the implementation plan; model/training dependency gates remain intact.
- Local operating guide, recovery commands and handoff into models/training tickets44–48.

## Verifiers

- Actual worker/lead/controller loop with independently proven execution overlap, live Insula checks and candidate/integration evidence; scripted model-free fixtures complement but do not replace the actual worker handoff.
- Clean up one stopped attempt while the other worker is active; independently prove its files/branch/process remain unchanged. Interrupt cleanup after landing, retain LANDED plus pending cleanup, and resume without relaunching work or deleting foreign data. Exercise third-start, duplicate-task and shared-GPU/resource conflict refusal.
- Export/restore only the Sureal Kata project and reconcile owners/stages with retained execution receipts before claiming recovery.
- Retain/reopen protocol records and required research artifacts; use existing verified HDFS readback/live recovery before any scientific payload release.
- Reconcile the complete stage index and independently review the full implementation against this specification.

## Acceptance

- Initial capacity two is demonstrated by actual overlapping sessions at B with distinct writable workspaces. Landing is serialized: C lands, stale D is refused, then fresh E with parent C lands after its own verification. D's earlier evidence cannot authorize E; canonical source remains clean and ownership remains per seat/task/attempt.
- All required evidence and candidate objects survive cleanup; no unique unsubmitted work is discarded.
- Cleanup, publication and integration remain separately recorded facts. An uncertain outcome never frees a seat or marks the task complete.
- Sureal runs the protocol with its admitted shared Kata project and no Corenius runtime/code/policy dependency. Both pilot issues retain spec pins, real owner/session/attempt links and verified closure evidence; Kata stage and actual execution receipts reconcile.
- The admitted loop is ready to carry the scientific model/training workstream; protocol completion does not establish model quality.

## Closure evidence

Provide both overlapping task lifecycles, the stale D/refreshed E lineage, all independently audited stage receipts, actual process/cleanup outcomes, retained artifacts, exact landed heads and documented remaining limits. Unresolved stop/retention/cleanup gates leave closeout open.
