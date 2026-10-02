# All-class single-batch overfit sweep

User authorization: run the experiments at overfit level, correcting the previous16-frame cohort comparison. Use the existing isolated tracer worktree and live Insula; Torch only.

## Goal and fixture

Prove or reject fixed-batch memorization for every runnable architecture and documented training control. Use one native frame, batch size1, with all required classes; it is not a16-frame study. Selection uses training annotations and target coverage only, before sweep outcomes: require at least5 anchor-covered cyclist observations, all4classes, and zero uncovered eligible GT; among qualifying balanced16 frames minimize native eligible GT count, break ties lexically. Frozen identity:16977844994272847523_2140_000_2160_000:1557450679864286. GT36vehicle/18pedestrian/14sign/5cyclist; positive anchors338/30/16/6. Preserve all73eligible boxes.

## Matrix

Reference: GN8 BEV with original pillarBN, same64-channel embedding and0.25m512-square input/head geometry. Runnable architecture treatments: deep_pfn, context_pfn, masked_pfn, residual_bev, window_bev, coarse_mlp, retain64, all_pillars. Norm controls: fullBN, GNbackbone+pointwiseLNpillar, no_norm. Optimization controls: foreground-prior classification bias(logit0.01), AdamLR3e-4, no gradient clipping, positive-class-balanced focal weights (weight390/(4*Nclass) on true positive classification terms only; negative terms and other losses unchanged). No combined treatments in this first sweep.

All-pillar treatment is an equivalence control on this fixture because15079occupied pillars are below20k; it must prove exact packed tensors and inference equality rather than claim additional retained measurements. Planned unimplemented architecture ideas remain separately tracked while the user clarifies scope; no fabricated runnable results.

## Training and acceptance

Seed17, Adam betas(.9,.999),eps1e-8,weightdecay0,foreachFalse, baselineLR1e-4/clip10, FP32, deterministic, TF32off, fixed physical observations and targets with no augmentation or resampling. Primary checkpoints0/25/50/100/200/300/500/750/1000/1500/2000; if the all-class gate does not sustain at the last two samples, extend the same trajectory at3000/4000/6000/8000/10000 updates. Cap10000; nonfinite/resource failures are outcomes, not silent retunes. A matched treatment uses the same fixture, initial compatible weights and declared one-factor change. Record parameter counts and optimizer initialization. All four native LEVEL2 APH values must reach0.8 at two consecutive sampled checkpoints including the terminal checkpoint. Loss reduction is diagnostic only. Time-to-fit is bracketed between sampled failures/passes; unsuccessful runs are right-censored.

Every milestone runs live Insula: physical packing/input isolation, module/gradient/norm contracts, actual optimizer execution, independent scalar/literal losses, deterministic trajectory/checkpoint+Adam replay, proposal/measurement/GT audit, protobuf reread and official evaluator reruns. Preserve the complete curve and perclass values, positive/negative loss and score/gradient diagnostics, clipping, synchronized training time and evaluator overhead. Resource guards: scientific15GiB, raw2GiB, allocatedGPU8GiB, processRSS16GiB; GPU runs serial.

## Bounded retention ruling

Existing artifacts remain byte-identical. Exact duplicates may be atomically hardlinked after hash verification, with before/after inode and digest evidence; count unique inode payload bytes against the same15GiB scientific cap and disclose historical logical-versus-physical accounting. New intermediate snapshots are transient scientific data: retain them through independent loss/inference/native-score audits, then remove only declared new temporary snapshots after persistent evidence is admitted. Retain source/runtime/input hashes, every curve, native predictions/GT/protobufs, expected head hashes and terminal model+Adam checkpoint. Independently replay the full deterministic trajectory against all expected checkpoint hashes before transient snapshots can be released. Retain initial/final heads and terminal checkpoint; this avoids a growing unbounded head archive while preserving deterministic reproducibility. No historical evidence deletion or off-budget payload storage.

## Decisions

A completed experiment can be a negative result. No larger-cohort or heldout promotion without the all-class Tier1 gate. Architecture/support, normalization and optimization are separate axes; apparent improvement does not prove a generalization benefit. All retained-data and task-specific research goals remain open beyond this sweep.


Execution refinement (2026-10-02, matching the user’s request to run to overfit):2000 is the primary update ceiling. A trajectory may stop sooner when two consecutive sampled native checkpoints, including the terminal sample, pass every class; all loss/proposal/export/native and exact replay admissions remain mandatory. Chunk boundaries300,500,750,1000,1500,2000 allow this verified stopping. Unsuccessful trajectories extend unchanged through3000,4000,6000,8000,10000. Earlier first-tier runs retain their original complete2000 trajectory.

2026-10-02 heading verifier correction:
The retained baseline exposes a decoder defect: direction-bin correction compares an unwrapped raw heading's sign. Equivalent angles separated by2pi can therefore decode to opposite orientations. Versioned `gpu/scored_proposals_v3.py` canonicalizes the raw angle before bin correction; literal audit independently implements this ordering. Live paired evaluation of identical2000-update heads raises pedestrianLEVEL2APH .758646→.999529 and sign .714347→.927947, with vehicle/cyclist unchanged. All73nativeGT remain present. Preserve legacyv2 scores and source; score the matched sweep consistently withv3. Existing optimization trajectories require new native scoring and exact replay, not duplicate training. The baseline completed4000updates before this verifier diagnosis; preserve/adopt that trajectory explicitly, and derive its earlier time-to-fit from the corrected sampled curve.
