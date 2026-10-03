# 02 — M1: replay the complete native slice

**Goal / what to deliver:** Prove the acquired all-modality slice survives native-table loading without loss or accidental row multiplication.

**Blocked by:** [01](01-insula-runtime.md)

**Status:** verified-complete — full replay/source reconciliation/adversarial checks passed live

**Lane:** core

**Verifier:** Live replay of all 34 source files; independent reopening of source Parquet keys and reconciliation of every output row, checksum and modality coverage count.

## Acceptance criteria

- [x] All source hashes match the cohort lock; all 17 acquired component families are accounted for.
- [x] All native rows reconcile exactly to source keys at their native grain; no Cartesian sensor/object join.
- [x] Missing supervision and unresolved associations remain explicit; no fabricated matches.
- [x] Invalid source hash and duplicate/substituted key fixtures fail validation.
- [x] Independently validate live Insula receipt, candidate/input/runtime identities, required assertions, output hashes and measured resources; missing or failed checks prohibit closure.
- [x] Publish a reviewable evidence summary with exact replay recipe, observed outcome and limitations; existing host tests or historical receipts alone do not close this ticket.

## Binding completion policy

[Program goal and evidence policy](program-goal.md) applies in full. Preparation may occur before blockers clear; candidate execution/promotion and completion require verified blockers. Scientific completion permits negative/inconclusive findings. Adoption requires the separately stated promotion rule.

Evidence: [M1 verification](../../../experiments/waymo-perception/research/m1-verified.json).
