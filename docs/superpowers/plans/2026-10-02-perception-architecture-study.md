# Perception Architecture Study Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** execute isolated architecture directions with independent live Insula quality/time evidence.

**Architecture:** add candidate wrappers without mutating the pinned reference pipeline. Preserve fixed native observations/targets for encoder/backbone candidates; regenerated caches for retention changes are independently admitted before use. Execute first cohort then gate subsequent subprojects.

**Tech Stack:** Torch,NumPy,existing locked Insula GPU/CPU/nativeCPP metric roots; no TensorFlow.

**Spec:** ../specs/2026-10-02-perception-architecture-study-design.md

## Global Constraints

Same seed17,Adam1e-4,2000 updates and11 checkpoints; allGT retained. GPU serial; GPU8GiB/RSS16GiB/scientific15GiB/raw2GiB. All implementation milestones require live Insula verifiers. Preserve historical outputs; absentcyclist/signfail blocks whole-model acceptance.

## Review Focus

Padded slots: test evaluation valid-point pooling and report unchanged firstBN padding policy.
Point permutation: native encoder fixtures must preserve pooled representation within floating-point tolerance.
Residual channels/stride: reuse same-width stride1 units only; test zero branch identity.
Source identity: verify pinned frame artifacts before training/export and score all nativeGT.
Decoder failures: record original failures, secondary scores require exact reference-equivalence evidence.

### Task 1: candidate modules and live contract

Files: gpu/architecture_variants.py,gpu/architecture-contract.py,.scratch/run-architecture-contract.py.
Interfaces: configure_architecture(model,variant) supports deep_pfn,context_pfn,residual_bev and returns detector with same forward signature/output. Pooled outputsP×64; contextual adapter forwards counts from detector without altering heads.
- [x] Write live fixtures for shape, gradients, point permutation, eval padding extension, residual zero-branch identity and shared initial weights.
- [x] Run lockedGPU Insula missing-module RED; implement specified wrappers; rerun GREEN. Pin all candidate/reference inputs and outputs.

### Task 2: first-cohort training and independent replay

Files: gpu/native-architecture-learning-curve.py,gpu/audit-architecture-checkpoint.py,.scratch/run-architecture-learning-curve.py,.scratch/audit-architecture-checkpoint.py.
Consumes Task1 configure_architecture plus original GN backbone recipe.
- [x] Adapt existing pinned norm harness to architecture-specific namespace/manifests without changing optimizer/targets/checkpoint grid.
- [x] Serial native train each3 variants; admit exact initial/final heads and Adam2000 states with separate live workers.
- [x] Independently reconcile literal loss/components/update-time arithmetic from saved heads and originalGT. Retain failures.

### Task 3: native quality comparison

Files: architecture-specific score and audit drivers under .scratch; research/architecture-first-cohort-results.json and .md.
Consumes Task2 retained heads/manifests.
- [x] Run score-before-decode secondary curve using existing proven decoder, recording declared scope and baseline exact-equivalence link.
- [x] Independently decode/NMS/source-point/NLZ/GT/protobuf/native-metric rerun each11 checkpoint exports.
- [x] Rehash producer/audit artifacts, report quality/time/params/resources and decisions; update tickets/ledger without closing wholemodel gate.

### Task 4: retention controls

Files: dedicated packing manifests/workers/retained-index audits and training namespaces.
- [x] Repack fixed physical frame at64points; live independent source reconciliation and unchanged target equivalence.
- [x] Run same training/score/replay gates as Tasks2–3 and record comparison.
- [ ] Specify and implement ragged segmented baseline equivalence; live test gradients/identity/resources before training.

### Task 5: spatial/range follow-ups and adoption

- [ ] Write exact grid/downsampling/anchor interface spec for fixed-head-spacing sweep; execute cache/geometry/training gates.
- [x] Specify window attention and parameter-matchedCNN; implement red→green and native training gates. (Declared parameter matching; FLOP matching remains open.)
- [ ] Specify local point attention and range-feature provenance; execute native gates.
- [ ] Resolve sign-support control, admit all4classfixture, run fixed16/multiseed/segmentheldout evaluations before adopting candidates or combining them.

Pre-flight: Task1 factory name/forward interface is consumed identically by Task2 replay and training. Task2 observation/target manifests feed Task3 without regeneration; Task4 explicitly regenerates observations only. Task5 needs additional concrete subproject specs before implementation; no implicit approval of unspecified attention/window settings. User requested execution; no renewed permission round for concrete Tasks1–4. No incidental baseline edits or commits of unrelated untracked files.

## Execution record (append-only)

Tasks1–3 implemented for firstcohort plus written masked/window/equalparameter controls; native train/scoring admission and strict re-admission receipts tracked in research/architecture-study-status.md. Task4 64point and evidence-driven allpillars controls implemented; ragged remains open. Task5 windowattention first diagnostic implemented with a parameter-matched control; grid/range/localpointattention/fullclass/heldout gates remain open. This does not mark the multi-stage plan complete.

Rulings: proceed natively under user's explicit spec-and-execute authorization; preserve original pipeline/history; no incidental commits of earlier untracked work. Fix scheduler planned-list bug and exclude original contextual timing, using exact exclusive repeat. Contextual pooling masking gets its own maskedcontrol. Windowattention versus coarseMLP is parameter-matched rather than FLOP-matched and cannot establish pure attention-mechanism benefit. New allpillars control follows live source-support finding; point sampling can differ because pillar-selection RNG draw disappears.
