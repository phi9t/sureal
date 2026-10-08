# Claude focused-check provenance

Claude checked exact commit `deed4aadf4ec94516674710613473c30d9d88e59`; [provenance](2026-10-03-sureal-collaboration-claude-focused-review.json) pins source and raw artifacts. This historical verdict identified only B1; the resolution ledger records its correction. No runtime acceptance is implied.

---

# Focused diff check at `deed4aa`

**Verdict: not PASS yet.** Twelve of the thirteen findings are resolved; R1 is resolved in content but its fix introduced one contradiction in the phase/role contract (B1 below). I found no dependency cycle. B1 is a two-file text/JSON edit, and nothing else blocks.

This is a documentation check only: nothing was executed, and no runtime acceptance is implied.

## Remaining blocker

**B1 — The role contract contradicts the case table and leaves each ticket's required roles undefined (from the R1/R5 fix).**

- **Evidence:**
  - `coverage.json` `phase_contract` says: "Require every case matching ticket,phase,candidate-role. Empty matching phase refuses. … All implementation and metadata role receipts required for ticket closure."
  - The plan (Exact candidate and independent audit) says the same: "Ticket closure requires all role/phase receipts."
- **Failure, read literally:**
  - Tickets 50, 51, 52, 53.0 and 54 have no metadata post-landing case (`exact-stage-landing` and `landed-foundation` are `implementation` only). A required metadata role therefore hits an empty phase, and closure refuses.
  - Ticket 53 has no implementation-role gate or post-landing case, so it fails the same way.
  - `pilot-state` is missing from the closure sentence, so 53's E-state receipts are not literally required.
- **Failure, read charitably:** if only "applicable" roles count, nothing says which roles a ticket has. A role that is never invoked is never refused, which reopens the vacuous pass R1 was meant to close.
- **Unclear `all`:** the five code gate cases in 49 are `all`, so the M gate would rerun them. In 53 the gate cases are `pilot-state`, so the F gate does not. The contract does not say which is intended.
- **Fix:**
  1. Add a `ticket_roles` map to `coverage.json`: 49 → implementation, metadata; 50, 51, 52, 53.0, 54 → implementation; 53 → pilot-state, metadata.
  2. Define `all` as "every role in that ticket's `ticket_roles`". If M should not rerun the code gate cases, mark those five as `implementation` instead.
  3. Replace the last `phase_contract` sentence with: "Ticket closure requires accepted gate and post-landing receipts for every role in `ticket_roles`; an empty phase refuses for those roles." Mirror that in the plan sentence.

## R1–R13 dispositions

| ID | Disposition | Evidence |
| --- | --- | --- |
| R1 | Resolved in content; B1 outstanding | Every ticket now has post-landing and closure cases, and the zero-case refusal is stated. I counted 63 cases (10/13/6/7/7/9/11), matching the ledger. |
| R2 | Resolved | Task 50 has the `refresh_task(..., runtime: Codex)` interface, `test_refresh_retains_stops_retires_and_uses_fresh_context`, the `explicit-refresh` gate case, and the takeover-retires-only statement in the plan and ticket 50. |
| R3 | Resolved | `runtime-probes.json` has a `stop-capability` probe (non-managed, A50 helper, per-probe authority). Gate case `stop-capability-before-first-claim` carries the ordering oracle, and the plan runs it before implementing 50. |
| R4 | Resolved | Gate cases `prepilot-fixtures-at-B` and `refresh-fixtures-at-C` exist. The materialized-C invocation is given, and preflight is collection only, with a case-only audit counted as a partial receipt. |
| R5 | Resolved; role semantics in B1 | `map-M-gate`, `map-M-landing` and `final-F-gate` are defined. The plan binds candidates M, E and F to their roles, and `F-gate-audit.json` now has an oracle. |
| R6 | Resolved | Split into gate-phase `fixture-import-revision-status` and a closure-phase real bootstrap/M/close case, with no running-brief clause at closure. |
| R7 | Resolved in text | Scope naming, the `systemd-run` recipe, sole membership, zero swap, and the 49 and per-worker 50 probes are stated. `kernel_scope.py` was not supplied, so validator conformance remains a live gate. |
| R8 | Resolved | Exit 64 with USAGE_ERROR and exit 1 with INTERNAL_ERROR are defined; a truncated envelope is unknown. |
| R9 | Resolved | `build-runtime` and `fixture --pilot` use absolute materialized paths and `--gate-admission`. |
| R10 | Resolved | The harness returns normally, uses `exit=False`, and treats inner exits as data. |
| R11 | Resolved | `stale-land` has `expected_reason: STALE_BASE`. |
| R12 | Resolved | The file map lists `heartbeat_worker.py` and `docs/collaboration/evidence/53/`. |
| R13 | Resolved | The "above" references, "scripts consuming the … manifests", ledger S19 and the README 53 dependencies are corrected. |

## Non-blocking tidy-ups

These can ride along with the B1 edit; none needs a re-check.

- **M sentence in `exact-stage-landing`:** "49 additionally records separately verified M" is copied into tickets 50–54, where it is noise. In 49 it has no evidence artifact, and M does not exist when X's landing is read back. Delete it; `map-M-landing` and the 49 closure case already cover M.
- **Takeover wording in ticket 50:** the earlier deliverable says controlled takeover "starts a new acknowledged attempt", while the new line says `task takeover` only retires. Reword the earlier one to "takeover followed by `task start`".
- **Probe command path:** `collab_live.py fixture --probe …` in the plan is still a bare script name, and the A50 stop-probe helper has no stated invocation.
- **Carried from N17:** the `kata init --workspace` help check is still not recorded in the ledger.
