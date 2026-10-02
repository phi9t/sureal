# 26 — Test temporal memory and uncertainty

**Goal / what to deliver:** Determine whether causal memory improves persistence and corrects stale beliefs under missing observations.

**Blocked by:** [11](11-point-segmentation.md), [18](18-mask-to-lidar.md)

**Status:** conditional — not authorized for execution

**Lane:** conditional

**Verifier:** Live causal history inference with dropped-sensor/occlusion/reappearance controls; independent future-access, identity and held-out calibration checks.

## Acceptance criteria

- [ ] Activate after explicit history/output choice; freeze window, identity namespaces and uncertainty targets.
- [ ] Report causal versus offline variants separately; memory age/support and missing sensors are represented explicitly.
- [ ] Measure persistence, stale-belief correction, semantic/identity quality and calibration under predeclared perturbations.
- [ ] Independently validate live Insula receipt, candidate/input/runtime identities, required assertions, output hashes and measured resources; missing or failed checks prohibit closure.
- [ ] Publish a reviewable evidence summary with exact replay recipe, observed outcome and limitations; existing host tests or historical receipts alone do not close this ticket.

## Binding completion policy

[Program goal and evidence policy](program-goal.md) applies in full. Preparation may occur before blockers clear; candidate execution/promotion and completion require verified blockers. Scientific completion permits negative/inconclusive findings. Adoption requires the separately stated promotion rule.
