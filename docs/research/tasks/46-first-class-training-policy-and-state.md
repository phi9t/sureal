# 46 — First-class training policy and state

Design milestone: MT-2. Workstream: first-class models and training.

**Goal:** give existing losses, optimizer policy, determinism and continuation state a maintained home under `sureal.training` without changing their scientific contracts.

**Dependencies:** 45. Retain the specialized sustained update loop and independent reference implementations.

**Spec:** [Models/training design](../../superpowers/specs/2026-10-03-first-class-models-training-design.md).

## Deliverables

- Detection reference loss and explicit fixed-frame versus sustained class-balanced objectives.
- Adam setup and deterministic execution policy separated from model construction.
- Explicit fixed-frame and sustained checkpoint formats and their capture/restore behavior.
- Sustained update/state ownership in training without unifying its sampling with fixed-frame execution.
- Thin newly admitted experiment adapters use canonical policy/state modules; no old frozen package is rewritten.

Current source families: `tier1/models.py`, `pipeline/detector_loss.py`, `cohort/sustained_loss.py`, `cohort/sustained_loop.py`, `cohort/sustained_state.py`; checkpoint handling in `tier1/train.py` and `advanced/train.py`.

## Verifiers

- Live Insula forward/backward/update comparison against the separately frozen reference, with independent literal-loss and reference-update checks.
- Exact uninterrupted/resumed comparison of model, Adam parameter mapping/moments, Torch/CUDA RNG and scientific step/cursor state; sustained Python/NumPy RNG is checked separately.
- Malformed or externally mismatched checkpoint identity, missing moment, incompatible parameter order, foreign observation binding and invalid cursor refusal before state mutation.
- Confirm class-balanced fixed-frame loss rejects missing positive classes, while the existing sustained absent-class equation matches its literal reference.
- Confirm no import-time seed change, CUDA initialization, filesystem access or training execution.

## Acceptance

- Preserve seed 17; recipe learning rate; Adam betas `(0.9, 0.999)`, epsilon `1e-8`, zero weight decay, `foreach=False`; current deterministic policy.
- Preserve focal classification, sine-based box comparison, Smooth L1 localization and direction cross-entropy, with total `classification + 2 * localization + 0.2 * direction`.
- Preserve both checkpoint schemas and their validation semantics without editing historical serialized artifacts.
- Preserve fixed-frame, shuffled balanced and sustained round-robin sampling as distinct recipes.
- Independent scalar/NumPy loss and reference-update verifiers remain separately implemented.
- Live comparisons, refusal probes and applicable resource checks pass; model construction no longer owns loss/optimizer policy.

## Closure evidence

Retain equation and trajectory comparison artifacts, checkpoint inventories, corruption-refusal outputs, independent receipts, source/runtime pins and reviewed landed commits. Full replay of the same producer is determinism evidence, not a substitute for independent loss/update verification.
