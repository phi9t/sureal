# 11 — Establish independent point-semantic segmentation

**Goal / what to deliver:** Establish native TOP-point semantic predictions independently from the detection model.

**Blocked by:** [07](07-scientific-protocol.md), [08](08-gpu-runtime.md), [09](09-perception-evaluators.md)

**Status:** planned — blocked by prerequisite verification

**Lane:** core

**Verifier:** Live training/inference and original-range export; independent point-key/label-mask reconciliation and class IoU calculation on held-out predictions.

## Acceptance criteria

- [ ] All native semantic classes and undefined masks follow the pinned ontology; valid background geometry is retained.
- [ ] Original sensor/return/pixel identity survives export; absent labels do not become background.
- [ ] Finite gradients and training-only overfit criterion pass; held-out per-class IoU/mIoU and eligible counts are reported.
- [ ] Model, training budget and seeds are recorded independently of detection; foreground selection is not substituted for semantic segmentation.
- [ ] Independently validate live Insula receipt, candidate/input/runtime identities, required assertions, output hashes and measured resources; missing or failed checks prohibit closure.
- [ ] Publish a reviewable evidence summary with exact replay recipe, observed outcome and limitations; existing host tests or historical receipts alone do not close this ticket.

## Binding completion policy

[Program goal and evidence policy](program-goal.md) applies in full. Preparation may occur before blockers clear; candidate execution/promotion and completion require verified blockers. Scientific completion permits negative/inconclusive findings. Adoption requires the separately stated promotion rule.

## Independent implementation preparation

[All-point semantic candidate fixtures](../../../experiments/waymo-perception/research/point-semantic-preparation-verified.json) verify an independent physical-measurement MLP/global-context head with all23 native logits, no foreground filtering, permutationequivariance and explicit absent/undefined label handling. CPU Torch backward is finite. This is a candidate baseline, not a paper reproduction or scientific modelselection; realpoint GPU resources, architecture/protocol freeze, optimization/overfit, original-key export and heldout metrics remain open.

[Native CPU integration evidence](../../../experiments/waymo-perception/research/native-point-semantic-cpu-verified.json) covers all157,870points across bothTOPreturns of one labeledengineeringframe,152,773eligible targets, finitebackward and separately checked sourcepixelidentity/fullnativehistogram. Zerooptimizersteps; GPUcost and scientifictraining/export/heldoutevaluation remain open.

[Native model-output semantic scoring evidence](../../../experiments/waymo-perception/research/native-point-semantic-scoring-verified.json) verifies originalpoint export/compression/frame identity and native mIoU parity with independent confusion on bothTOPreturns. This is untrained engineering integration; protocol/training/overfit/heldoutevaluation remain open.

[Native GPU resource evidence](../../../experiments/waymo-perception/research/native-point-semantic-gpu-verified.json) verifies all157,870nativepoints and152,773eligiblelabels with zerooptimizersteps and813,467,136allocatedpeakbytes, plus separate originalpixelidentity checker. The0.522s interval includes predictionhostcopy/outputwrites. This is engineeringresourcepreparation, not trainingcost/protocolfreeze or heldoutmodelquality.
