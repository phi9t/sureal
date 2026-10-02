# 15 — Establish camera-only 3D and LET evaluation

**Goal / what to deliver:** Quantify camera-based metric localization and the effect of longitudinal error tolerance.

**Blocked by:** [07](07-scientific-protocol.md), [08](08-gpu-runtime.md), [09](09-perception-evaluators.md)

**Status:** planned — blocked by prerequisite verification

**Lane:** core

**Verifier:** Live camera-only model/export plus independently checked depth and LET matching/weight fixtures; evaluate declared reference-time targets.

## Acceptance criteria

- [ ] Pick and audit one perspective or BEV camera baseline, informed by FCOS3D/BEVDepth/BEVFormer, before training.
- [ ] Declare camera-time versus LiDAR-reference boxes and train/inference evidence; LiDAR-depth training is disclosed.
- [ ] Strict localization and configured LET metrics are both reported with depth/distance diagnostics.
- [ ] LET implementation passes TF-free parity checks; tolerance does not silently remove localization errors.
- [ ] Independently validate live Insula receipt, candidate/input/runtime identities, required assertions, output hashes and measured resources; missing or failed checks prohibit closure.
- [ ] Publish a reviewable evidence summary with exact replay recipe, observed outcome and limitations; existing host tests or historical receipts alone do not close this ticket.

## Binding completion policy

[Program goal and evidence policy](program-goal.md) applies in full. Preparation may occur before blockers clear; candidate execution/promotion and completion require verified blockers. Scientific completion permits negative/inconclusive findings. Adoption requires the separately stated promotion rule.
