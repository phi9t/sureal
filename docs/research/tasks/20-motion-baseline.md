# 20 — Establish tracks-and-map forecasting reference

**Goal / what to deliver:** Establish a reproduced, resource-bounded MTR/Wayformer-informed forecasting baseline on native history and maps.

**Blocked by:** [07](07-scientific-protocol.md), [08](08-gpu-runtime.md), [19](19-motion-ingestion-evaluation.md)

**Status:** planned — blocked by prerequisite verification

**Lane:** core

**Verifier:** Live train/infer/export/score with independently checked causal features, finite gradients, candidate distributions and scenario-level held-out metrics.

## Acceptance criteria

- [ ] Choose one audited implementation and record deviations before training.
- [ ] Oracle historical tracks/maps are explicit; no predicted-perception performance is implied.
- [ ] Training-only overfit criterion passes; held-out mAP, minADE/minFDE, miss rate, seeds and costs are reported.
- [ ] Target identity, K, horizon and valid probabilities reconcile exactly through export.
- [ ] Independently validate live Insula receipt, candidate/input/runtime identities, required assertions, output hashes and measured resources; missing or failed checks prohibit closure.
- [ ] Publish a reviewable evidence summary with exact replay recipe, observed outcome and limitations; existing host tests or historical receipts alone do not close this ticket.

## Binding completion policy

[Program goal and evidence policy](program-goal.md) applies in full. Preparation may occur before blockers clear; candidate execution/promotion and completion require verified blockers. Scientific completion permits negative/inconclusive findings. Adoption requires the separately stated promotion rule.
