# 47 — Shared fixed-frame producer

Design milestone: MT-3. Workstream: first-class models and training.

**Goal:** train and resume tier1 and advanced one-frame treatments through one maintained producer in `sureal.training`, keeping experiment launch and persistence in thin adapters.

**Dependencies:** 46. The sustained loop stays specialized; this ticket does not build a universal trainer.

**Spec:** [Models/training design](../../superpowers/specs/2026-10-03-first-class-models-training-design.md).

## Deliverables

- One shared fixed-frame producer owns updates, checkpoint sampling, train/eval diagnostics, exact continuation and synchronized training timing.
- Explicit model/observation adapters retain normal, retain64, grid, ragged and range fixture behavior.
- Thin tier1/advanced workers own admitted mounted paths, reservation, serialization and receipt production; importing the trainer executes no job.
- Matched reference/candidate trajectory and resume gates, followed by unchanged independent export/native scoring audits.
- An easy-to-run first-tier investigation command reporting sampled iterations/time-to-fit, native class quality and execution/resource censoring.

Current duplication: `tier1/train.py` and `advanced/train.py`; orchestration and historical verifiers remain versioned experiment code.

## Verifiers

- Execute both producer adapters in live Insula using independently pinned old/new packages and identical fixtures/recipes.
- Compare sampled heads, scalar/component losses, gradients, model/Adam/RNG, records and scientific diagnostics for matched update sequences and resumed chunks.
- Restore normalization buffers after train-mode evaluation probes; verify probes do not change subsequent trajectory state.
- Run independent literal losses, proposal/NMS/measurement/GT audits, protobuf rereading and official native AP/APH replay.
- Exercise timed overfit reporting and malformed input/state/observation refusal; measure resource usage and enforce the existing GPU lock and storage reservation.

## Acceptance

- Both treatment families use the same producer implementation without rewriting its source text.
- Preserve ordered sampling, checkpoint keys/diagnostics and native scores. Wall-clock measurements are observed values, not expected to be bitwise equal.
- First-tier research gate remains per-class LEVEL2 APH at least 0.8 at two consecutive prescribed samples including terminal; primary ceiling 2,000 updates, extension 10,000, training bound 7,200 synchronized seconds.
- Report native quality, sampled fit interval, timing and resource/evaluator overhead. A finite capped case remains censored; the migration cannot reclassify the sparse-transformer negative as fitted or require it to become a scientific winner.
- Short numerical probes do not count as fresh complete overfit evidence; retained outcomes require their original admitted source identities, and a new complete outcome requires its own full gates.
- GPU 8 GiB, RSS 16 GiB, raw 2 GiB, scientific 15 GiB unique-inode storage and the 2 GiB active-case reservation remain enforced. Native scoring 14,400 seconds / host 14,700 seconds remain separate from training time.

## Closure evidence

Retain matched trajectory/resume artifacts, all independent audits, native curves, exact state comparisons, timed investigation output, resource receipts and reviewed landed changes. Any remaining duplicated trajectory implementation must have an explicit historical-replay purpose, not remain the maintained producer by accident.
