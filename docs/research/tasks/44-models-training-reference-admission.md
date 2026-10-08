# 44 — Admit the models/training migration reference

Design milestone: MT-0. Workstream: first-class models and training.

**Goal:** freeze the actual landed scientific reference and prove that old/new implementation comparisons can execute in isolated, pinned runtimes before relocating model behavior.

**Activation:** the active worker finishes its current implementation milestone and lands ready owned work; pristine mainline and [53 — local protocol closeout](53-collaboration-cleanup-closeout.md) are admitted; this workstream's written design and implementation plan are reviewed. This does not require completing the entire research program or all future training. The existing worker's live source tree and running source packages remain intact.

**Dependencies:** current live runtime/geometry/evaluation foundations 01/06/08/09; the applicable resource and storage admission. This is a migration gate, not scientific completion of ticket 10.

**Spec:** [Models/training design](../../superpowers/specs/2026-10-03-first-class-models-training-design.md).

## Deliverables

- A machine-readable reference inventory binding landed revision, complete imported source closure, runtime/driver identity, selected fixture hashes, catalogue cases and retained checkpoints.
- All 16 tier1 treatment rows and eight advanced rows identified, including the nontrained `all_pillars` equivalence control.
- Per-treatment ordered parameter/buffer inventory, initial state/RNG identity, required observation family and expected output geometry.
- Explicit fixed-frame versus sustained state inventories; nonpersistent range observations recorded as required inputs rather than checkpoint contents.
- A separately frozen comparison harness and independent auditor capable of admitting two source closures. The harness must not resolve either implementation through the other one's imports.
- Actual live reference execution and retained outputs suitable for the migration comparisons.

## Verifiers

- Reopen and rehash fixtures and historical references; a path's existence is not admission.
- Run dedicated live CPU/CUDA Insula invocations under the existing runtime and exclusive GPU lock; record isolation, input/source/runtime identity and measured resource usage.
- Independently verify reference heads, parameter ordering, constructor RNG state and input lineage. Reuse existing analytic/literal checks without making them depend on the producer.
- Negative probes reject swapped reference/candidate identity, missing closure files, changed fixture content and a busy GPU lock before execution.

## Acceptance

- Every supported case has an exact reference and an explicitly paired observation/target recipe.
- Both checkpoint formats and all model-specific parameter orders are captured without conversion.
- Live reference execution and an independent artifact audit pass; there is a tested way to compare separately frozen implementations, not merely repeat one implementation.
- No active source inventory, runtime root, old evidence or checkpoint is changed.
- Package import/staging acceptance for real migrated scientific modules belongs to 45; this task does not create empty model packages to satisfy a superficial import check.

## Closure evidence

Retain the landed revision and inventories, fixture/runtime/source pins, actual commands, UTC start/end and exits, live logs, outputs, independent receipts and resource reports. Queue completion requires these artifacts and the reviewed landed change; an inventory-only host report leaves the live gate open.
