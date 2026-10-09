# Plan authority: launch-plan records, not command lines, are what new receipts are checked against

Status: ready-for-agent

Governing decisions: `autonomy/docs/adr/0003-executions-are-described-by-launch-plans.md` (the command-line parser stays *only* to read old receipts) and `autonomy/docs/adr/0002-evidence-blobs-go-through-a-blob-store.md`. Vocabulary follows `autonomy/CONTEXT.md`: launch plan, mount role, runtime lock, receipt, source snapshot. This spec is a follow-on to `.scratch/launch-plans/` and came from the 2026-10-09 architecture review (candidates 1 and 2).

## Problem Statement

New receipts already record a launch plan by mount role and digest. But much of the code that *checks* a new receipt still renders the plan to a sandbox command line and parses that command line back, which goes against ADR 0003. The bugs that kept coming back during the launch-plans landing grew out of this:

- **`/tmp` mount ordering is written three times.** It lives in the renderer, in the code that orders mounts for a record, and in `resources.command`, which splices mounts into an already-rendered command line. The resource runner applies mounts and then renders; the resource verifier splices the rendered command line. The two must agree byte for byte.
- **Callers force the legacy parser on new receipts.** Seven active call sites in `resources.stage`, `resources.checkpoint` and `training_execution.sustained_controller_backend` wrap a command in a fake receipt (`{'command': …}`) so that `read_receipt_mounts` parses it. `check_stage` parses the command line before it looks at the plan record.
- **The seam keeps moving.** The resource-wrapper helpers moved into the launch-plan module and back out again. The boundary test now pins them with an allowlist plus a "these are not public" test. `resources.command` imports five private launch-plan names through a parenthesised import, and the boundary regex only matches imports written on one line, so it misses them.
- **GPU driver pins are stored and checked more than once.** Each sustained stage receipt records `driver_hashes` keyed by host path *and* `gpu-driver:<name>` mount digests in its plan record. These are checked at render time, compared with each other by file name, re-hashed from host paths, and read a fourth way in `resources.dependencies`.
- **One digest bypasses the plan.** The scientific-root digest (and the source-snapshot digest) is attached to the frozen `LaunchPlan` with `object.__setattr__`, and a local `record_plan` copies it into the record. Recording the plan through `insula.launch_plan.record_plan` silently drops it.
- **Small checks are copied.** The Python-worker check is written five times and the GPU device list twice.

## Solution

The launch-plan module owns both building plans and checking them.

- **The resource wrapper becomes plan data.** It is a known set of mounts with mount roles, plus a command prefix, applied to a plan before it renders.
- **Checking a new receipt compares plans.** The plan the checker expects is compared with the plan record in the receipt: mount roles, targets, modes, digests, devices, environment, working directory and command. This happens inside the launch-plan module and works on data, not strings.
- **Rendering happens only when the plan launches,** and the `/tmp` and device ordering rule lives only in the renderer.
- **A plan can carry a declared digest for any named input,** and the plan record is the only authority for GPU driver pins.
- **The command-line parser is reached only for receipts that have no plan record:** legacy receipts, read exactly as before.

## User Stories

1. As a maintainer, I want the `/tmp` and device mount order written in exactly one place, so that fixing it once fixes the runner, the recorder and the verifier.
2. As a maintainer, I want the resource runner and the resource verifier to describe the wrapped stage the same way, so that they cannot disagree.
3. As an auditor, I want a new receipt checked against the plan it records, by role and digest, so that the check does not depend on how a command line is laid out.
4. As an auditor, I want legacy receipts, including every retained receipt and the balanced16 re-admission receipts, to keep verifying exactly as they do today.
5. As a researcher, I want a declared named-input digest to survive recording through the public `record_plan`, so that no receipt silently loses it.
6. As an auditor, I want GPU driver pins checked once, from the plan record, so that a pin mismatch has one place to fail and one message.
7. As a maintainer, I want the boundary test to catch private launch-plan imports however they are formatted, so that the seam stops moving.
8. As a maintainer, I want `resources.command` reduced to the legacy-receipt reader, so that deleting it later is mechanical.
9. As a test author, I want to assert on structured plans and records, not on `--ro-bind` index slices.

## Implementation Decisions

These decisions were made by the coordinator, under the user's standing delegation, on 2026-10-09.

- **Scope:** architecture-review candidates 1 and 2 only. One stage-execution module (candidate 3) and the publication module owning receipt classification (candidate 4) are separate future work.
- **The rendered command line does not change.** For every plan shape that runs today, the rendered argv after the change must be byte-identical to the argv before it. A golden characterisation test pins this first.
  - **Why:** changing what the sustained run launches would change its source snapshot meaning, and a running cohort should not need re-admission because of a refactor.
  - **Code is still code:** the source snapshot naturally includes the changed modules, so the next sustained admission covers them.
- **Every retained receipt must keep verifying, unchanged.** That includes the legacy, command-line-only receipts and the plan-record receipts written by blob-store 12 and earlier. An offline sweep over every retained receipt that active verifiers check is the acceptance gate for each ticket. The sweep itself must not write retained evidence.
- **How a receipt is classified:** a receipt with a `launch_plan` record is new-style and is checked only through plan comparison. A receipt without one is legacy and goes through the existing command-line parser. A new-style receipt whose command line disagrees with its record fails; the rendered command line is checked by rendering the record, not by parsing the command line.
- **Resource-wrapper mount roles:** the wrapper mounts get explicit roles, for example `resource-code` and `resource-output`. Their names are left to the implementer but must be stable and documented in the launch-plan module. Legacy receipts keep their inferred roles.
- **Named-input digests:** the plan builder accepts a declared digest for a named input and records it. The `object.__setattr__` path and the local `record_plan` in the sustained controller are deleted.
- **Driver pins:**
  - The `gpu-driver:*` mount digests in the plan record are the authority.
  - New receipts may keep a `driver_hashes` field only if it is derived from the plan record when the receipt is written, never computed separately.
  - Verification of new receipts reads only the plan record. Legacy receipts keep their current driver check.
- **Boundary test:**
  - The private-import scan must match parenthesised and multi-line imports.
  - The resource-helper allowlist and the "not public" test are deleted once no caller needs them.
  - The boundary test is not weakened in any other way.

## Testing Decisions

- **Good tests check external behaviour:** the plan a builder returns, the record `record_plan` writes, whether a receipt verifies, and the rendered argv for a fixed plan.
- **Golden argv test:** representative plans (CPU, GPU with driver pins, symlink rootfs entries, `/tmp` tmpfs plus mounts under `/tmp/`, resource-wrapped, sustained stage) render to the exact argv rendered at the base commit.
- **Retained-receipt sweep:** run every active receipt verifier over the retained receipts it covers today, offline, and record pass counts before and after. The counts must match exactly.
- **Prior art:** `insula/launch_plan_test.py`, `insula/launch_plan_boundary_test.py`, `resources/stage_test.py`, `training_execution/sustained_controller_backend_test.py`, and the deep legacy publication validation (9/9 retained publications) from commit 3b435f9.
- **Gates for every ticket:**
  - the default CPU suite `//autonomy/...`;
  - `//parallax/...`;
  - `--config=cuda //autonomy/...` on GPU 1 only, when it is free.

## Out of Scope

- One stage-execution module replacing the launcher swap in `resources.backend` (review candidate 3).
- The publication module owning receipt classification and release checks (candidate 4), and deduplicating the publisher helpers (candidate 5).
- HDFS writes, re-admission and rootfs rebuilds. Live acceptance runs (motion verifiers, a resource stage, the GPU live gate on GPU 1) are in scope from ticket 03 on.
- Frozen code under `research/`, `studies/*/procedure_records/` and `studies/architecture/harness/`.

## Further Notes

The architecture review report is at `/data02/home/philip.yang/devx/tmp/architecture-review-20261009T1900Z.html`; this spec is self-contained without it.
