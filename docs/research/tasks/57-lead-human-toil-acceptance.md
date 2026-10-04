# 57 — Decision reporting and human-toil acceptance

Priority: P0 (highest). Status: specified; execution not admitted.

The [October 5 happy-path priority](../2026-10-05-mac-happy-path-first.md)
permits58 provisional manual use first. Dependencies below govern this ticket's
full automation acceptance; they do not block58 or claim runtime capability.

**Goal:** demonstrate that admitted research coordination progresses without
routine human steering and that genuine decisions remain clear and accountable.

**Dependencies:**56 accepted and landed; reviewed written pilot plan with exact
task briefs, authority, fault inputs, resource limits and independent checks.

**Spec:** [Persistent research lead](../../superpowers/specs/2026-10-04-persistent-research-lead-design.md).

## Deliverables

- `scripts/_collab/lead_decisions.py` retains OPEN/RESOLVED/SUPERSEDED decisions,
  authority/evidence/affected-work identity, recommendation and resolution.
- Extend54's overview with current/next lead action, budgets, pending effects,
  unresolved decisions and freshness. Notifications track material changes;
  observer refresh cannot mutate authority or workers.
- Count human operational interventions per accepted task/experiment, preserving
  repeated requests and separately reporting scientific decisions, initial
  admission and deliberate verifier inputs. Report evidence coverage and limits.

## Verifiers and acceptance

- Run the spec's actual two-worker pilot with live Insula and independent source/
  receipt audit: continuation, bounded repair, exact landing/stale refresh,
  interruption recovery, HDFS retention and safe cleanup all hold.
- A genuine out-of-authority decision preserves the affected hold and yields one
  unresolved decision record, while known-safe independent work can continue.
  Restart preserves its identity; unchanged observations do not create repeated
  decision requests. Uncertain notification delivery is represented honestly.
- Require zero human operational prompts necessary for authorized pilot progress.
  Publish all intervention counts and denominator; any required routine relay,
  continuation or landing prompt leaves this acceptance open.
- Independently reconcile overview claims/counts with raw public items and exact
  accepted effects, prove no observer mutation and land coherent verified work.

## Closure evidence

Exact pilot/authority/source/runtime pins, real worker and lead event timelines,
decision/resolution evidence, intervention ledger, live independent receipts,
HDFS readback/recovery, landed closeout and measured limitations. A dashboard,
producer success claim or lower unverified prompt count is insufficient.
