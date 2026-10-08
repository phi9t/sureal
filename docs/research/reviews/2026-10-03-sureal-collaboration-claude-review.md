# Claude review provenance

The user requested this review of the [implementation plan](../../superpowers/plans/2026-10-03-sureal-two-worker-collaboration.md) against the approved full spec and companions. Claude reviewed the exact commit `4469127623350ad5a644ae8c4dd0f8f21ab7c990`; all file/line references below refer to that revision.

The request contained 15 committed source documents/helpers with one-based line numbers. Claude Code2.1.288 ran with tools disabled, safe mode and no session persistence. It returned success and the verdict **changes required**. Its severity counts are review findings, not independently proved implementation failures. The ordering/commit-binding concern and the existing runtime helper constraints were corroborated by local source inspection; the remaining findings await triage. No implementation, live acceptance or user-plan approval is claimed.

[Machine-readable provenance](2026-10-03-sureal-collaboration-claude-review.json) records exact source/request/response hashes and the reported model/session identity. The following report is preserved verbatim; it does not supersede accepted task/spec authority.

---

# Plan review: Sureal two-worker collaboration (commit 4469127)

Path abbreviations used below:
- **PLAN** = `docs/superpowers/plans/2026-10-03-sureal-two-worker-collaboration.md`
- **SPEC** = `docs/superpowers/specs/2026-10-03-sureal-serial-collaboration-design.md`
- **RT** = `docs/superpowers/specs/2026-10-03-codex-runtime-domain-design.md`
- **ST** = `docs/superpowers/specs/2026-10-03-worker-session-state-design.md`
- **Q** = `docs/research/task-queue.md`
- **T49–T54** = `docs/research/tasks/<n>-*.md`
- **IE** = `experiments/waymo-perception/pipeline/insula_entry.py`
- **STG** = `experiments/waymo-perception/resources/stage.py`

This is a documentation review only: nothing was executed, and I make no claim about the current state of mainline.

## 1. Verdict

**Changes required.** Counts: P0 = 0, P1 = 12, P2 = 12, P3 = 4.

The plan tracks the spec's invariants closely and mostly restates them correctly. The blockers sit where it stops restating and has to commit to a concrete operation or oracle:

- **Gate-to-commit binding:** the step ordering verifies an uncommitted tree, and the task-53 sequencing forces a rewrite of the verified commit.
- **Insula reuse:** the claim of reusing the helpers without mutating them is contradicted by the supplied helper code.
- **Bootstrap cycles:** there are two, one around init/import/map and one around Kata closure.
- **Missing oracles:** several named tests have no credible oracle (wrong-thread rejection, stop evidence, materialization fidelity, health classification, audit coverage).

None is a design dead end. Each has a bounded fix, but they should be settled in the plan text before implementation rather than discovered at gate 49.

## 2. Spec compliance

### P1

**S1 — Gates run before the commit they are supposed to certify.** PLAN:106–107, 119–120, 132–133, 145–146, 159–160, 173–174.
- **Mismatch:** every task orders "Run … gateN/auditN" and then "Review and commit". SPEC:81 requires verification to "bind exact C/tree/B/…", and SPEC:225 requires "exact landed evidence".
- **Failure:** evidence is taken from a dirty working tree. The later commit, or a rebase or squash in the unspecified "existing manual workflow", is a post-verification write that no receipt can detect.
- **Fix:** reorder each task to commit X, run the gate on a clean detached materialization of X (driver records commit and tree), have the audit refuse a dirty or mismatched source, then land X by fast-forward only. Any change to X means a new gate.

**S2 — The pilot moves mainline out from under the unlanded task-53 implementation.** PLAN:173–174 ("manually land protocol implementation if not already landed"); T53:44.
- **Mismatch:** if retention/cleanup code is still an isolated candidate X (parent B) while the pilot lands C and then E, X can no longer fast-forward.
- **Failure:** landing X needs a rebase or merge, so the landed head differs from the gate-53 evidence. Separately, 53.A must document and run CLI commands (T53:30–32) that do not exist in its worktree at B.
- **Fix:** split task 53. Land the retention/cleanup implementation first, under its own fixture gate, so it becomes pilot base B. Run the pilot as the final live gate, with only evidence and manifests committed afterwards.

**S3 — "Reuse without mutation" of the Insula helpers is contradicted by the helper code.** PLAN:93; IE:38, IE:45, IE:16, IE:31; STG:8–11, STG:50–53, STG:102. Confirmed contradictions:
- IE:45 hashes `here/'insula/Dockerfile'` and `requirements-tracer.lock` under waymo-perception. A rootfs built from `experiments/collaboration/runtime/Dockerfile` cannot pass that check with an honest lock.
- IE:38 hard-wires `/experiment` and `PYTHONPATH` to waymo-perception. `scripts/_collab` and `tests/collab` are only reachable through the single `/source` mount.
- IE:16 always uses `--unshare-all` (the `--offline` flag at IE:31 is parsed and never used), with one read-only source and one writable `/outputs`. There is no socket mount for Kata or Codex.
- STG:50–53 admits exactly one `--bind … /outputs`, and STG:102 requires the stream to be `live.log`.
- STG:8–11 imports `resources.command`, `scoped_stage` and `stage_accounting`, which the plan's pin list ("`resources/{stage,sources}.py`") omits.
- **Failure:** gate 49 either cannot start or silently requires editing frozen helpers.
- **Fix:** have the plan name a new additive entry (for example `experiments/collaboration/runtime/entry.py`) with its own lock schema, reusing only `launch_plan` and `verify_rootfs` by import. State the rootfs build and lock procedure and who verifies it. Pin the full import closure. Say how the hyphenated `waymo-perception` directory gets onto `sys.path`.
- **Durability note:** the durability/lock probe (PLAN:104) must run on the real state filesystem, not the `/tmp` tmpfs inside bwrap.

**S4 — The 53.A/53.B executable verifiers are a circular reference.** PLAN:172 ("checked against its guide/runbook verifier in ticket53"); T53:44 ("The accepted implementation plan supplies exact executable commands, runtime source/candidate pins and fixture preparation").
- **Mismatch:** neither document contains the commands, so the pilot's `--checks FILE` has no admitted content.
- **Fix:** add the two check manifests to the plan: argv for link validation, replay of documented commands against the fixture with expected exits and refusals, and a credential/transcript scan, plus fixture preparation.

**S5 — Gate 54 omits verifiers that ticket 54 requires.** PLAN:159–160; T54:29 ("submission, stale-base refresh and per-seat cleanup display correctly") against T54:7.
- **Mismatch:** per-seat cleanup does not exist until task 53, and gate 54 as listed also omits submission and stale refresh.
- **Failure:** 54 closes, unblocking 53.A/B, with a required verifier unexercised; or it can never close.
- **Fix:** exercise submission and stale refresh in gate 54 using the 49–52 capabilities. For the cleanup display, the ticket text needs an explicit user-approved reconciliation, for example auditing it in gate 53 as retained task-54 evidence. I am not proposing to weaken it; the plan must surface the conflict per SPEC:25.

**S6 — Bootstrap cycles: init/import/map, and Kata closure.** PLAN:64, 68, 105, 170–171; command table PLAN:66–78.
- **Cycle (a):** `init` "checks it [the landed map] against the daemon" (PLAN:105). The map needs issue UIDs from `task import`, and `task import` needs `--project-state` from `init`. In addition, `kata init` runs before any Store exists, so it has no effect receipt, and landing the map moves mainline off the Project's recorded transition base.
- **Cycle (b):** 53.A/B are "blocked by54" (PLAN:171), but Kata close is implemented in task 53 (PLAN:170) and there is no close command. Meanwhile task 52 must implement a "Kata closure" recoverer (PLAN:144) for an effect that does not yet exist.
- **Fix:** specify the order explicitly:
  1. Manual `kata init`, with retained readback.
  2. `init` without a map.
  3. `task import`.
  4. Reviewed map-only commit.
  5. A dispatch precheck that validates the map at the current B.
  Also state whether the real import happens before or after 49's code lands. Give closure an owner and command in task 52, and define the manual evidence-backed close for 49–52/54 (Q:121–125).

**S7 — Stop and goal-continuation evidence has no concrete operations or oracle.** PLAN:113, 118; RT:47; SPEC:152.
- **Mismatch:** `Codex` exposes no goal read, no queued-input read and no process-handle enumeration. `stop_owned` mixes observation with mutation, and the authority for a goal pause or clear is unstated. The plan never says whether v1 workers get a native goal at all (ST:9 "NO NATIVE GOAL").
- **Failure:** `turn/interrupt` succeeds, an active goal schedules a continuation turn, and takeover proceeds on "stopped" evidence while the old thread still writes.
- **Fix:** define the stop predicate:
  - no `inProgress` turn;
  - goal absent or non-active, read from the daemon;
  - no queued input;
  - no process with cwd or open fds under the owned worktree, identified by (pid, start time, boot ID);
  - all of the above observed twice.
  If any of these is unreadable, the result is UNKNOWN and takeover is refused. Add separate read methods.

**S8 — "Wrong-thread report is rejected" has no oracle under the stated interface.** PLAN:70–71, 115; Q:36; SPEC:148.
- **Mismatch:** `task checkpoint` and `task submit` take only `--attempt --generation`. A CLI invocation carries no thread identity, and "authenticated" is undefined within a cooperative boundary.
- **Failure:** thread T2 in the same session reports with T1's IDs and is accepted, and the test passes only against a mock.
- **Fix:** the controller corroborates each report by reading the exact bound thread's public items for the matching invocation or report digest in the current turn. Otherwise the report is labelled worker-reported and uncorroborated and rejected for state transitions. Rename "authenticated" accordingly.

**S9 — Immutable materialization has no mechanism or fidelity check.** PLAN:126, 130; SPEC:166; T51:30.
- **Mismatch:** `materialize_candidate(...) -> Path` returns no receipt, and the method is unstated.
  - A linked worktree registers shared metadata, and its `.git` pointer breaks inside the sandbox.
  - `git archive` applies `export-ignore` and `export-subst`.
  - A plain checkout applies smudge and EOL filters.
  - Read-only bind protects only inside bwrap.
- **Failure:** the verified bytes differ from C's tree, or the host copy is mutated mid-run.
- **Fix:** specify the method. Recompute the tree ID of the materialized directory independently before and after the checks and require equality with C's tree. Refuse gitlinks, or declare how they are handled. Return a receipt.

**S10 — The health detector lacks deterministic classifiers.** PLAN:156; ST:58, 78, 70; T54:33.
- **Mismatch:** thresholds are pinned, but "meaningful progress", "equivalent failure" (ST:78 "reviewed definition of equivalent failures") and the "supported worker-specific nonmutating probe" are undefined, and per-poll inference is forbidden.
- **Failure:** the observer's own reads, or checkpoint chatter, reset progress (self-attribution). Alternatively no probe exists, and the "owned stalled operation" fixture can only ever yield UNKNOWN, which makes that verifier vacuous.
- **Fix:** define:
  - progress as attempt-attributed events only (HEAD or diff digest change, declared artifact change, checkpoint flagged material), excluding controller, observer and lead items;
  - equivalence as (argv digest, exit, normalized-output digest, no intervening source change);
  - the owned-operation signal, for example owned process CPU-time or artifact delta.

**S11 — The audit's independence and coverage oracle are unspecified.** PLAN:89; T49:23; T52:25.
- **Mismatch:** `audit_live.py` ships in the same candidate and validates whatever the driver emitted. No required-coverage list exists per ticket, and nothing proves Insula actually ran.
- **Fix:** commit a per-ticket coverage manifest derived from the ticket verifiers before implementation. The audit must not import `scripts/_collab`, and must reopen raw Git, Kata and log artifacts and recompute digests. It must also validate the rootfs lock and bwrap argv (the equivalent of STG `validate_proof`). Name the independent reviewer role.

### P2

**S12 — Thread binding into Kata metadata, and per-step effect identity.** PLAN:99, 116; RT:39; SPEC:144, 146.
- **Mismatch:** the metadata must include `thread_id`, which is known only after step 4, and the plan does not list that second revision-conditional update as its own effect. One `--operation-id` also spans five external effects.
- **Fix:** key each effect by (operation ID, step) and refuse a repeated ID whose input digest differs.

**S13 — Git determinism and shared state.** PLAN:104, 142; T54:37.
- **Mismatch:** hooks, `core.hooksPath` and the remote URL are shared and worker-mutable, and a post-merge hook could dirty canonical. `git status` takes optional index locks, so the observer is not strictly non-mutating and can race a landing. Ignored files are invisible to the stated status command.
- **Fix:** pin a config and hook digest at admission. Run controller Git with hooks disabled and a fixed environment. Use `--no-optional-locks` for reads. Record `--ignored` output at submission.

**S14 — HDFS retention.** PLAN:169.
- **Mismatch:** the helper is unnamed (STG has no HDFS functions; STG:65–67 only refers to a lifecycle elsewhere), it executes on the host rather than in Insula, and partial-upload or lost-acknowledgement handling is absent.
- **Fix:** name and pin the helper. Use immutable per-export paths with no overwrite. Reconcile by listing plus a fresh GET and hash. Record the host-execution boundary.

**S15 — Revision handling.** PLAN:3, 105; SPEC:137; Q:19.
- **Mismatch:** there is no operation or test for an admitted task revision updating the same issue while a running attempt keeps its old brief. Checkbox tracking inside a pinned mainline plan either dirties canonical or moves B.
- **Fix:** add a test, and track progress outside pinned source.

**S16 — Unknown-thread deadlock.** PLAN:117.
- **Mismatch:** after a lost `thread/start` acknowledgement, `task abort` needs stop evidence for a thread it cannot name.
- **Fix:** define the disposition evidence, such as a probe listing threads by the unique worktree cwd, or an explicit human disposition record.

**S17 — The task-49 status deliverable is unowned.** T49:17, 19; PLAN:99–107. No interface, test or module for `status` exists until task 54.

**S18 — Tool results in the public allowlist.** PLAN:155. Result bodies can contain secrets. Persist metadata and digest by default, and keep bodies only in the scoped drilldown.

**S19 — "GPU-lock wait" in gate 50.** PLAN:119. The plan does not say whether this is the real experiment lock, which would interfere with scientific jobs, or a fixture lock, which proves nothing about integration.

### P3

- **S20 — Push refspec.** PLAN:143: push the exact `C:<ref>` refspec, not the branch name.
- **S21 — Digest stability.** PLAN:60: forbid floats in digested records.
- **S22 — Evidence output paths.** PLAN:85–86: fixed `/ABS/evidence/49` paths cannot keep failed attempts; use per-run directories (compare STG:94).

## 3. Design and implementation quality

**D1 (P1) — No process owns the worker's connection.** PLAN:9 ("No … daemon"), 117.
- **Problem:** the launching CLI exits after acknowledgement. It is unspecified whether a turn survives client disconnect, and who answers server-to-client approval requests.
- **Failure:** the worker blocks forever on an approval and is diagnosed as hung.
- **Fix:** specify the approval and sandbox policy at `thread/start`, and probe survival across disconnect before 50's design is fixed.

**D2 (P2) — Worker-facing invocation is undefined.** PLAN:64, 70–71.
- **Problem:** the plan does not say which `scripts/collab.py` a worker runs (its worktree copy at B, or pinned controller source). It also does not address that the worker's sandbox must write to `../.sureal-collab` and to the common `.git` in order to commit at all.
- **Fix:** state who invokes each command and from which source. Record the write grants honestly as a cooperative boundary.

**D3 (P2) — Interfaces are incomplete for the operations they must serve.** PLAN:99, 113, 144.
- **Kata:** no release, transfer, close, comment or export.
- **Codex:** no goal, list, interrupt or fork-fixture methods.
- **Recoverers:** the closure and cleanup recoverers are scheduled in task 52, before their effects exist.
- **Fix:** enumerate the methods per task, and move those recoverers to the task that creates the effect.

**D4 (P2) — Execution-method wording.** PLAN:3, 39, 187.
- **Problem:** the plan says "REQUIRED SUB-SKILL: subagent-driven…" and also "Preserve the previously selected inline execution". It calls the inline workflow "already-authorized" while the plan is unapproved. An inline implementer who also reviews undercuts S11.
- **Fix:** state one method, drop "already-authorized", and name a separate reviewer.

**D5 (P2) — Snapshot collection model.** PLAN:152, 158.
- **Problem:** a serial collector across Kata, Codex and three Git checkouts with no per-source timeout lets one slow source make all sources stale.
- **Fix:** give each source its own timeout and timestamp, and have the server collect on its own cadence rather than per request.

**D6 (P3) — Proportionality.** The module count is acceptable. Keep the SVG state graphs minimal, rendered from the same text graph, and avoid splitting further.

## 4. Strong parts worth preserving

- **Receipts and recovery:** prepared/result receipts per external effect, UNKNOWN holding the seat, and no blind retry (PLAN:64, 116–117).
- **Retention:** controller-owned refs with independent readback (PLAN:129).
- **Landing:** fast-forward only, with exact post-state readback and separate publication, cleanup and closure facts (PLAN:142–143).
- **Honesty about trust boundaries:** the plan says the boundary is cooperative and that host adapters are not sandboxed (PLAN:91).
- **Scope discipline:** argv-only command APIs, hash-chained journal, deterministic-clock health tests, a GET-only localhost observer, and task 54 ordered before 53 to avoid a cycle.

## 5. Required pre-implementation corrections and live unknowns

**Corrections before approval:** S1–S11 and D1, plus D4's wording. S5 needs the user's explicit reconciliation of ticket 54.

**Live capability unknowns.** Each needs a probe and must block rather than be mocked.

Kata v0.14.3:
- project-scoped **restore/import** (only export is listed at SPEC:231 and Q:54);
- an idempotency-key flag;
- `kata init --project`;
- claim refusal without `--force`;
- a release/transfer command;
- a second isolated fixture daemon (T50:28).

Codex daemon 0.160.0:
- turn survival after client disconnect;
- approval behaviour with no client attached;
- goal and queued-input reads over the proxy;
- whether `thread/read` loads or touches thread state;
- listing threads by cwd;
- whether tool-process handles are exposed.

Worker sandbox:
- whether a worker can write the shared `.git` (needed for any commit in a linked worktree);
- whether it can run nested bwrap for its "owned live Insula probes".

Runtime and infrastructure:
- Unix-socket bind mounts under `--unshare-all`;
- lock and fsync semantics on the actual state filesystem;
- the HDFS helper's identity and where it executes;
- the identity and protocol of the existing exclusive experiment lock.

**Final summary:** the plan is faithful in intent and well scoped, but it is not ready. Reordering gate and commit, landing the task-53 implementation before the pilot, defining an additive Insula entry, breaking the two bootstrap cycles, and writing the missing oracles and pilot check manifests would make it approvable. The probes above then decide what gate 50 and gate 54 can actually prove.
