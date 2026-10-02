# 25 — Test a joint multimodal detector and segmenter

**Goal / what to deliver:** Determine whether shared multimodal representation helps both tasks relative to independently established models.

**Blocked by:** [10](10-pointpillars-detection.md), [11](11-point-segmentation.md), [14](14-camera-box-mask-baselines.md), [18](18-mask-to-lidar.md)

**Status:** conditional — not authorized for execution

**Lane:** conditional

**Verifier:** Live shared-model train/export/evaluate with separate-model, shared-no-SAM and added-teacher controls; independent task-mask/gradient and cost audit.

## Acceptance criteria

- [ ] Activate only after explicit architecture/budget decision; keep native task ontologies and masks distinct.
- [ ] Report both task outcomes, task interference and total inference/training cost; do not hide regression behind a combined score.
- [ ] Compare identical evidence/cohorts and matched capacity/budgets; teacher/fusion contribution is ablated separately.
- [ ] Independently validate live Insula receipt, candidate/input/runtime identities, required assertions, output hashes and measured resources; missing or failed checks prohibit closure.
- [ ] Publish a reviewable evidence summary with exact replay recipe, observed outcome and limitations; existing host tests or historical receipts alone do not close this ticket.

## Binding completion policy

[Program goal and evidence policy](program-goal.md) applies in full. Preparation may occur before blockers clear; candidate execution/promotion and completion require verified blockers. Scientific completion permits negative/inconclusive findings. Adoption requires the separately stated promotion rule.
