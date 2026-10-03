# 40: Sparse multiscale BEV transformer

Status: fixed-batch engineering task closed with an independently verified negative result at the 10,000-update cap; held-out comparison remains open.

Goal: Test occupied-token multiscale spatial processing against the dense CNN under the same physical head lattice.

Design: [expanded architecture spec](../../../docs/superpowers/specs/2026-10-02-expanded-single-batch-architectures-design.md).

Implementation verifier: Independent sparse set/hierarchy/shift/mask conservation and deterministic gradients; metric positions; shared PFN/up/head initial weights; actual-frame resource and flatten-order checks.

Training verifier: serial live Insula fixed73-object/all-four-class batch, seed17, original loss/Adam/clip and versionedv3 decode; independent literal losses at every checkpoint, proposal/physical metadata/GT/export/native metric replay, exact complete head/model/Adam/RNG trajectory replay.

Acceptance: each implementation milestone needs live receipts. Fixed-batch task closes only with every class native LEVEL2 APH>=0.8 at two consecutive sampled checkpoints including terminal, or a fully audited finite10,000-update censored result. Record fit intervals and synchronized time, normalization/truncation/topology co-changes, parameters, clipping and peak resources. An implementation/resource failure stays open. No heldout or broader research-program completion claim.

Resources: GPU allocated8GiB, RSS16GiB, raw2GiB, scientific unique payload15GiB until explicitly changed. Preserve historical evidence; reserve before writes.

Closed evidence: [eight-case native closure](../../../experiments/waymo-perception/research/advanced-closure-expanded20261002a-verified.json), [results and limitations](../../../experiments/waymo-perception/research/advanced-expanded20261002a-status.md), and [exact HDFS retention/recovery index](../../../experiments/waymo-perception/research/advanced-expanded20261002a-hdfs-retention-index.json). These use the historical eligible ROI GT contract and provide no held-out improvement claim.

The transformer finished at10,000 updates with vehicleAPH0.741925, below0.8; the other three classes pass. Training time is right-censored at1,925.60seconds. Preserve this negative result and the separately recorded support diagnostic. Neither proves that transformer models generally cannot fit.
