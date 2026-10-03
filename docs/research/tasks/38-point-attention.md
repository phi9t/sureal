# 38: Within-pillar attention

Status: fixed-batch engineering task closed with independently verified sustained fitting; held-out comparison remains open.

Goal: Test masked relative-point interactions against shared baseline and a declared pointwise-only control.

Design: [expanded architecture spec](../../../docs/superpowers/specs/2026-10-02-expanded-single-batch-architectures-design.md).

Implementation verifier: Live padding/permutation/pooling invariants, attention-gradient checks, initial shared weights and parameter accounting; actual-frame memory and output shape.

Training verifier: serial live Insula fixed73-object/all-four-class batch, seed17, original loss/Adam/clip and versionedv3 decode; independent literal losses at every checkpoint, proposal/physical metadata/GT/export/native metric replay, exact complete head/model/Adam/RNG trajectory replay.

Acceptance: each implementation milestone needs live receipts. Fixed-batch task closes only with every class native LEVEL2 APH>=0.8 at two consecutive sampled checkpoints including terminal, or a fully audited finite10,000-update censored result. Record fit intervals and synchronized time, normalization/truncation/topology co-changes, parameters, clipping and peak resources. An implementation/resource failure stays open. No heldout or broader research-program completion claim.

Resources: GPU allocated8GiB, RSS16GiB, raw2GiB, scientific unique payload15GiB until explicitly changed. Preserve historical evidence; reserve before writes.

Closed evidence: [eight-case native closure](../../../experiments/waymo-perception/research/advanced-closure-expanded20261002a-verified.json), [results and limitations](../../../experiments/waymo-perception/research/advanced-expanded20261002a-status.md), and [exact HDFS retention/recovery index](../../../experiments/waymo-perception/research/advanced-expanded20261002a-hdfs-retention-index.json). These use the historical eligible ROI GT contract and provide no held-out improvement claim.

Relevant treatment/control rows both pass at500 and750 sampled updates. Use the report for parameter counts, observed training time, class scores and scope; do not interpret one-frame timing or fitting as a controlled generalization gain.
