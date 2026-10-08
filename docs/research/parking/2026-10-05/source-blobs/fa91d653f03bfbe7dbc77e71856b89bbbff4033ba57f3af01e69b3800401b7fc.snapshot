# 38: Within-pillar attention

Status: implementing under approved written design/inline plan; live model and fitting admission pending.

Goal: Test masked relative-point interactions against shared baseline and a declared pointwise-only control.

Design: [expanded architecture spec](../../../docs/superpowers/specs/2026-10-02-expanded-single-batch-architectures-design.md).

Implementation verifier: Live padding/permutation/pooling invariants, attention-gradient checks, initial shared weights and parameter accounting; actual-frame memory and output shape.

Training verifier: serial live Insula fixed73-object/all-four-class batch, seed17, original loss/Adam/clip and versionedv3 decode; independent literal losses at every checkpoint, proposal/physical metadata/GT/export/native metric replay, exact complete head/model/Adam/RNG trajectory replay.

Acceptance: each implementation milestone needs live receipts. Fixed-batch task closes only with every class native LEVEL2 APH>=0.8 at two consecutive sampled checkpoints including terminal, or a fully audited finite10,000-update censored result. Record fit intervals and synchronized time, normalization/truncation/topology co-changes, parameters, clipping and peak resources. An implementation/resource failure stays open. No heldout or broader research-program completion claim.

Resources: GPU allocated8GiB, RSS16GiB, raw2GiB, scientific unique payload15GiB until explicitly changed. Preserve historical evidence; reserve before writes.
