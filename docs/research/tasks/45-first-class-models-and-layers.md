# 45 — First-class models and neural layers

Design milestone: MT-1. Workstream: first-class models and training.

**Goal:** make all maintained perception architectures constructible from installed `sureal.models`, with concentrated detector assembly and meaningful internal encoder/backbone seams, preserving scientific behavior.

**Dependencies:** 44. The approved implementation plan fixes exact source mappings and public interfaces before execution.

**Spec:** [Models/training design](../../superpowers/specs/2026-10-03-first-class-models-training-design.md).

## Deliverables

- First-class detector assembly/heads, pillar/point/range neural layers, normalization and dense/sparse BEV implementations.
- A maintained construction seam for existing scientific model choices; experiment catalogues continue to own treatment definitions.
- Shared dense feature/head execution, replacing duplicated behavior in `PillarDetector`, `EncodedDetector` and `AdvancedDetector` without changing parameter registration.
- Package discovery installs `sureal` alongside `surflo`; scientific imports use neither historical experiment modules nor experiment-directory path injection.
- New versioned source staging includes every canonical scientific dependency needed inside Insula. Historical frozen packages remain unchanged.

Current source families: `pipeline/pillar_detector.py`, `pipeline/pillar_encoder.py`, `gpu/architecture_variants.py`, `gpu/architecture_followups.py`, `gpu/norm_variants.py`, `advanced/models.py`, `advanced/point_modules.py`, `advanced/range_fusion.py`, `advanced/spatial_modules.py`.

## Verifiers

- In live Insula, compare old/new initial tensors, ordered named parameters/buffers and post-construction RNG for every supported treatment.
- Compare train/eval ordered heads, reference losses and gradients using the same admitted observation families and runtime.
- Strictly load retained model state; compare parameter traversal against Adam mapping, not just state-dict spelling.
- Independently check masking/ragged reductions, point permutation behavior, fine/coarse output-grid equivalence and attention/MLP/range/zero-range controls.
- In a clean CPU-capable runtime directory, import the installed scientific package without initializing CUDA, reading a fixture or executing a job.

## Acceptance

- All supported treatment rows are covered. Packing/optimization controls and `all_pillars` retain their own meanings; they are not counted as new architectures.
- Preserve exact head values/order where promised by the reference: row, column, anchor; 524,288 anchors with four classification, seven box and two direction channels.
- Model-specific registration order and constructor RNG draw history remain exact. Strict checkpoint loading needs no key conversion.
- Preserve range observation binding after device placement; fixture-specific buffers remain nonpersistent and required at inference.
- Model input contains physical measurements only; supervision metadata cannot leak into learned features.
- Native resource caps and import/staging independence pass actual live checks. Independent verification does not import the implementation it is meant to verify.

## Closure evidence

Retain paired source manifests, per-case comparison results, independent model/lineage receipts, import/staging receipt, checkpoint compatibility inventories, resource measurements and reviewed landed commits. Any mismatch leaves the affected gate open; do not widen tolerance to admit a refactor.
