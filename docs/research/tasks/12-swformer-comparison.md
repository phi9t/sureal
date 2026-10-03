# 12 — Compare pillar encoding with SWFormer mechanisms

**Goal / what to deliver:** Measure the effect of sparse window attention beyond the PointPillars reference.

**Blocked by:** [10](10-pointpillars-detection.md)

**Status:** planned — blocked by prerequisite verification

**Lane:** core

**Verifier:** Live matched-budget encoder comparison with independently audited inputs, head controls, predictions and segment-level paired analysis.

## Acceptance criteria

- [ ] Freeze identical evidence/cohort/supervision and report compute-matched conditions.
- [ ] Use a common head where feasible; otherwise separate encoder and head ablations and avoid attributing combined changes solely to attention.
- [ ] Window shift, multiscale processing and diffusion treatments are explicit; unofficial implementation gaps are recorded.
- [ ] Report AP/APH effects with uncertainty and runtime/memory; negative results close the research ticket.
- [ ] Independently validate live Insula receipt, candidate/input/runtime identities, required assertions, output hashes and measured resources; missing or failed checks prohibit closure.
- [ ] Publish a reviewable evidence summary with exact replay recipe, observed outcome and limitations; existing host tests or historical receipts alone do not close this ticket.

## Binding completion policy

[Program goal and evidence policy](program-goal.md) applies in full. Preparation may occur before blockers clear; candidate execution/promotion and completion require verified blockers. Scientific completion permits negative/inconclusive findings. Adoption requires the separately stated promotion rule.

Sparse grouping preparation: research/sparse-windows-verified.json records4 live Insula groups for unique [batch,y,x] BEV tokens, explicit origin shifting without cyclic wrap, lossless power-of-two occupancy buckets and padding masks. Window membership survives input permutation, every token appears once, and padded capacity is below2× real tokens. This prepares the previously specified common-head SWFormer-style mechanism study, not an official port. Attention, multiscale fusion, diffusion, GPU resources and matched held-out comparisons remain open.

Attention operator preparation: research/sparse-window-attention-verified.json records3 CPU Torch groups in live content-locked Insula, zero optimizer updates. Uniform Q/K with identity V produces the independently expected window mean despite padding; batch isolation, original-order scatter, permutation consistency and finite feature/parameter gradients pass. Positional encodings, residual/FFN, multiscale/diffusion, native GPU pilots and matched scientific comparisons remain open. Host grouping/device-copy cost must be included in those resource pilots.

### Native engineering GPU integration — independently checked

Live Insula PFN → shifted sparse attention → BEV forward/backward passed with 14,384 pillars, 92,603 retained points and 938 windows. Independent live NumPy reconstruction verified window counts, unique coordinates, padded capacity (19,386 slots), and packed source SHA; receipt, artifacts and current code hashes agree. Pilot: 2.344 s forward/backward, 645,334,528 bytes peak allocated GPU memory, zero optimizer steps. Evidence: `research/sparse-window-native-independent-verified.json`. This operator lacks positional/residual/multiscale/diffusion blocks and does not establish trained detection quality or complete SWFormer reproduction. Scientific acceptance remains open.
