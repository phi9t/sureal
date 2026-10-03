# Expanded Single-Batch Architectures Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement and run every planned architecture idea to an independently verified fixed-batch overfit or finite10,000-update censored result.

**Architecture:** Add an `advanced/` experiment family without changing the frozen original sweep or its16-row catalog. Reuse its admitted fixture, objective, native v3 decoder, loss audit and replay/lifecycle rules. New cache/model factories have explicit case-specific inputs and independent references; baseline evidence is referenced rather than trained again.

**Tech Stack:** Torch/NumPy and existing locked Insula CPU/GPU/native CPP roots; no TensorFlow.

**Spec:** ../specs/2026-10-02-expanded-single-batch-architectures-design.md (approved by user).

## Global Constraints

Fixed73-object/all-four-class frame; same physical anchors and256² detection lattice; v3 decode; seed17, FP32, TF32off, deterministic algorithms, Adam1e-4, clip10. Two consecutive sampled native all-class LEVEL2 APH>=0.8 including terminal; unchanged extension to10,000. Serial GPU, allocated8GiB, workerRSS16GiB, raw2GiB. Local scientific unique payload15GiB with user-authorized HDFS retention; reserve before writing and retain historical evidence. No incidental commit, merge or publication.

## Review Focus

Point identities and evaluation/label fields must remain separate from model inputs.
Grid boundaries/strides must preserve physical head anchors and every nativeGT.
Sparse/ragged CUDA reductions must support exact deterministic trajectory replay.
New parameters must receive finite gradients; unused range prediction heads are excluded.
Resource/implementation failures must not be reported as successful overfit or finite10,000-update negatives.

## Task 0 — verified HDFS retention

Files: advanced/archive.py, advanced/archive_worker.py, advanced/test_archive.py and research HDFS publication/readback receipts.
- [ ] Resolve project paths through Waystone; verify current authenticated connection without logging credentials. Bound client processes externally when native timeout does not cover direct I/O.
- [ ] Write CPU Insula RED/GREEN archive contracts: safe member paths, deterministic manifest, immutable file hashes and exact member accounting.
- [ ] Upload complete admitted new-run payloads and manifests to unique content-addressed HDFS paths; independently download and verify inside CPU Insula. Preserve failed transfers; never overwrite a different archive.
- [ ] Record archival lineage and verified bounded rehydration; only then release specifically declared new local payload. Preserve historical artifacts and keep15GiB local accounting honest.

## Task 1 — advanced cache contracts (tickets36,37,39)

Files: advanced/packing.py, advanced/prepare.py, advanced/test_packing.py, advanced/cache_contract.py; fixture receipts under research/advanced-allclass-fixture-verified.json.
- [ ] Write synthetic failing tests for fine/coarse grid boundaries, ragged segmented ordering/counts, cap/source accounting and original point identities.
- [ ] Add grid packing via existing pack_points with case-specific cell/grid; independent literal grouping/sampling reference.
- [ ] Add ragged flat points/counts/coordinates/source indices and an independent point-for-point reference, with20,000 pillar cap unchanged.
- [ ] Read raw LiDAR rows for native10 sensor/return shapes and first3 physical channels. Reconcile valid pixels and original physical intensity/identity; pack range grids/valid masks and point-to-pixel indices. No NLZ/label arrays enter observations.
- [ ] Run separate producer/reference CPU Insula workers on synthetic and actual fixed frame; preserve failed outputs and source/receipt hashes. Retain original native target hashes and73GT unchanged.

## Task 2 — point and range modules (tickets37–39)

Files: advanced/point_modules.py, advanced/range_fusion.py, advanced/models.py, advanced/model_contract.py; live fixtures and independent scalar references.
- [ ] Run liveGPU RED missing-module contracts; implement exact ragged decorations/reductions, point attention with512-pillar chunks and pointwise control, and range features/zero-initialized fusion from approved spec.
- [ ] Check deterministic segmented mean/max values and gradients; point permutation, valid masks, padding exclusion and no-cap equivalence.
- [ ] Check range native gather order and gradients, zero-fusion equivalence to baseline heads, and frontend gradient after projection update; add zero-range ablation.
- [ ] Check shared initial PFN/backbone/head values where interfaces remain compatible; report new parameter counts without claiming FLOP matching.
- [ ] Run actual-frame full detector forward/backward and resource preflight in liveGPU Insula; independent evidence before marking runnable.

## Task 3 — grid and sparse spatial backbones (tickets36,40)

Files: advanced/spatial_modules.py, advanced/sparse_sets.py, advanced/models.py, advanced/spatial_contract.py.
- [ ] Run liveGPU RED contracts, then implement fine/coarse first-stride4/1 variants with unchanged later stages and heads.
- [ ] Implement exact multiscale occupied-token hierarchy,8×8 windows,64-token bounded sets, alternating axis/shifted second blocks and64/128/256 channels.
- [ ] Independent CPU/reference set membership and hierarchy conservation; live gradients, mask/shift boundaries, occupied-cell scatter and256² head flatten order.
- [ ] Preserve shared PFN/upsample/head initialization and explicitly report replaced denseCNN parameters. Run actual-frame forward/backward/preflight inside Insula.

## Task 4 — immutable runner and recipe catalog

Files: advanced/catalog.py, advanced/train.py, advanced/run.py, advanced/verify_results.py, advanced/README.md; extend architecture idea records only after live admission.
- [ ] Freeze six named treatments plus pointwise-only and zero-range controls. Keep original tier1/catalog.py and original source snapshots unchanged.
- [ ] Adapt resumable producer and exact replay to case-specific observations; bind/pin auxiliary range observations explicitly before model use. Persist optimizer/RNG and record all component losses, class statistics, clipping, synchronized update times and head hashes.
- [ ] Reuse immutable native scoring/literal-loss workers with unchanged heads/targets/protocol. Reconcile each summary entry to its producer and score receipts. Require every matrix row in final closure.
- [ ] Admit storage/resource preflight before launching each actual workload; keep15GiB locally using verified HDFS retention. Resolve deterministic implementation errors rather than silently relaxing checks.
- [ ] Verify recipes can list, prepare, run and resume by experiment ID; planned IDs stay non-runnable until their live contracts pass.

## Task 5 — serial overfit matrix and closure

- [ ] After the original GPU matrix/recovery/terminal-equivalence gates release the GPU lock, run the advanced model contracts and serial training treatments.
- [ ] At sampled checkpoints0,25,50,100,200,300,500,750,1000,1500,2000,3000,4000,6000,8000,10000 run independent literal losses and native proposal/geometry/export/metric audits. Stop after two consecutive all-class passes; otherwise execute to10,000 with unchanged recipe.
- [ ] Exact full model/Adam/RNG/head trajectory replay after every training chunk precedes declared transient release. Preserve initial/final heads and terminal optimizer evidence within the admitted budget.
- [ ] Final liveInsula closure, one whole implementation review, persisted comparison and per-ticket acceptance. Include sampled fit intervals/times, retention, normalization/topology co-changes, native all-class terminal values, resources and censored negatives. Do not claim broader16-frame/segmentation/heldout research readiness.

Execution method proposed: inline in the already authorized isolated worktree; no concurrent GPU workload or modification of frozen original experiments. Scope and written design are approved; plan approved for inline execution. User selected HDFS retention with the local15GiB limit unchanged.
