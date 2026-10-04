# Sureal Two-Worker Collaboration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Preserve the previously selected inline execution method unless the user changes it; the two managed worker seats are product acceptance requirements.

**Goal:** implement a dependable local two-worker research workflow with Kata ownership, understandable evidence-backed status, exact candidate verification and recoverable mainline integration.

**Architecture:** a thin Python command delegates to private collaboration modules; Kata remains the operational queue. Durable operation receipts live outside canonical source, separate worker threads own separate worktrees, and one controller serializes integration. A read-only observer projects the same snapshots into JSON, text and local HTML.

**Tech Stack:** Python standard library, unittest, Git, installed Kata/Codex, additive live Insula runtime and the existing resource/HDFS verification helpers. No new scientific dependencies, frontend framework, database or daemon.

**Spec:** [approved full specification](../specs/2026-10-03-sureal-serial-collaboration-design.md), including its [runtime identities](../specs/2026-10-03-codex-runtime-domain-design.md), [worker state contract](../specs/2026-10-03-worker-session-state-design.md) and [queue policy](../../research/task-queue.md).

Status: implementation plan written after full-spec approval; awaiting plan review. No implementation milestone is closed by this document. Dates use the client timezone.

## Global Constraints

- Canonical integration remains `refs/heads/phi9t/mainline`.
- At most two admitted active worker seats; one active owner per task. STARTING/UNKNOWN attempts retain occupancy.
- Each attempt has a distinct primary thread, worktree, unique `codex/<task-id>/<attempt-id>` branch and writable output/cache/log paths.
- Reviewed task specs and required plans are on mainline before task admission; pin exact revisions, source B, brief digest, authorized write scope and resource rules.
- Submission retains one candidate C with exactly one parent B, its tree/context and a clean owned source checkout. Retain all rejected/superseded candidates before amendment/removal.
- Landing serializes integration, requires clean current mainline exactly B, and advances to exact reviewed C with fast-forward-only checkout integration. No post-verification rewrite, patch, fix, merge, squash or forced ref update.
- Runtime state lives in configurable sibling `../.sureal-collab/<project-id>/`, on a local filesystem with admitted lock/atomic-write semantics. Canonical source stays clean. HDFS stores recovery exports/evidence, not live SQLite or controller locking files.
- GPU/RAM/raw/local-storage limits and existing exclusive experiment lock remain unchanged; two workers do not imply two GPU jobs.
- Every implementation milestone retains actual live Insula commands/logs/exits, source/runtime pins, independent reopened artifacts, refusal/fault results and exact landed evidence.
- Summaries target at most 120 words per current worker card. Visible overview polls every 5 seconds; each source shows its own timestamp and becomes stale after 15 seconds without successful observation.
- Corenius is read-only reference material. All implementation, specs and task definitions live in Sureal.

## Review Focus

1. Paths with spaces, symlink aliases and submodules must not escape ownership or become shell commands: task49 admission and task50 scope tests.
2. Disk-full/fsync failure and valid-record/missing-projection crashes must preserve an unresolved effect rather than authorize a retry: task49 durability tests.
3. Shared session IDs, reused PIDs and successful daemon probes must not identify or certify a worker: task50 identity and task54 liveness tests.
4. A lost remote acknowledgement after actual publication must not cause a second integration or false closure: task52 recovery tests.
5. Paginated/compacted history and malicious transcript text must show gaps and render safely without exposing private content: task54 collection and browser tests.

## Bootstrap, source mapping and execution order

Order: existing worker owned closeout → pristine mainline → **49 → 50 → 51 → 52 → 54 → 53 → models/training44–48**. The already-authorized inline workflow implements the dependent controller stages; product concurrency is independently demonstrated in50/54 and the final53.A/53.B pilot. Two seats do not bypass dependency edges.

Before task49 execution, land the approved spec bundle and accepted plan through the existing manually reviewed workflow. Preserve current worker priority. Independently record outstanding-work disposition, stopped canonical writers, exact base/ref/tree/index/untracked cleanliness and required remote readback. A dirty or uncertain mainline blocks runtime initialization; do not clean by deleting or ignoring outstanding work.

The plan fixes these source homes. Tests use `python3 -m unittest discover -s tests/collab -p 'test_*.py' -v`, matching the existing unittest convention. `scripts/collab.py` bootstraps the repository root for imports and stays a parser/dispatcher; collaboration code does not belong in the future scientific `sureal.models`/`sureal.training` packages. Do not alter Surflo packaging/dependencies for this tooling.

| Files | Responsibility / first task |
| --- | --- |
| `scripts/collab.py`, `scripts/_collab/__init__.py`, `cli.py`, `contracts.py` | Typed records, refusal/result envelope and command dispatch /49 |
| `scripts/_collab/store.py`, `admission.py`, `git_workspace.py` | Journal/lock, project/task admission, Git/worktree identity /49, extended50 |
| `scripts/_collab/kata.py`, `codex.py`, `attempts.py` | Versioned real adapters and task-owner dispatch/handoff /49–50 |
| `scripts/_collab/candidates.py`, `verification.py` | Retention, materialization and exact evidence binding /51 |
| `scripts/_collab/landing.py`, `recovery.py` | Conditional landing and actual-effect reconciliation /52 |
| `scripts/_collab/observations.py`, `health.py`, `overview.py`, `overview.html` | Scoped public source collection, pure diagnosis and read-only views /54 |
| `scripts/_collab/retention.py`, `cleanup.py` | Scoped export/HDFS recovery and owned disposal /53 |
| `scripts/collab_live.py`, `tests/collab/live_support.py`, `audit_live.py` | Live fixture orchestration and separately executed artifact audit /49, extended each stage |
| `tests/collab/test_{admission,store,kata,attempts,candidates,verification,landing,recovery,observations,health,overview,cleanup,retention}.py` | Meaningful refusal/crash/identity tests in the owning task |
| `docs/collaboration/README.md`, `.kata.toml`, `docs/research/kata-task-map.json` | Discoverability, shared project binding and stable task-to-issue links /49 |

Use `JsonObject = dict[str, object]` and opaque string IDs. Define frozen dataclasses in `contracts.py`: `Project`, `TaskBrief`, `Attempt`, `Candidate`, `Verification`, `Effect`, `Closure`, `Snapshot`, `Refusal` and `Result`. Their required fields come directly from the full spec's record table; serialize with schema version1. `Result` has `operation_id`, `outcome`, `record_id`, `reason`, `evidence`; outcomes are `ok`, `refused`, `unknown`. JSON commands emit one envelope, exit0 for completed read/operation,2 for refusal,3 for unknown/corruption. These are command results, not task acceptance.

Define `digest(value: JsonObject) -> str` over UTF-8 `json.dumps(..., sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)`; reject duplicate JSON keys/nonfinite numbers and unknown schema versions. Journal records include sequence, previous event digest, operation identity and immutable record digest. All external command APIs accept argv arrays, explicit cwd and timeout; never use `shell=True`.

## Command and evidence contracts

Every command takes explicit `--project-state PATH`. `init` instead takes `--canonical PATH --state PATH --admission FILE`. `status` supports `--format json|text`. Mutations require `--operation-id ID`; a repeated ID first reconciles the retained effect and never blindly replays it.

| Command | Required additional arguments |
| --- | --- |
| `task import` | `--task-map FILE`; updates an owned metadata worktree, then manually reviewed binding/map commit |
| `task start` | `--task ID --brief FILE`; controller assigns seat/attempt IDs |
| `task checkpoint` | `--attempt ID --generation ID --report FILE`; authenticated assignment check, bounded public summary/evidence, no acceptance |
| `task submit` | `--attempt ID --generation ID --commit C --report FILE` |
| `task verify` | `--candidate ID --checks FILE`; checks must match the admitted brief; independent audit/review remains required |
| `task repair` | `--candidate ID --findings FILE`; preserve C1, enforce live-versus-terminal attempt contract |
| `task refresh`, `task takeover`, `task abort` | `--attempt ID --disposition FILE`; stop/work retention evidence required; refresh adds `--brief FILE` at newly admitted base |
| `task land` | `--candidate ID --review FILE`; context-matching independent review and project integration delegation required |
| `recover` | `--effect ID`; read/compare actual state before bounded reconciliation |
| `cleanup` | `--attempt ID --retention FILE`; validated stop/retention receipts |
| `observe` | `--once` or `--serve --listen 127.0.0.1 --port N`; read-only snapshot/view |

Admission JSON pins canonical/common-Git-dir/ref, publication policy/remote ref, delegated authority, clean-base evidence, exact tool paths/digests/versions, Kata daemon/project IDs, Codex schema/socket identity, additive Insula recipe/rootfs identity, resource budgets and source/output locations. Resolve actual values at task49 admission, not from historic paths. Check manifests contain argv arrays, exact source/runtime/input pins, outputs and per-stage budgets; neither arbitrary worker commands nor producer `passed` flags can become accepted checks.

Each live milestone runs:

```bash
python3 scripts/collab_live.py gate --ticket 49 --admission /ABS/admission.json --output /ABS/evidence/49
python3 tests/collab/audit_live.py --ticket 49 --admission /ABS/admission.json --evidence /ABS/evidence/49 --output /ABS/audit/49.json
```

Substitute ticket50/51/52/54/53 for later gates; `/ABS` paths are explicit execution-owned paths from the actual admission, not installed defaults. The driver records argv/source/runtime/fixture/command logs and exit codes, resource measurements, reopened output hashes and refusal/fault evidence. The independent audit returns exit0 only for exact-context validated evidence; missing capabilities/coverage return nonzero with the gate open. A reviewer independently reads the evidence and implementation before manual bootstrap landing; the runtime under development cannot certify itself.

Offline Git/store probes execute inside an additive live Insula CPU runtime. Real Kata/Codex handoffs use actual admitted daemon transports; preserve their call/readback evidence and record which effects execute on the host. Offline unshared networking cannot reach a host daemon. If an adapter runs inside Insula, explicitly admit the required socket/network mounts and prove them live; do not describe host adapter execution as sandboxed. Each gate must include real Insula execution and the ticket's real external effects. Worker Codex worktree access remains cooperative unless actual launch restrictions prove more.

Reuse landed `experiments/waymo-perception/pipeline/{insula_entry,runtime_identity}.py` and `resources/{stage,sources}.py` through explicit source pins. Task49 adds the additive protocol runtime recipe `experiments/collaboration/runtime/Dockerfile` and its manifest; do not mutate frozen scientific rootfs/images/helpers. The manifest separately bounds CPU tests and actual worker operations; it inherits existing caps/locks and preserves extended scientific scoring budgets. It pins required Git/Python/bwrap/Kata/proxy transport capabilities and permits no undeclared writable mounts. Failure to prove a usable runtime is a blocker, not a mock substitution.

## Task49: durable project admission and shared Kata queue

**Ticket:** [49](../../research/tasks/49-collaboration-project-admission.md). **Files:** create the49 homes in the file map and `test_admission.py`, `test_store.py`, `test_kata.py`; modify `.gitignore` only for `.kata.local.toml`. Do not ignore outstanding work to pass cleanliness.

**Interfaces:** `Store(state: Path)` supplies `locked() -> ContextManager`, `prepare(kind: str, inputs: JsonObject, operation_id: str) -> Effect`, `record(effect: Effect, facts: JsonObject) -> Result`, `read(record_id: str) -> JsonObject`, `reconcile_journal() -> Result`. `admit_project(canonical: Path, state: Path, admission: JsonObject) -> Project`; `admit_task(project: Project, task_id: str, brief: JsonObject) -> TaskBrief`; `GitWorkspace.inspect(root: Path) -> JsonObject`; `Kata.read_issue(uid: str) -> JsonObject`, `Kata.import_tasks(tasks: list[TaskBrief]) -> Result`, `Kata.claim(uid: str, actor: str) -> JsonObject`, `Kata.assign(uid: str, revision: str, assignment: JsonObject) -> JsonObject`. Constructors receive `Project`; `contracts.Refusal` binds one of the spec's stable reasons.

- [ ] Write failing tests `test_admission_rejects_dirty_wrong_ref_unpinned_and_alias`, `test_lock_excludes_second_controller`, `test_durable_boundary_recovery`, `test_fsync_failure_and_earlier_corruption_hold_mutation`, `test_kata_import_idempotency_and_dependency_readback`. Assert no launch/ref update on any refusal; runtime output stays outside canonical source; duplicate imports preserve one UID; torn trailing events remain diagnosed while earlier corruption refuses.
- [ ] Run `python3 -m unittest discover -s tests/collab -p 'test_admission.py' -v`, then corresponding store/Kata suites. Retain expected failures due to missing implementation, not an unrelated fixture failure.
- [ ] Implement records, lock and journal sequence: append+fsync event, atomic immutable record+parent fsync, then projection. Inject faults at each boundary; projection reconstructs only from validated records and actual effects. Precondition failures produce durable refusals.
- [ ] Implement Git admission with `git status --porcelain=v1 -z --untracked-files=all`, exact symbolic ref/HEAD/tree/common-dir and submodule disposition; paths are argv elements. Probe actual local lock/atomic-write behavior and tool versions. Import reviewed definitions49–54/44–48 without historical closure claims; use installed Kata JSON/unique actor/idempotency-key/blocked-by and revision-conditional assignment APIs. Verify project identity before each call; no newer unprobed flags.
- [ ] Create `.kata.toml` through an owned metadata worktree using installed `kata init --project sureal`; reconcile actual returned project identity. Generate stable version1 task/spec/plan/issue-UID map; no mutable owner/status fields. Land this reviewed mapping before managed dispatch; initialization checks it against the daemon. Fixture imports never touch unrelated projects.
- [ ] Run targeted suites and gate49/audit49. Test real fixture Kata export/restore scoped by project ID, durability interruption and dirty/ref/root/lock refusal inside actual Insula. Retain exact clean-mainline/disposition evidence independently.
- [ ] Review and commit only task49 files; manual bootstrap landing closes49 only after its live receipts and actual landed head pass independent review.

## Task50: two owned worker attempts and safe handoff

**Ticket:** [50](../../research/tasks/50-collaboration-worker-attempts.md). **Files:** create `codex.py`, `attempts.py`, `test_attempts.py`; extend `git_workspace.py`, `kata.py`, CLI/live harness and contracts.

**Interfaces:** `Codex(project: Project).read_thread(thread_id: str) -> JsonObject`, `.start_thread(workspace: Path) -> JsonObject`, `.start_turn(thread_id: str, assignment: JsonObject) -> JsonObject`, `.read_public_items(thread_id: str, cursor: str | None) -> JsonObject`, `.stop_owned(attempt: Attempt, disposition: JsonObject) -> JsonObject`; `start_task(project: Project, brief: TaskBrief, operation_id: str) -> Result`; `checkpoint(project: Project, attempt_id: str, generation: str, report: JsonObject) -> Result`; `retire_attempt(project: Project, attempt_id: str, disposition: JsonObject, operation_id: str) -> Result`. Git helper `.create_attempt(brief: TaskBrief, attempt_id: str) -> JsonObject` creates one owned worktree/branch receipt.

- [ ] Write failing tests `test_reservation_claim_cas_thread_ack_order`, `test_third_duplicate_scope_resource_refusals`, `test_lost_creation_or_turn_ack_never_redispatches`, `test_shared_session_pid_and_completed_turn_do_not_release`, `test_takeover_requires_stop_and_rejects_old_generation`. Assert reservation survives unknown outcome; two tasks have disjoint real worktrees; wrong-thread report is rejected even with matching sessionID; a completed turn can retain an active attempt/task.
- [ ] Run `python3 -m unittest discover -s tests/collab -p 'test_attempts.py' -v` red; then implement the exact ordered handshake from the spec with separate prepared/result records for each external effect. Keep locks short; reserve seats during calls and recheck authority on readback.
- [ ] Implement newline JSON-RPC via installed `codex app-server proxy --sock <admitted socket>` using generated admitted schema, request IDs and initialize handshake. Separate read-only methods from launch/stop. `thread/start` returns the fresh primary thread/session before `turn/start`; a public assignment acknowledgement must match brief/generation/attempt and the exact returned thread/turn before RUNNING. Unsupported fields/methods block capability admission; timeout holds UNKNOWN, not retry.
- [ ] Implement scope canonicalization/ancestry and shared-output/resource checks; distinct writable caches/logs/outputs; branch ownership receipts include common-dir identity. Before handoff, retain unsubmitted changes and reconcile thread, native-goal continuation/queued turns and owned tools. A connection/launcher exit is insufficient. Do not kill the shared app-server daemon.
- [ ] Run tests and gate50/audit50 with two actual bounded Codex threads on committed independent fixture briefs, distinct worktrees and observed active overlap. Both workers execute owned live Insula probes. Record exact native grouping, multiple-turn continuation, read-only fork identity fixture, actual Kata contention/CAS rejection, third start, overlapping scope, GPU-lock wait and stopped takeover/new identity. Fault creation/start acknowledgements; independently prove no duplicate launch. Model-free tests alone cannot close50.
- [ ] Review, commit and manually land50 with its independently accepted live evidence; preserve known-safe activity in the other seat during isolated uncertainty.

## Task51: immutable candidates, independent verification and repair

**Ticket:** [51](../../research/tasks/51-collaboration-candidate-verification.md). **Files:** create `candidates.py`, `verification.py`, `test_candidates.py`, `test_verification.py`; extend attempts/CLI/live audit.

**Interfaces:** `submit_candidate(project: Project, attempt_id: str, generation: str, commit: str, report: JsonObject, operation_id: str) -> Result`; `materialize_candidate(project: Project, candidate: Candidate, output: Path) -> Path`; `verify_candidate(project: Project, candidate: Candidate, checks: JsonObject, operation_id: str) -> Result`; `repair_candidate(project: Project, candidate: Candidate, findings: JsonObject, operation_id: str) -> Result`; `validate_review(candidate: Candidate, verification: Verification, review: JsonObject) -> Result`.

- [ ] Write failing tests `test_zero_multiple_merge_dirty_wrong_base_rejected`, `test_ref_retention_survives_amendment`, `test_context_swap_and_mutable_leftovers_refused`, `test_live_waiting_repair_vs_terminal_new_attempt`, `test_changed_candidate_requires_new_audit`. Assert exact commit/tree/sole-parent/B/task/brief/claim/source/runtime/fixture pins, candidate retention ref survives worker branch changes, C1 review cannot accept C2.
- [ ] Run candidate/verification suites red; implement clean submission after explicit source-freeze/continuation disposition. Pin candidate objects under controller-owned `refs/sureal/candidates/<attempt>/<candidate>` with independent readback. Record only declared outputs; ignored incidental source cannot enter verification.
- [ ] Implement separate detached verification materialization from retained C, explicit immutable source/input mounts and owned output. Run admitted checks through actual Insula/resource wrappers; reopen artifacts independently and retain exact logs/exits/digests. Producer flags and narrative claims never substitute for the independent audit/review.
- [ ] Implement repair: retain C1 and findings; additional authorized turn only for a still-live waiting attempt at same brief/base. Terminal attempt must be stopped/retired and receive a fresh claim/thread/worktree. Neither path inherits verification or rewrites a previously accepted identity silently.
- [ ] Run suites and gate51/audit51; mutate worker leftovers while separately verifying retained C, swap identity/evidence, exercise C1→C2 repair and preserve C1 after owned workspace removal. Keep a second actual worker active and independently audit source/output isolation.
- [ ] Review, commit and manually land51 after exact-context live acceptance.

## Task52: serialized exact landing and actual-effect recovery

**Ticket:** [52](../../research/tasks/52-collaboration-landing-recovery.md). **Files:** create `landing.py`, `recovery.py`, `test_landing.py`, `test_recovery.py`; extend CLI/live audit.

**Interfaces:** `land_candidate(project: Project, candidate: Candidate, review: JsonObject, operation_id: str) -> Result`; `recover_effect(project: Project, effect_id: str) -> Result`; `read_publication(project: Project, commit: str) -> JsonObject`. Recovery dispatches by retained effect kind; never accepts a generic replay command.

- [ ] Write failing tests `test_exact_clean_B_to_C_only`, `test_stale_second_candidate_cannot_reuse_review`, `test_crash_before_after_integration_reconciles_B_C_neither`, `test_remote_ack_loss_reads_exact_ref`, `test_shared_unknown_holds_only_affected_mutation`. Assert HEAD/tree/index/worktree exact after fast-forward; publication/cleanup/Kata closure separate; no forced update or reset on unexpected remote/main state.
- [ ] Run landing/recovery suites red. Implement locked preflight owner/context/review/delegation/mainline-B checks, prepared landing receipt and `git -C <canonical> merge --ff-only <exact-C>`; independently read exact HEAD/tree/index/worktree before recording result. A no-op/recovery at C reconciles the earlier operation, not a new acceptance event.
- [ ] Implement conditional non-force publication to the configured remote/ref when required; inspect remote identity/head before and after. Reconcile lost acknowledgement with `git ls-remote` on the actual configured target. Record local landing, publication, retention, cleanup and eventual closure independently; remote divergence retains a blocker.
- [ ] Implement recoverers for every full-spec recovery-matrix row (claim, metadata, workspace, thread/turn, submission/retention, verification, integration, publication, Kata closure and cleanup). Unknown shared identity holds affected project mutations; isolated unknown ownership holds its seat/scope. No uncertain launch retry, C rewrite or automatic takeover.
- [ ] Run tests and gate52/audit52 in real Git fixtures with owned bare remote, interruption at each effect boundary, two same-B candidates and an unrelated active worker. After C lands, refuse stale D even with disjoint paths and old verification; preserve it for explicit fresh-attempt handling. Reopen refs/effects/remote facts independently.
- [ ] Review, commit and manually land52; exact mainline and independently verified evidence remain authoritative over runtime labels.

## Task54: understandable worker state, trace summaries and local overview

**Ticket:** [54](../../research/tasks/54-worker-program-observability.md). **Files:** create observation/health/overview homes and tests from the map; extend read-only `status`/`observe`, native read adapter and live harness. No new launch methods or queue authority in the observer.

**Interfaces:** `collect_snapshot(project: Project, previous: Snapshot | None, now: float) -> Snapshot`; `assess_health(observation: JsonObject, policy: JsonObject, history: list[JsonObject], now: float) -> JsonObject`; `validate_summary(summary: JsonObject, observation: JsonObject) -> JsonObject`; `render_text(snapshot: Snapshot) -> str`, `render_html(snapshot: Snapshot) -> str`; `serve_overview(project: Project, port: int) -> None`. Snapshot schema binds source freshness/cursors/coverage to exact worker/task/claim/thread/turn/item identities. Pure health functions never call runtime/queue mutation.

- [ ] Write failing tests `test_wrong_thread_fork_history_pid_reuse_no_bleed`, `test_pagination_compaction_disconnect_retains_gaps`, `test_phase_threshold_hysteresis_and_valid_wait`, `test_responsive_daemon_is_not_worker_probe`, `test_summary_attribution_escape_and_no_secrets`, `test_observation_has_no_control_effects`. Advance a deterministic clock for thresholds; do not sleep10/30min in unit tests. Replay controlled live timestamps with explicit fixture labeling rather than reporting a fake live elapsed period.
- [ ] Run observation/health/overview suites red. Implement scoped public allowlist: message/tool-action/result and receipt metadata only; exclude reasoning/private fields, credentials and unrelated sessions before persistence/rendering. Deduplicate exact identities; paginate admitted reads without resuming/steering; retain compaction/retention/reconnect gaps and inherited-history provenance. Source failure records last-success timestamp separately from last-poll time.
- [ ] Implement separate operating/native-goal/attempt/task/queue/health views per the companion tables. Pin defaults: development600sec, long-computation1800sec, equivalent failures3, hysteresis2 observations at least5sec apart, supported worker-specific nonmutating probe5sec/3misses. Valid declared quiet jobs retain WAITING and actual budgets. A server-level read is not a worker liveness probe; absent supported signal shows UNKNOWN coverage. HUNG_CONFIRMED requires retained explicit technical diagnosis/reviewer. No health condition kills/restarts/releases work or mutates goals.
- [ ] Implement existing lead/worker narrative checkpoint ingestion at acknowledgement/material change/submission/exit; ≤120word cards link public item/event/artifact anchors and label observed/reported/inferred claims. Collector corroborates evidence; missing usable summaries leave54 open. Do not add per-poll inference or private transcript scraping.
- [ ] Implement one snapshot for CLI JSON/text and localhost static HTML/SVG views: two cards, queue dependencies, spec/task acceptance, state graphs, incidents/history and integration/publication/cleanup separately. Serve GET-only `/snapshot.json` and local UI; no control endpoint. Escape text/URLs and reject active schemes; bind127.0.0.1 only. Poll5sec; mark source stale after15sec. Exclude raw credentials even in error text; drilldown remains scoped/sanitized.
- [ ] Run suites and gate54/audit54 using actual two-worker activity, resource waits, multi-turn/reconnect/identity cases, failed check/corrective finding and confirmed diagnosis fixture. Perform genuine source outage/restart and measure refresh/stale timing; independently compare browser/CLI snapshot and public anchors. Prove observer cannot claim/close/steer/start/interrupt or mutate source. Inject alive-no-progress and owned stalled-operation evidence separately from observer outage; compare state reasons/policies/coverage. Runtime-authorized pause/block/limit fixtures do not bypass native goal rules.
- [ ] Review browser output and source audits, commit and manually land54. Its exercises use admitted49–52 and do not wait for53, avoiding a dependency cycle.

## Task53: retention, safe cleanup and the actual concurrent pilot

**Ticket:** [53](../../research/tasks/53-collaboration-cleanup-closeout.md). **Files:** create `retention.py`, `cleanup.py`, `test_retention.py`, `test_cleanup.py`; extend recovery/live audit/operating documentation. Pilot workers own only `docs/collaboration/operations/` (53.A) and `docs/collaboration/incidents/` (53.B).

**Interfaces:** `retain_attempt(project: Project, attempt: Attempt, output: Path, operation_id: str) -> Result`; `cleanup_attempt(project: Project, attempt: Attempt, retention: JsonObject, operation_id: str) -> Result`; `restore_project_export(project: Project, manifest: JsonObject, output: Path) -> Result`. Restoring retained records/queue into an owned recovery fixture does not automatically authorize live dispatch.

- [ ] Write failing tests `test_cleanup_rejects_canonical_foreign_symlink_live_unknown`, `test_unsubmitted_work_and_candidates_retained_before_removal`, `test_cleanup_other_seat_unchanged`, `test_hdfs_readback_and_scoped_queue_restore_required`. Assert no deletion before exact stopped/retention evidence, retained refs survive worktree removal, and restored owner/status must reconcile actual runtime effects.
- [ ] Run cleanup/retention suites red. Implement immutable work/evidence export, exact project-only Kata export and existing Waystone HDFS archive/readback/live rehydration adaptation from landed resource-retention helpers. Pin source/tool/archive/manifest identity; fresh GET and independent reopened union/hash evidence precede any local scientific payload release. Authentication remains in the existing external refresh mechanism, not journal/spec/token snapshots.
- [ ] Implement validated Git worktree removal, never broad recursive source deletion. Preserve retained candidate refs/bundles and unique unsubmitted work; verify path ownership/stopped effects and another active seat's files/branch/tool identity before/after. Journal interruption leaves cleanup pending, not successful closure. Close Kata only after required ticket-specific landing/publication/retention/cleanup acceptance; audit final mapping independently.
- [ ] Admit pinned landed53.A/53.B brief anchors into Kata as stable logical subtasks, both blocked by54 and **related** to53, not children that cannot start until53 closes. Both at B, disjoint documented scopes. Start two actual fresh primary threads/worktrees and prove active overlap while observing summaries/state/queue.
- [ ] Have53.A produce C and53.B produce D, both sole-parentB, each checked against its guide/runbook verifier in ticket53. Independently verify C and exact-land it first. Preserve/refuse D as STALE_BASE; stop/retain/retire old53.B attempt, create new claim/thread/worktree at C and explicitly carry retained D as input. Produce E sole-parentC; require new exact live checks/review before E lands. Earlier D evidence cannot accept E. Document actual installed commands, not hypothetical examples.
- [ ] Run gate53/audit53, retaining both overlaps, C/D/E lineage, refresh/new identity, per-seat cleanup while other work is active, restart/recovery/publication distinctions, GPU-lock/capacity/scope refusals, local overview snapshots and HDFS recovery/queue restore. Independently audit every49–54 closure and actual source/runtime identity. Final canonical source/ref/index/working state and configured remote must match accepted evidence.
- [ ] Review and manually land protocol implementation if not already landed; commit only owned accepted evidence/manifests/docs. Record closure with precise remaining limits. Only then admit models/training44–48; protocol success establishes collaboration reliability, not model quality.

## Coverage and handoff

| Normative requirement | Owning task |
| --- | --- |
| Clean base, committed spec/plan authority, durable record/lock/corruption safety, one Kata project | 49 |
| Scoped dispatch, two seats, native identities/acknowledgements, stop/takeover/ownership | 50 |
| Immutable single candidate, isolated verification, independent checkers, repair evidence | 51 |
| Exact integration, stale refusal, remote outcomes, all interrupted-effect recovery | 52 |
| Human overview, summaries/public evidence, state/health, freshness and no-control views | 54 |
| Retention, HDFS/queue restoration, safe cleanup, concurrent C/D/E pilot and scientific handoff | 53 |

Before implementation, review this plan against the approved specs. Each stage ends with independent review, live evidence and an owned integration checkpoint; no test result or completed model turn closes the entire program. Report blockers with retained evidence and continue only independent permitted work. Preserve the user's inline execution choice; do not silently replace it with a different agent workflow.
