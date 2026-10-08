# 40: Sparse multiscale BEV transformer

Status: implementing under approved written design/inline plan; live model and fitting admission pending.

Goal: Test occupied-token multiscale spatial processing against the dense CNN under the same physical head lattice.

Design: [expanded architecture spec](../../../docs/superpowers/specs/2026-10-02-expanded-single-batch-architectures-design.md).

Implementation verifier: Independent sparse set/hierarchy/shift/mask conservation and deterministic gradients; metric positions; shared PFN/up/head initial weights; actual-frame resource and flatten-order checks.

Training verifier: serial live Insula fixed73-object/all-four-class batch, seed17, original loss/Adam/clip and versionedv3 decode; independent literal losses at every checkpoint, proposal/physical metadata/GT/export/native metric replay, exact complete head/model/Adam/RNG trajectory replay.

Acceptance: each implementation milestone needs live receipts. Fixed-batch task closes only with every class native LEVEL2 APH>=0.8 at two consecutive sampled checkpoints including terminal, or a fully audited finite10,000-update censored result. Record fit intervals and synchronized time, normalization/truncation/topology co-changes, parameters, clipping and peak resources. An implementation/resource failure stays open. No heldout or broader research-program completion claim.

Resources: GPU allocated8GiB, RSS16GiB, raw2GiB, scientific unique payload15GiB until explicitly changed. Preserve historical evidence; reserve before writes.
