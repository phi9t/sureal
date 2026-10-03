# 27 — Specify and verify the next planning study

**Goal / what to deliver:** Define an evaluable planning hypothesis supported by forecasting findings and a verified TF-free dataset/runtime path.

**Blocked by:** [21](21-forecast-feature-study.md)

**Status:** conditional — not authorized for execution

**Lane:** conditional

**Verifier:** Primary-source metric/input audit and live pilot of the selected E2E or simulator path with independent trajectory/observation and evaluator fixtures.

## Acceptance criteria

- [ ] Activate after an explicit planning decision; offline E2E and closed-loop studies are separate contracts.
- [ ] Offline rater/ADE scoring has validated support/parity; closed-loop use declares dynamics/reactive agents/observation assumptions.
- [ ] TF-free ingestion/evaluation and live pilot pass before broader implementation; improved offline scores are not called closed-loop safety.
- [ ] Independently validate live Insula receipt, candidate/input/runtime identities, required assertions, output hashes and measured resources; missing or failed checks prohibit closure.
- [ ] Publish a reviewable evidence summary with exact replay recipe, observed outcome and limitations; existing host tests or historical receipts alone do not close this ticket.

## Binding completion policy

[Program goal and evidence policy](program-goal.md) applies in full. Preparation may occur before blockers clear; candidate execution/promotion and completion require verified blockers. Scientific completion permits negative/inconclusive findings. Adoption requires the separately stated promotion rule.
