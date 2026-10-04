# 54 — Worker summaries and program overview

Milestone: O0. Implementation home: Sureal. Status: specified, not implemented.

**Goal:** let the user understand both workers, their tasks and the research queue from concise evidence-linked summaries and state views, without routinely reading raw transcripts.

**Dependencies:** 49–52; read-only session/history capability admitted on the effective runtime. Collection/view design can proceed earlier; complete live acceptance precedes53. Its live exercises run under this task using admitted49–52 capabilities; they do not depend on starting or closing53.

**Runtime entity contract:** [Session/thread/turn/attempt model](../../superpowers/specs/2026-10-03-codex-runtime-domain-design.md).

**Session-state contract:** [Operating state and progress health](../../superpowers/specs/2026-10-03-worker-session-state-design.md).

**Spec:** [Worker and program overview](../../superpowers/specs/2026-10-03-sureal-serial-collaboration-design.md#worker-and-program-overview).

## Deliverables

- Read-only local browser overview plus matching status JSON/text: two worker cards, centralized Kata queue, spec/task progress and recent-event timeline. Repository-owned implementation, no public deployment or separate queue authority.
- Each worker binds its actual session/primary-thread/current-turn/attempt/claim to issue/spec/plan revision and worktree/branch/base/candidate. Cards show goal/current focus, recent actions/results/findings, blocker/next step, observed runtime state, task workflow and verification/integration/publication/cleanup separately.
- Incremental transcript/progress summaries targeting at most 120 words per current worker card; evidence drilldown by item/event/artifact identity, grouped meaningful timeline and optional raw trace. Bounded generation path uses existing lead/worker workflow; actual public transcript/tool deltas corroborate checkpoints.
- Explicit IDLE/PURSUING/WAITING/BLOCKED/PAUSED/LIMIT_REACHED/FINISHED/ERROR/UNKNOWN operating view and native goal state, with separate HEALTHY/STUCK_SUSPECTED/HUNG_SUSPECTED/HUNG_CONFIRMED/UNKNOWN health, phase-policy thresholds, incident history and unblock/next-event evidence.
- Worker/attempt/task state graphs with highlighted current state and transition blockers; queue dependency explanation and spec admission/closure evidence links.
- Source-specific freshness/cursors/coverage, deduplication/reconnect/restart behavior, partial/stale/error indications and retained historical attempts/summaries. Five-second visible refresh and fifteen-second stale-source indication are the proposed targets.
- Scope to Sureal-owned session identities; exclude private reasoning/credentials/unrelated session content and escape rendered messages. Record actual server/schema capabilities; unsupported history cannot be hidden behind a fabricated narrative.

## Verifiers

- In the actual two-worker live pilot, independently compare both cards, issue/spec/claim/workspace mappings and state graphs with reopened Kata, Codex and controller/verification evidence. Confirm active overlap, resource waits, submission, stale-base refresh and per-seat cleanup display correctly.
- Read actual public session history without resuming or steering workers. Independently compare summary source anchors with recent actions/results, a failed check and corrective action, findings, blocker and next step. Statements based solely on a worker report remain labeled as such; independent pass/landed claims require matching receipts.
- Exercise right-session/wrong-thread, fork-inherited history and reused process incarnation; prove neither sessionId nor PID alone can merge worker summaries or completion evidence. Multi-turn, resume/reconnect and compaction retain the admitted ownership identity.
- Exercise mismatched issue/session/thread/turn/attempt/generation and mixed candidate evidence, duplicate/out-of-order events, paginated history gaps, compaction/takeover, source disconnect and observer restart. Prove no cross-worker summary bleed, invented progress or lost historical provenance.
- Exercise actual pursuit, known resource/tool wait, explicit pause, evidenced blocker/unblock, native goal limit/completion and task handoff under the applicable runtime/goal rules. Separately inject an alive repetitive/no-progress worker and an owned stalled operation with fresh observer, plus observer outage; independently audit operating/health distinctions. A suspicion cannot be upgraded to confirmed hang without explicit diagnosis evidence.
- Verify phase-aware long-job progress, failed experiments with new findings, idle-between-turn continuation gates, stale transport, recovery and out-of-order transitions. Prove timers/token chatter/identical retries cannot manufacture progress, and detector/label changes never mutate native goals or release/reassign an unresolved attempt.
- Advance observed material state on an owned live fixture and measure refresh; disconnect a source and measure explicit stale indication. Verify bounded collection/generation and that UI refresh does not invoke inference per token or per poll.
- Inspect the browser and CLI output from the same snapshot. Confirm goal/current work/blocker/next step and queue/spec status are understandable without opening raw transcript; use raw evidence only for the independent audit.
- Independently prove overview reads/refreshes do not claim/close issues, start/resume/interrupt sessions, mutate candidate/canonical source or change integration authority. Corrupt/unknown input renders an explicit error. Raw text cannot inject active markup or expose fixture credentials/unrelated session content.

## Acceptance

- Both actual concurrent workers are identifiable by their tasks/specs and unique primary-thread/attempt/workspace with actual native session grouping; reported queue state and observed execution discrepancies remain visible.
- Every independent completion/check/landing claim links to exact accepted evidence. Summaries distinguish observed, worker-reported and inferred content and clearly show coverage/freshness; elapsed silence is not treated as process termination.
- Every operating/health transition has exact identity, reason, since/duration, source evidence, effective policy and next-event/unblock condition. Missing phase thresholds or worker-specific liveness signals are explicit gaps; no global silence timeout infers a hung process or changes scientific execution budgets.
- State machines represent native goal, operating state/health, runtime, attempt, task workflow, Kata stage and spec/outcome as distinct views. EXITED does not imply DONE, idle does not free ownership, and LANDED does not imply publication/cleanup complete.
- UI meets measured five-second visible refresh and fifteen-second stale-source indication under the admitted local test conditions. Missing transcript capability or unclear current work leaves this task open until resolved or the contract is explicitly revised.
- A fresh observer reconciles retained identities/cursors and reopens summaries/evidence after restart or takeover, while the two-worker pilot and all prior ownership/live gates remain intact.

## Closure evidence

Retain live source/runtime pins, actual session/history read probes, paired UI/CLI snapshots, trace-summary source audits, refresh/outage timings, reconnect/identity/refusal results, retained historical summaries and reviewed landed implementation. Static mockups or self-reported screenshots alone do not close this task.
