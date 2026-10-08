# 53 — Safe cleanup and concurrent-loop admission

Milestone: P4. Implementation home: Sureal.

**Goal:** admit the complete local lead–worker loop through two real concurrent bounded tasks, serialized exact landing, stale-candidate recovery, retained evidence and safe disposable-workspace cleanup.

**Dependencies:** 52; landed53.0; 54; all49–52/53.0 and worker/program overview54 receipts independently admitted. Runtime retention/cleanup implementation lands before the pilot baseB is selected; final53 closes only after the actual concurrent C/D/E loop.

**Spec:** [Sureal two-worker collaboration](../../superpowers/specs/2026-10-03-sureal-serial-collaboration-design.md).

**Implementation plan:** [Two-worker collaboration](../../superpowers/plans/2026-10-03-sureal-two-worker-collaboration.md); plan review precedes execution.

## Deliverables

- Cleanup retains brief/candidate/report/verification/landing history and required scientific artifacts before removing only owned disposable state.
- Confirmed stopped attempts and refusal of canonical, foreign, symlinked or unresolved workspace deletion. Linked-worktree cleanup uses Git and preserves the common Git directory, retained candidate refs and other worktrees.
- Two actual worker sessions actively overlap on independent tasks T1/T2, in distinct worktrees/branches, both starting at B. T1 produces reviewed C and lands first; T2's retained D with parent B is refused as stale. Explicitly refresh T2 through a new claim/attempt/worktree at C, produce E with parent C and obtain fresh review/live verification before E lands. Use the concrete53.A/53.B briefs below; model/training dependency gates remain intact.
- Local operating guide, recovery commands and handoff into models/training tickets44–48.

## Concrete pilot briefs

Both briefs are committed here before dispatch; Kata links to their pinned anchors, with stable IDs53.A and53.B and `related` context to53. Their predecessors are landed53.0 and admitted54. These are actual repository work, not practice issues. Neither modifies controller/model code, acceptance specs or shared scientific artifacts. Keep per-attempt mutable execution/evidence output paths distinct.

### Pilot task53.A

**Goal:** publish the verified local collaboration operating guide, so a user can inspect ready work, identify both owners, follow a candidate through live verification/landing and recover retained evidence.

**Write scope:** `docs/collaboration/operations/`; primary result `README.md`. Other source is read-only.

**Verifier:** run the admitted installed CLI status/help and the documented lifecycle commands against an owned live Insula fixture; independently compare guide steps with exact successful/refused effects and reopen linked evidence. Validate all local links and ensure no credential/raw transcript payload enters the guide.

**Acceptance:** guide identifies tool/runtime pins, native thread/attempt/claim ownership, two-worktree concurrency, required live acceptance, precise landing/closure semantics and retained recovery evidence. Each command example matches actual admitted CLI behavior. Candidate is independently accepted and lands as exact C with parent B.

### Pilot task53.B

**Goal:** publish the evidence-backed incident runbook, so a user can distinguish waiting, blocked, stuck, hung and observer outage, and understand safe takeover/stale-base recovery.

**Write scope:** `docs/collaboration/incidents/`; primary result `README.md`. Other source is read-only.

**Verifier:** run admitted read-only observation and refusal/recovery probes against owned live Insula fixtures; independently compare examples with native runtime/queue/controller evidence. Validate links, attribution, freshness and no automatic takeover/goal mutation claims.

**Acceptance:** runbook explains operating/health distinctions, effective phase policy, missing liveness signals, scope/claim uncertainty, retained handoff and stale-base refresh. It documents actual supported diagnosis/recovery operations. Initial candidate D has parent B and is retained/refused after53.A lands; fresh attempt produces E with parent C and obtains fresh review/live verification before exact landing.

These directory claims are disjoint. The implementation plan and committed `docs/collaboration/checks/{53.A,53.B}.json` supply executable commands/oracles;53.0 implements the helpers before pilot baseB is chosen. The complete independently fixture-verified runtime implementation must already be landed through53.0/54, so both workers can use it at B. Final53 is program admission through the real concurrent pilot, not permission to rewrite and later land an unlanded implementation candidate. Independent auditors decide acceptance. Any runtime correction suspends/restarts the pilot after a new exact verification/landing; final evidence commits have their own fresh source verification.

## Verifiers

- Actual worker/lead/controller loop with independently proven execution overlap, live Insula checks and candidate/integration evidence; scripted model-free fixtures complement but do not replace the actual worker handoff.
- Clean up one stopped attempt while the other worker is active; independently prove its files/branch/process remain unchanged. Interrupt cleanup after landing, retain LANDED plus pending cleanup, and resume without relaunching work or deleting foreign data. Exercise third-start, duplicate-task and shared-GPU/resource conflict refusal.
- Export/restore only the Sureal Kata project and reconcile owners/stages with retained execution receipts before claiming recovery.
- Retain/reopen protocol records and required research artifacts; use existing verified HDFS readback/live recovery before any scientific payload release.
- Exercise overview54 throughout both live workers and stale refresh; retain understandable summary/state/queue snapshots anchored to actual evidence.
- Reconcile the complete stage index and independently review the full implementation against this specification.

## Acceptance

- Initial capacity two is demonstrated by actual overlapping sessions at B with distinct writable workspaces. Landing is serialized: C lands, stale D is refused, then fresh E with parent C lands after its own verification. D's earlier evidence cannot authorize E; canonical source remains clean and ownership remains per seat/task/attempt.
- All required evidence and candidate objects survive cleanup; no unique unsubmitted work is discarded.
- Cleanup, publication and integration remain separately recorded facts. An uncertain outcome never frees a seat or marks the task complete.
- Sureal runs the protocol with its admitted shared Kata project and no Corenius runtime/code/policy dependency. Both pilot issues retain spec pins, real owner/session/attempt links and verified closure evidence; Kata stage and actual execution receipts reconcile.
- The admitted loop is ready to carry the scientific model/training workstream; protocol completion does not establish model quality.

## Closure evidence

Provide both overlapping task lifecycles, the stale D/refreshed E lineage, all independently audited stage receipts, actual process/cleanup outcomes, retained artifacts, exact landed heads and documented remaining limits. Unresolved stop/retention/cleanup gates leave closeout open.
