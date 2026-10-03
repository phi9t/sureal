# 24 — Test camera-teacher to LiDAR-student distillation

**Goal / what to deliver:** Determine whether training-only camera-mask supervision improves LiDAR-only inference.

**Blocked by:** [18](18-mask-to-lidar.md)

**Status:** conditional — not authorized for execution

**Lane:** conditional

**Verifier:** Live teacher artifact generation and student training; independent split/provenance audit and matched native-supervision-only comparison.

## Acceptance criteria

- [ ] Activate after positive mask-transfer evidence or a documented new hypothesis; generate teachers only from training data.
- [ ] Separate auxiliary pseudo-labels from native targets; confidence/visibility masking and full-scene support are retained.
- [ ] Compare matched budgets and seeds on held-out native mIoU/detection as declared; verify no camera/teacher access at LiDAR-only inference.
- [ ] Independently validate live Insula receipt, candidate/input/runtime identities, required assertions, output hashes and measured resources; missing or failed checks prohibit closure.
- [ ] Publish a reviewable evidence summary with exact replay recipe, observed outcome and limitations; existing host tests or historical receipts alone do not close this ticket.

## Binding completion policy

[Program goal and evidence policy](program-goal.md) applies in full. Preparation may occur before blockers clear; candidate execution/promotion and completion require verified blockers. Scientific completion permits negative/inconclusive findings. Adoption requires the separately stated promotion rule.
