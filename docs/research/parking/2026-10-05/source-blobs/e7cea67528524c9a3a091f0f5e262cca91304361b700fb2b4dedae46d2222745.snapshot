# 05 — M4: inspect range, BEV and camera scene views

**Goal / what to deliver:** Make reconstructed scene evidence inspectable without hiding transformation or supervision errors.

**Blocked by:** [04](04-sensor-reconstruction.md)

**Status:** verified-complete — live views independently reconciled

**Lane:** core

**Verifier:** Generate range/BEV/point-cloud views, camera projections and semantic overlays live; independently reconcile displayed sample keys, coordinates and coverage against reconstruction artifacts.

## Acceptance criteria

- [x] Views include all available modalities and explicitly identify selected frames/sensors/returns.
- [x] Range-to-Cartesian and BEV rasterization report invalid, clipped and unobserved support separately.
- [x] At least one segmentation-labeled and one unlabeled example are inspected with coverage metadata.
- [x] Images and views reference independently validated geometry; visually plausible plots alone cannot pass.
- [x] Independently validate live Insula receipt, candidate/input/runtime identities, required assertions, output hashes and measured resources; missing or failed checks prohibit closure.
- [x] Publish a reviewable evidence summary with exact replay recipe, observed outcome and limitations; existing host tests or historical receipts alone do not close this ticket.

## Binding completion policy

[Program goal and evidence policy](program-goal.md) applies in full. Preparation may occur before blockers clear; candidate execution/promotion and completion require verified blockers. Scientific completion permits negative/inconclusive findings. Adoption requires the separately stated promotion rule.

Evidence: [M4 verification](../../../experiments/waymo-perception/research/m4-verified.json).
