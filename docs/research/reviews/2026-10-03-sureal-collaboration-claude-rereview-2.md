# Claude second-review provenance

Claude reviewed exact commit `d5ead21fb46ddef78bed8d8ac0f8b122ca1f0c01`; all line references below refer to that revision. The response succeeded, with tools disabled. [Provenance](2026-10-03-sureal-collaboration-claude-rereview-2.json) pins the22 source files and raw request/response. The report is preserved verbatim; no live runtime or implementation approval is claimed.

---

# Re-review: Sureal two-worker collaboration plan at d5ead21

Documentation review only. Nothing was executed, the research README linked at SPEC:22 was not in the bundle, and `execute_worker.py`, `sources.py`, `scoped_stage.py` and `stage_accounting.py` were not supplied, so claims about them are flagged as unverified.

Abbreviations: PLAN, SPEC, RT, ST, Q, T49–T54, T53.0 as in the first review; COV = `docs/collaboration/coverage.json`; CHK-A / CHK-B = `docs/collaboration/checks/53.A.json` / `53.B.json`.

## 1. Verdict

**Changes required.** Remaining findings: P0 = 0, P1 = 6, P2 = 10, P3 = 5.

The fixes resolve the original structural blockers: commit-before-gate, the 53.0 split, the additive entry, the TaskDefinition/TaskBrief split and effect keys. The remaining P1s are mostly new and sit in the artifacts the fixes introduced, namely the coverage manifest, the pilot manifests, the auditor's home and no-goal mode. Each fix is a bounded text or JSON edit.

## 2. Original finding dispositions

| ID | Status | Evidence |
| --- | --- | --- |
| S1 | Resolved in contract; residual N10 | PLAN:107 and the "Commit clean … X first" step in every task (183, 195, 208, 221, 234, 247). The gate argv (PLAN:91–92) still does not name X. |
| S2 | Resolved | 53.0 lands before 54 and before pilot B (PLAN:41, 224–234; T53.0:31; T53:44). Final 53 adds only docs/evidence (PLAN:252, 260). |
| S3 | Resolved; residuals N16, N20 | Additive entry, collaboration lock, full `resources/` closure, single `/outputs` bind and `live.log` (PLAN:99, 133–139) match `stage.py:50–56, 102` and `command.py:23–26`. |
| S4 | **Partial** | Manifests exist, and success receipts do precede document verification (claim/submit from the outer pilot, verify/land/close from prepilot). They are not executable as written: N5, N6, N7, N8. |
| S5 | Resolved | T54:7, PLAN:247–248, SPEC:223, Q:142 are consistent; no verifier was waived. |
| S6 | Resolved for the original cycles; new cycle N1 | PLAN:119–129 gives the manual init → map-less `init` → import → M → dispatch check order; `task close` is in 52. |
| S7 | **Partial** | Read methods and the twice-observed predicate exist (PLAN:149, 189). The response to unexposed process/queue coverage (N3) and a continuation operation (N4) are missing. |
| S8 | Resolved | Exact thread/turn/item arguments and public-digest corroboration (PLAN:75–76, 143); residual N21. |
| S9 | Resolved | Raw `ls-tree`/`cat-file` materialization, manifest-only gitlinks, independent `mktree` rebuild before and after, receipt type (PLAN:109–111, 202). |
| S10 | **Partial** | The classifier is deterministic but misclassifies ordinary development, and the heartbeat assumption is unverified (N9). |
| S11 | **Partial** | The coverage manifest and no-import rule exist, but the auditor is still in the producer's candidate (N2) and the manifest has gaps (N1, N12). |
| S12, S13, S15–S18, S20, S22 | Resolved | PLAN:69, 115, 127, 143, 151, 159, 175, 219, 139. |
| S14 | Resolved; residual N19 | Host adapter, pinned tool closure, immutable digest path, LS plus fresh GET (PLAN:163). |
| S19 | Partial | Specified, but now touches the real scientific lock (N14). |
| S21 | Resolved; residual N18 | PLAN:65. |
| D1 | Resolved; residual N11 | Foreground supervisor, `approvalPolicy=never`, UNKNOWN on loss (PLAN:147). |
| D2, D4, D5, D6 | Resolved | PLAN:45, 3, 159/246, 159. |
| D3 | **Partial** | Kata/Codex methods were added and recoverers moved, but there is no continuation operation (N4) and no fork/goal fixture method or authority (N13). |

## 3. Remaining and new findings

### Spec compliance

**P1**

**N1 — Coverage cases require events that happen after the gate they decide.** COV:47–48, 285–286, 399–400; PLAN:95, 113, 119, 183, 259–260.
- **Failure:** PLAN:113 refuses the gate if any listed case is missing, but three cases depend on later steps:
  - Case 49 `queue-bootstrap-revision-status` needs "actual manual bootstrap/import/map M/closure readbacks". Bootstrap happens only after X49 is gated and landed, and closure comes last.
  - Case 53.0 `landed-foundation` needs X landed.
  - Case 53 `final-independent-closeout` needs F landed, yet gate 53 runs before F exists.
- **Fix:** add a `phase` field to each case (`gate`, `post-landing`, `closure`) and a `--phase` argument on `audit_live.py`, matching the driver's 53 preflight. State that landing needs only gate-phase cases and closure needs all phases.

**N2 — The "independent" auditor is authored and versioned inside the candidate it audits.** PLAN:59, 92, 113.
- **Failure:** the file map lists `tests/collab/audit_live.py` as created in 49 and "extended each stage", so the stage-N oracles ship in X_N, written by the inline implementer. PLAN:113 requires its digest to be admitted "before testing X", which is impossible for bytes that first appear in X. The shown command also runs it by relative path from the working tree.
- **Fix:** specify a separate auditor commit A_N per stage:
  - A_N touches only `tests/collab/audit_live.py` and its support, derived from COV and the ticket verifiers.
  - It is reviewed by the non-implementing reviewer and landed (or snapshot-admitted) before X_N is gated.
  - X_N is refused if it modifies auditor paths, and the audit is invoked from the admitted snapshot's absolute path.

**N3 — No defined outcome if the runtime does not expose owned-process or queue coverage.** PLAN:149; T50:15; resolution ledger:40.
- **Failure:** "any missing API, process/queue coverage … refuses release/takeover", and a process scan is "supporting evidence, not a substitute". The ledger itself says the schema does not prove process-handle coverage. If that probe fails, every retirement, takeover, cleanup and the pilot's 53.B refresh is refused permanently. That blocks gates 50, 53.0, 54 and 53 with no path forward.
- **Fix:** define the minimum sufficient evidence for that case now. One option:
  - terminal turn status;
  - every tool item in the attempt's turn range terminal;
  - no queued input;
  - two scans 5 s apart showing no process whose incarnation, cwd or fds fall in the owned worktree/output scope.
  
  Record it as a limited-coverage stop requiring lead sign-off. Alternatively, state that failure of this probe is a user-escalated design blocker before 50 starts.

**N4 — No-goal mode has no continuation operation.** PLAN:71–84, 145, 189, 195.
- **Failure:** managed workers get bounded turns and "do not pursue another turn without an explicit admitted lead continuation". The command table offers only `task start` and `task repair`, and repair requires a candidate. A turn that ends before submission is the normal case, and it leaves the attempt idle with no way to resume. Gate 50's "multiple-turn continuation" has no interface.
- **Fix:** add `task continue --attempt --generation --thread --assignment FILE` with:
  - its own `launch-turn`/`acknowledge` effect keys;
  - the same foreground supervision;
  - a no-in-flight-turn and no-goal precheck;
  - a test that it refuses an old generation.

**N5 — "host-fixture-execute" scenarios cannot run where the manifest runs.** CHK-A:68; CHK-B:56, 71, 136; PLAN:137, 167, 169.
- **Failure:** the candidate checks run as `python /source/…` inside the offline entry, which has only `/source` and `/outputs` and "no socket/network effects". The scenarios `status`, `observe`, `task takeover` and `recover` use a host `$CONTROLLER` path and need the fixture Kata/Codex transports. `recover` and `takeover` also mutate state. Either they cannot execute, or the checker runs on the host, unstated.
- **Fix:** define each mode's executor:
  - `host-fixture-execute` is run by the lead's pinned controller during fixture preparation and yields a receipt.
  - The in-Insula checker only parses the document and compares receipts.
  
  Rename the mode to reflect that. Also state whether `/outputs/fixtures/<pilot>` is a copy of the prepared fixture or the `/outputs` mount itself.

**N6 — The pilot checker executes from the candidate tree, and no step enforces the write scope on the candidate diff.** CHK-A:12, 26, 40; PLAN:135, 204–205; SPEC:79.
- **Failure:** `/source` is the complete candidate, so C supplies the `pilot_checks.py`, `collab_checks.py` and manifest that judge C. Task 51's tests bind commit, tree, parent and context, but never check that `diff(B..C)` lies inside the brief's allowed writes. A candidate that edits its own verifier, or any file outside `docs/collaboration/operations/`, is accepted.
- **Fix:**
  - Add a submission/verification refusal (SCOPE_CONFLICT) when changed paths fall outside the admitted scope, with a 51 test.
  - Have the audit confirm that the checker and manifest blob IDs in C equal those at the admitted base.

**P2**

**N7 — E's fixtures contradict the committed manifest text.** CHK-B:67, 88, 109, 132, 150, 170; PLAN:167, 258.
- **Failure:** every oracle hard-codes "prepilot fixtures at exact B, completed before pilot dispatch". PLAN:258 requires E's fixtures at exact C, prepared after dispatch. The worker cannot edit the manifest, so E's check is either unsatisfiable or satisfied by D's fixtures.
- **Fix:** reword to "the candidate's admitted base, audited before that candidate's worker launches". Also state whether fixture-project worker threads count against the two-thread cap.

**N8 — `unknown-stop` expects exit 3; the contract says refusal.** CHK-B:86–87; PLAN:63, 149; SPEC:128.
- **Failure:** takeover on unresolved state "refuses", which is exit 2 with reason UNKNOWN_EFFECT. The manifest expects outcome `unknown`, exit 3.
- **Fix:** pick one and state the rule. Suggested: a precondition that sees unknown state is `refused`; `unknown` is reserved for this operation's own uncertain effect.

**N9 — The progress classifier makes ordinary development look stuck, and the heartbeat source is assumed.** PLAN:155, 157; ST:58; T54:34.
- **Failure:** HEAD/diff changes and checkpoints do not count; findings need a lead acknowledgement. A worker coding for 15 minutes becomes STUCK_SUSPECTED unless the lead acknowledges within 10. "The pinned resource wrapper's heartbeat sequence" is not visible in `stage.py`, which writes `worker-resource.json` only at the end. If it does not exist, the stalled-operation verifier can only yield UNKNOWN.
- **Fix:**
  - Count independently observed transitions as progress without lead acknowledgement: a pinned check argv changing exit status, or a new declared artifact digest.
  - Confirm the heartbeat in pinned source, or specify a collaboration-owned fixture wrapper that emits one, without touching frozen helpers.

**N10 — Gate invocation does not bind X, and two different "admission" documents share one definition.** PLAN:86, 91–92, 119.
- **Failure:** the `gate` argv has no candidate or materialization argument and uses relative script paths. The admission JSON is defined to pin Kata project IDs, which do not exist at gate 49.
- **Fix:**
  - Add `--candidate X --materialization RECEIPT` and run the driver from the materialized path.
  - Define a gate admission (fixture identities) separately from the project admission consumed by `init`.

**N11 — `task start` envelope and exit semantics.** PLAN:63, 147.
- **Failure:** "JSON commands emit one envelope", but `start` emits an acknowledgement envelope and then supervises to a terminal turn. Which result sets the exit code is undefined, and CHK-A:99–100 expects exit 0.
- **Fix:** define a two-record stream (ack, then turn result) with the exit code from the last. State which `recover` path re-attaches after supervisor loss.

**N12 — The coverage manifest omits ticket verifiers and uses one generic evidence triple for all 39 cases.** COV throughout.
- **Failure:** verifiers absent from COV:
  - T50:29 — worktree index/HEAD separation and the canonical-mainline guard;
  - T50:29 and PLAN:195 — multi-turn/resume and the fork fixture;
  - T53:49 — third-start, duplicate and GPU refusals in the final pilot;
  - T54:34 — idle-between-turn and long-job progress.
  
  Since "missing coverage refuses" is relative to COV, omitted verifiers can be skipped silently.
- **Fix:** add these cases and give each case specific artifact names.

**N13 — Native-goal and fork fixtures have no creator or authority.** PLAN:145, 189, 195, 247; T54:33; RT:56.
- **Failure:** the controller "never creates/pauses/completes a native goal" and `Codex` has no fork method, yet gates 50 and 54 require goal pause/limit/complete and fork fixtures. "Existing separately authorized" fixtures are not identified.
- **Fix:** state who creates them (the lead, manually, on a non-managed fixture thread), under which user authorization, and that they hold no seat.

**N14 — The gate briefly acquires the real scientific lock.** PLAN:161.
- **Failure:** an idle-time acquire/release can make a concurrent scientific launcher see busy, and may rewrite owner metadata. The implementation was not supplied.
- **Fix:** default to read-only wiring validation plus fixture contention. Make the real acquire conditional on explicit user approval and on confirming the lock's caller semantics.

**N15 — Final candidate F has no owner, path or landing mechanism.** PLAN:260; COV:399–400.
- **Fix:** name the directory, the producer (lead, or a managed attempt under ticket 53) and whether `task land` or the manual path applies.

**N16 — Fixture Kata "inside actual Insula" contradicts the offline entry.** PLAN:182 against PLAN:133, 137.
- **Fix:** state that Kata export/restore runs through the host adapter and only store/Git tests run in Insula; or add Kata to the rootfs and prove a fixture daemon runs offline.

### Implementation quality

**P2**

**N17 — Manual close syntax differs between documents.** PLAN:220 uses `--reason done --test`; Q:121–125 uses `--done --evidence 'test:…'`. Pin the one that v0.14.3 help actually shows.

**P3**

- **N18** — PLAN:240 takes `now: float` while PLAN:65 requires integer milliseconds.
- **N19** — PLAN:163 does not say which `layout-profile` key is the root, and does not require an LS before PUT. Overwrite behaviour of `put` is unproved.
- **N20** — `launch_plan` hard-codes `PYTHONPATH=/experiment` and `--chdir /experiment` (`insula_entry.py:22`). PLAN:135 should say the new entry rewrites those argv values before `run_stage` and that the audit checks the final argv.
- **N21** — PLAN:143 should require the corroborating item to be worker-authored within the attempt's turn range, not a lead message quoting the digest.
- **N22** — PLAN:73 `task import --task-map FILE` does not say whether FILE is input or output. The "committed independent fixture briefs" at PLAN:195 have no file home.

## 4. Mandatory live capability probes

Help or schema presence only; live behaviour unproved:

- **Kata:**
  - `init --project` (the `--workspace` flag is not confirmed by the ledger);
  - idempotency key and claim refusal without `--force`;
  - metadata `--if-match`;
  - `import --target --new-instance`;
  - a second daemon under its own `KATA_HOME`/socket.
  
  If the second daemon fails, the response is unspecified and the plan should say so.
- **Codex:**
  - `thread/goal/get`, `thread/queue/list` and `thread/list` cwd filter;
  - whether reads touch thread state;
  - turn survival on proxy disconnect;
  - whether `approvalPolicy=never` really yields no client requests;
  - owned process handles (see N3).

No evidence at all yet:

- **Worker sandbox:** writing the common `.git` from a linked worktree; nested bwrap for worker-owned Insula probes. Failure blocks gate 50 implicitly; the plan should say whether widening the sandbox grant is permitted.
- **Runtime:**
  - container build/export with pinned inputs;
  - third-party imports of the `resources/` closure and `archive_worker` inside the CPU rootfs;
  - Git under `--clearenv` and a user namespace (safe.directory, HOME);
  - lock/fsync semantics on the real state filesystem.
- **HDFS:** Waystone `put` overwrite semantics, token-file authentication, stability of the pinned debug binary.
- **Resource wrapper:** existence of a heartbeat (N9); whether the source freezer writes outside collaboration state.

PLAN:99 covers runtime failure ("blocker, not a mock"). N3 and the fixture daemon are the two probes whose failure response is missing.

## 5. Final assessment

The corrected bundle fixes the ordering, bootstrap and runtime-coupling problems honestly. The 53.0 split is consistent across the plan, spec, queue policy and tickets, with no final 53/54 verifier waived. It is not ready because the new enforcement artifacts do not yet work:

- the coverage manifest cannot be satisfied at gate time (N1);
- the auditor is not independent of the producer (N2);
- the pilot manifests cannot run as specified and can be altered by their own candidate (N5, N6);
- no-goal mode lacks a continuation command and a stop rule that survives a likely probe failure (N3, N4).

Fixing N1–N6 and the P2 contradictions N7, N8 and N17 would make the plan approvable. This review does not close any implementation gate.
