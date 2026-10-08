# 06 — M5: close the reproducible sensor-to-scene tracer

**Goal / what to deliver:** Demonstrate two complete, independently validated runs of the same locked two-scene processing pipeline.

**Blocked by:** [02](02-native-replay.md), [03](03-geometry-math.md), [04](04-sensor-reconstruction.md), [05](05-inspection-views.md)

**Status:** verified-complete — repeated live native, math, geometry and inspection stages reconciled

**Lane:** core

**Verifier:** Execute two fresh full-cohort live runs and compare independent manifests, geometry identities, coverage summaries and output hashes or declared numeric tolerances.

## Acceptance criteria

- [x] Both receipts identify the same runtime, code and input cohort.
- [x] All required invariants and artifact checks pass on both runs.
- [x] Exact fields match bytewise; floating artifacts satisfy declared tolerances; nondeterminism is explained.
- [x] Resource use and unresolved timing/association limitations are published; no learned-model performance is claimed.
- [x] Independently validate live Insula receipt, candidate/input/runtime identities, required assertions, output hashes and measured resources; missing or failed checks prohibit closure.
- [x] Publish a reviewable evidence summary with exact replay recipe, observed outcome and limitations; existing host tests or historical receipts alone do not close this ticket.

## Binding completion policy

[Program goal and evidence policy](program-goal.md) applies in full. Preparation may occur before blockers clear; candidate execution/promotion and completion require verified blockers. Scientific completion permits negative/inconclusive findings. Adoption requires the separately stated promotion rule.

Evidence: [M5 verification](../../../experiments/waymo-perception/research/m5-verified.json).
