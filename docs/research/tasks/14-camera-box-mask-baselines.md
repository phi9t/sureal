# 14 — Establish camera box and semantic baselines

**Goal / what to deliver:** Provide real predicted camera-box prompts and an independent native-label camera semantic reference.

**Blocked by:** [07](07-scientific-protocol.md), [08](08-gpu-runtime.md), [09](09-perception-evaluators.md)

**Status:** planned — blocked by prerequisite verification

**Lane:** core

**Verifier:** Live camera detector and semantic inference/export/scoring; independently validate original-image coordinates, class maps, coverage and empty/missing cases.

## Acceptance criteria

- [ ] Predicted 2D boxes and scores are produced without ground-truth or projected ground-truth prompts.
- [ ] Camera detector protocol and native semantic support/mapping are frozen; box/panoptic identity namespaces stay distinct.
- [ ] Held-out detection and camera semantic metrics, missed-object coverage and inference costs are reported.
- [ ] Preprocessing inversion and threshold-selection fixtures pass; all threshold tuning uses training/development support only.
- [ ] Independently validate live Insula receipt, candidate/input/runtime identities, required assertions, output hashes and measured resources; missing or failed checks prohibit closure.
- [ ] Publish a reviewable evidence summary with exact replay recipe, observed outcome and limitations; existing host tests or historical receipts alone do not close this ticket.

## Binding completion policy

[Program goal and evidence policy](program-goal.md) applies in full. Preparation may occur before blockers clear; candidate execution/promotion and completion require verified blockers. Scientific completion permits negative/inconclusive findings. Adoption requires the separately stated promotion rule.

[Camera-coordinate analytical evidence](../../../experiments/waymo-perception/research/camera-coordinates-verified.json) distinguishes align_corners=False pixelcenters from continuousboxedges and verifies resize/pad inversion using actualinteger dimensions. This prepares preprocessing inversion; actualimageinterpolation/nativeannotationconventions/model outputs and scientificprotocol remain open.

[Actual interpolation parity](../../../experiments/waymo-perception/research/camera-interpolation-parity-verified.json) checks the coordinate formulas against Torch bilinear align_corners=False, antialias=False ramps for both down/upsampling and padding, at float64 tolerance1e-12. This recipe-specific check does not certify SAM or any other model preprocessing convention.
