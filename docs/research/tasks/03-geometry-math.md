# 03 — M2: verify the mathematical geometry foundation

**Goal / what to deliver:** Provide tested coordinate and uncertainty operations whose conventions are explicit enough for every sensor adapter.

**Blocked by:** [01](01-insula-runtime.md)

**Status:** verified-complete — 11 independent fixtures passed live; receipt independently reconciled

**Lane:** core

**Verifier:** Run analytic fixtures and independent finite differences live for SO(3)/SE(3), transform chains, polar conversion, projection, BEV indexing and covariance propagation.

## Acceptance criteria

- [x] Record axis, unit, transform direction, rotation-first tangent, coupled SE(3) exponential and perturbation conventions.
- [x] Verify noncommuting transforms, coupled translation, near-zero/near-pi rotations and manifold Jacobians against independent references.
- [x] Verify polar axes/singularities, optical depth versus radial range and half-open BEV boundaries.
- [x] Reject invalid covariance/transforms; declare numerical tolerances before execution and pass every fixture.
- [x] Generic radar radial-relative-velocity fixtures are identified as synthetic; no Waymo radar data is claimed.
- [x] Independently validate live Insula receipt, candidate/input/runtime identities, required assertions, output hashes and measured resources; missing or failed checks prohibit closure.
- [x] Publish a reviewable evidence summary with exact replay recipe, observed outcome and limitations; existing host tests or historical receipts alone do not close this ticket.

## Binding completion policy

[Program goal and evidence policy](program-goal.md) applies in full. Preparation may occur before blockers clear; candidate execution/promotion and completion require verified blockers. Scientific completion permits negative/inconclusive findings. Adoption requires the separately stated promotion rule.

Evidence: [M2 verification](../../../experiments/waymo-perception/research/m2-verified.json). Sensor reconstruction remains a separate pending ticket.
