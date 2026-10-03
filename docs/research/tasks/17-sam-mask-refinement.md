# 17 — Compare frozen SAM spatial refinement

**Goal / what to deliver:** Determine whether SAM/SAM 3 improve pixel support over identical predicted camera boxes.

**Blocked by:** [14](14-camera-box-mask-baselines.md)

**Status:** planned — blocked by prerequisite verification

**Lane:** core

**Verifier:** Live B0 rectangle/B1 SAM/B2 SAM 3 spatial inference; independently validate prompts, mask coordinates, checkpoints, eligibility and segment-paired scores.

## Acceptance criteria

- [ ] All treatments use identical predicted prompts/classes/thresholds; oracle prompts are reported separately.
- [ ] SAM 3 spatial instance mode is enabled and verified; concept exemplars and SAM 3.1 are not silently substituted.
- [ ] Report end-to-end eligible-pixel scores, prompt coverage/false prompts and matched-object mask quality separately.
- [ ] Checkpoint access and resource limits pass; frozen models remain frozen and failures cannot promote artifacts.
- [ ] Independently validate live Insula receipt, candidate/input/runtime identities, required assertions, output hashes and measured resources; missing or failed checks prohibit closure.
- [ ] Publish a reviewable evidence summary with exact replay recipe, observed outcome and limitations; existing host tests or historical receipts alone do not close this ticket.

## Binding completion policy

[Program goal and evidence policy](program-goal.md) applies in full. Preparation may occur before blockers clear; candidate execution/promotion and completion require verified blockers. Scientific completion permits negative/inconclusive findings. Adoption requires the separately stated promotion rule.

## Pending semantic evidence contract

[Candidate semantic provenance](../../../experiments/waymo-perception/research/mask-semantic-provenance-candidate.md) addresses the coarse detector/fine segmentation mismatch. Predicted camera semantic evidence must be held identical across box/SAM/SAM 3 supports; ambiguous mappings abstain while a common independent LiDAR prediction retains full native point support. Mapping, pooling and fallback remain candidate decisions under ticket 07; this note is not task closure.

Frozen teacher engineering execution: `research/sam-native-image-independent-verified.json` records official pinned SAM ViT-B checkpoint/code in live GPU Insula on a native1280×1920 camera image with three explicitly tagged oracle camera-box prompts. Independent CPU restoration verifies every original-image mask pixel from retained low-resolution logits; receipt/current code/checkpoint/artifact hashes agree. Image encoding0.401s, batched mask decode0.085s and peak allocated2,905,302,528B, zero optimizer steps. These are engineering oracle prompts, not the required predicted-box scientific treatment. Native mask quality, detector miss/false-prompt accounting, point transfer, matched held-out comparison and SAM3 remain open.

Whole-frame engineering oracle coverage: `research/sam-full-frame-independent-verified.json` admits all63 source-ordered prompts, exact native mask restoration in two-mask CPU chunks, and literal point relations. `research/sam-full-frame-coverage.json` records26 masks with projected TOP support and37 with none;1486 unique points lie in any mask, with47 in overlapping masks. No oracle prompt is removed for poor output/support. All visibility-qualified support remains unpromoted. Predicted-box native quality, calibrated timing/visibility and scientific held-out comparisons remain open.
