# Sureal collaboration tooling

**PARKED — October5 user override:** local MAC completion is paused pending
Corenius infrastructure. No new dispatch or readiness-handshake implementation.
See [the consolidated closeout](../research/parking/2026-10-05/README.md). Historical criteria/status below
remain evidence, not permission to resume.


[Current user priority](../research/2026-10-05-mac-happy-path-first.md)
puts useful two-worker perception preparation before comprehensive hardening.
Explicit manual lead bootstrap can use existing tools; unfinished controller
commands remain unavailable. The
[full-admission backlog](../research/task-queue.md#historical-full-admission-sequence-october-4-2026)
retains MAC50–53 acceptance, followed by the
[persistent-lead extension](../superpowers/specs/2026-10-04-persistent-research-lead-design.md)
(55–57). These full-closure dependencies do not block provisional58 operation.
Models/training retain their own admission; the lead extension adds no new
dependency to44. See the [actual pilot record](../research/pilots/58/README.md).

The [approved design](../superpowers/specs/2026-10-03-sureal-serial-collaboration-design.md)
and [implementation plan](../superpowers/plans/2026-10-03-sureal-two-worker-collaboration.md)
define the acceptance gates. A successful command reports a bounded operation;
it does not accept a research task or implementation milestone.

Ticket49 provides project admission, durable intent/result records, source-pinned
task import and a read-only Kata status snapshot. Worker dispatch, candidate
verification, landing, cleanup and the overview are subsequent gated stages.
Their commands are unavailable until implemented and independently admitted.

Run tooling from the exact independently admitted source:

```text
python3 /ABS/admitted-source/scripts/collab.py init --canonical /ABS/sureal --state /ABS/external-state --admission /ABS/project-admission.json --operation-id ID
python3 /ABS/admitted-source/scripts/collab.py task import --project-state /ABS/external-state --definitions /ABS/reviewed-definitions.json --task-map-output /ABS/owned-metadata-worktree/docs/research/kata-task-map.json --operation-id ID
python3 /ABS/admitted-source/scripts/collab.py status --project-state /ABS/external-state --format json
```

Bootstrap is lead-owned: verify the exact clean mainline and tool/runtime pins,
retain actual native Kata project/binding readback, admit the project after its
implementation gate, then import reviewed committed definitions into the shared
project. Generate the map in a separate metadata worktree at the current base;
its binding/map commit requires its own live gate and exact landing proof.
Runtime journals and queue payloads stay outside canonical source.

JSON commands emit `ok`, `refused` or `unknown`. Exit0 means the operation
completed;2 refuses a precondition;3 holds an uncertain effect;64 denotes usage;
1 denotes an internal failure. An absent envelope is uncertain. A matching
operation ID reconciles retained facts; it never authorizes blind replay.
Status reports unadmitted Codex sources as `UNKNOWN` and task acceptance as
`NOT_AUDITED`.

Local checks use `python3 -B -m unittest discover -s tests/collab -p 'test_*.py' -v`.
The live driver is `scripts/collab_live.py`; its output retains actual commands,
interrupted bytes and source/runtime/resource identities for the separately
authored auditor. Local tests alone do not satisfy the live gate.


## Build the additive runtime

Use the [reviewed task49 build interface](../research/reviews/2026-10-04-collaboration-build-interface-reconciliation.md):

```text
python3 /ABS/materialized-X/scripts/collab_live.py build --materialization /ABS/materialization-X.json --packages /ABS/offline-packages --tools /ABS/tool-pins.json --output /ABS/fresh-runtime
```

Before building, independently reopen the exact retained/materialized source and
admit its source review, actual tool pins, offline package inputs and owned
output/resource scope. The candidate supplies Dockerfile/requirements; the
builder checks the complete package union/hash and Docker executable, retains
actual build/export/image/context receipts and reports `NOT_AUDITED`.
Assemble the complete runtime GateAdmission from those actual outputs before
running the live gate. The builder does not accept a task or start a worker.
The earlier planned `build-runtime` command is unavailable in the task49 source.
