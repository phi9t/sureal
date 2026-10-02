# 16 — Investigate reference-object distance estimation

**Goal / what to deliver:** Test whether reference-object relationships improve optical-axis distance estimates within evaluable dataset support.

**Blocked by:** [15](15-camera-3d-let.md)

**Status:** planned — blocked by prerequisite verification

**Lane:** core

**Verifier:** Live same-proposal distance comparison with predicted versus oracle reference depths separated; independent optical-depth reconstruction and distance-stratified error analysis.

## Acceptance criteria

- [ ] Target optical Z, proposal matching, reference selection and visibility rules are frozen.
- [ ] Prediction availability and upstream detector cost are included; oracle references are appendix-only controls.
- [ ] Report paired distance error and valid coverage within verified native label support.
- [ ] Do not claim the original long-range benchmark unless its labels are verified; missing long-range supervision is an explicit limitation.
- [ ] Independently validate live Insula receipt, candidate/input/runtime identities, required assertions, output hashes and measured resources; missing or failed checks prohibit closure.
- [ ] Publish a reviewable evidence summary with exact replay recipe, observed outcome and limitations; existing host tests or historical receipts alone do not close this ticket.

## Binding completion policy

[Program goal and evidence policy](program-goal.md) applies in full. Preparation may occur before blockers clear; candidate execution/promotion and completion require verified blockers. Scientific completion permits negative/inconclusive findings. Adoption requires the separately stated promotion rule.
