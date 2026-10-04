# Claude third-review provenance

Claude reviewed exact commit `f32a4965e682e972b61dacfb0ef60d40f4774ca4`; line references below refer to that revision. [Provenance](2026-10-03-sureal-collaboration-claude-rereview-3.json) pins33 source files and raw request/response. Trailing whitespace is normalized in this rendered copy; raw artifacts remain exact. The reviewer confirms the original findings are resolved, with bounded residual corrections; no runtime acceptance or execution approval is claimed.

---

# Third review: Sureal two-worker collaboration plan at f32a496

This is a documentation review only: nothing was executed, and `kernel_scope.py` and `process_lifecycle.py` were not supplied.

Abbreviations: PLAN = the implementation plan, COV = `coverage.json`, CHK-A/B = the pilot manifests, T-n = ticket files.

## 1. Verdict

**CHANGES REQUIRED (narrow).** P0 = 0, P1 = 2, P2 = 5, P3 = 6.

There are no remaining cycles and no design dead ends. Both P1s are bounded text/JSON edits, and a diff check of those edits should suffice rather than a fourth full review. No final 53/54 verifier is waived.

## 2. Prior findings disposition

**Resolved in current source:**
- **S1–S22, D1–D6:** all resolved.
- **N2:** an independently authored A_N is admitted before X_N gates and invoked from an absolute snapshot (PLAN:115).
- **N4:** `task continue` has a command, interface, test and coverage case (PLAN:76, 193, 195; COV:199–212).
- **N5, N6, N8:** lead-executed host receipts with compare-only checker; enforced diff scope and unchanged blob IDs; exit 2 versus exit 3 (PLAN:173, 210, 64; CHK-B:86–89).
- **N9, N11, N13, N14:** collaboration-owned heartbeat wrapper; ack/turn-result stream and supervision recovery; probe creator and authority; read-only lock wiring (PLAN:161, 64, 151, 143, 165).
- **N12:** I counted 44 cases (6/9/4/5/6/7/7), each with case-specific artifacts.
- **N16, N18–N22:** all resolved (PLAN:141, 244, 167, 137, 147, 74; `worker-briefs.json`).

**Resolved with a residual:**

| ID | Status | Residual |
| --- | --- | --- |
| N1 | Mechanism resolved, content incomplete | R1, R6 |
| N3 | Blocker outcome explicit and valid (PLAN:153) | R3: the preflight has no subject or oracle |
| N7 | Fresh C-context fixtures required (PLAN:262) | R4 |
| N10 | GateAdmission/ProjectAdmission split and gate argv are sound | R9 |
| N15 | F's owner, path and mechanism defined (PLAN:264) | R5 |
| N17 | Close syntax consistent (PLAN:224, Q:121–125) | `kata init --workspace` is not confirmed by the ledger; a help check is needed |

## 3. Remaining findings

### Blockers (P1)

**R1 — Post-landing and closure phases are empty for most tickets, so those audits pass vacuously.** COV; PLAN:97, 109, 115.
- **Failure:** PLAN:97 says closure requires all phases, and PLAN:109 requires an independent landing readback for every stage. COV has post-landing cases only for 53.0 and 53, and closure cases only for 49 and 53. For 50, 51, 52 and 54 (and 49's X/M landing, and 53.0's close), the audit has no oracle. The manual fast-forward and manual `kata close` are the least protected bootstrap effects, and their closure unblocks the next ticket.
- **Fix:** add to every ticket a post-landing case (ref/HEAD/tree/index/worktree equal exact X; M as well for 49) and a closure case (Kata close event/readback bound to accepted evidence). State that a phase with zero cases refuses.

**R2 — `task refresh` has no owning task, interface or test.** PLAN:81, 193, 206, 219, 232.
- **Failure:** the command is in the table and is required by gate 54 (PLAN:251), CHK-B:113–133 and the pilot (PLAN:262). No task 50–53.0 lists a function or test for it. Task 54 forbids new launch methods (PLAN:242), so the gap would surface at gate 54 and force an unplanned stage.
- **Fix:** assign it to 50 or 52 with a signature such as `refresh_task(..., runtime: Codex)`, a named test (old attempt retained and stopped, new claim/thread/worktree, no inherited verification) and a gate case. Also state that `task takeover` only retires the attempt and the replacement is launched by `task start`.

### Clarifications (P2)

**R3 — The stop-capability preflight has no fixture creator, authority or oracle.** PLAN:153; `runtime-probes.json`; COV 50.
- **Failure:** demonstrating complete stop evidence before any managed claim needs a live turn and tool on a non-managed thread. `runtime-probes.json` defines only `fork` and `native-goal-states`. No COV case requires the preflight receipts to precede the first claim effect.
- **Fix:** add a `stop-capability` probe (non-managed, per-probe authority) and a gate-50 case with that ordering oracle. Run it before implementing 50, so a design blocker surfaces before the code is written.

**R4 — The `preflight` phase is outside the audit contract.** PLAN:260, 262 against PLAN:97; COV:612.
- **Failure:** the driver takes `--phase preflight`, but the auditor phases are gate, post-landing and closure. No case covers the pre-pilot receipts at B or the fresh ones at C, and no command is given for the C run.
- **Fix:** add the phase or two gate cases (`prepilot-fixtures-at-B`, `refresh-fixtures-at-C`) and the `--candidate C` invocation.

**R5 — Metadata candidates M and F have no pre-landing oracle or gate binding.** PLAN:126, 263–264; COV:599–608.
- **Failure:** the evidence list for `final-F-landing` includes `F-gate-audit.json`, but no gate case defines what that audit checks. It is unstated which `--candidate` gate 53 takes. M has the same gap.
- **Fix:** add gate cases for diff scope, sole parent and referenced-receipt digests. State that gate 53's pilot cases bind E-state evidence and the F case binds `--candidate F`.

**R6 — The 49 closure case mixes fixture-only clauses with real-project readbacks.** COV:57–69.
- **Failure:** "old running brief stays pinned" cannot occur on the real project at 49 closure, because no attempt exists until 50. Meanwhile fixture import idempotency and status-no-control have no gate oracle before `task import` writes to the real project.
- **Fix:** split into a gate-phase fixture case and a closure-phase real bootstrap/M case.

**R7 — The kernel-scope prerequisite of `run_stage` is unnamed.** `scoped_stage.py:73–76`; `stage_accounting.py:83–94`; PLAN:101, 137, 151.
- **Failure:** admission needs an exclusive cgroup scope whose caller is the sole member, named `sureal-sustained-*.scope`, with an exact memory cap and zero swap. A Codex tool process is unlikely to satisfy that without creating a scope, and two workers need distinct ones.
- **Fix:** name scope creation and uniqueness in the runtime manifest and probe it in 49 (lead) and 50 (each worker). The existing "blocks before managed launch" outcome then applies.

### Minor (P3)

- **R8 — Exit codes.** PLAN:64 leaves exit 1 undefined, and argparse usage errors exit 2 with no envelope, colliding with "refused". Define both.
- **R9 — Paths and admission kind.** PLAN:135 and 173 use relative `scripts/collab_live.py`, and `fixture --pilot --admission` does not say which admission kind. Use absolute pinned paths and name the kind.
- **R10 — Stage scripts must return normally.** `execute_worker.py:23–36` writes the receipt only on normal return, and `run_stage` raises on nonzero exit. Scripts need a harness that exits 0 and records inner exits (no `sys.exit`; `unittest` with `exit=False`).
- **R11 — Missing refusal reason.** CHK-B `stale-land` lacks `expected_reason` (STALE_BASE).
- **R12 — Missing file homes.** `heartbeat_worker.py` and `docs/collaboration/evidence/53/` are absent from the file map.
- **R13 — Stale wording.**
  - PLAN:199 says "below" for a contract that is above.
  - PLAN:237 says "implement … manifests" where it means the scripts.
  - Ledger S19 still says "busy/idle probe".
  - README:56 omits 53.0 from 53's dependencies.

## 4. Live gates still required

- Current worker closeout and independently proven pristine mainline.
- Plan admission by the user.
- Recorded per-probe native authority (future, not existing approval).
- **49:** runtime build and rootfs lock; real state-filesystem lock/fsync; isolated Kata daemon, import and restore; kernel scope.
- **50:** stop preflight; disconnect and approval behaviour; common `.git` and nested Insula grants; two overlapping real workers.
- **51–52:** raw materialization fidelity; exact fast-forward; remote-ack recovery.
- **53.0:** HDFS no-overwrite preflight, LS and fresh GET; live rehydration; per-seat cleanup.
- **54:** heartbeat and health fixtures; refresh and stale timing; no-control proof.
- **53:** the actual C/D/E pilot, F, and closure audits.

This review approves nothing at runtime and does not permit bypassing any of these gates.
