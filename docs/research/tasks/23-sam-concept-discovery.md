# 23 — Evaluate SAM 3 concept discovery

**Goal / what to deliver:** Determine whether fixed concept prompts recover useful semantic support beyond the detector without uncontrolled taxonomy changes.

**Blocked by:** [17](17-sam-mask-refinement.md)

**Status:** conditional — not authorized for execution

**Lane:** conditional

**Verifier:** Live concept inference with a frozen phrase/exemplar mapping; independent native support, false-discovery and ambiguity scoring.

## Acceptance criteria

- [ ] Activate only after an explicit research decision; freeze ontology/prompts before evaluation.
- [ ] Report discovery separately from spatial refinement, with overlaps/unknown classes explicit.
- [ ] Unsupported concepts require audited additional labels or remain qualitative; report coverage and false discoveries.
- [ ] Independently validate live Insula receipt, candidate/input/runtime identities, required assertions, output hashes and measured resources; missing or failed checks prohibit closure.
- [ ] Publish a reviewable evidence summary with exact replay recipe, observed outcome and limitations; existing host tests or historical receipts alone do not close this ticket.

## Binding completion policy

[Program goal and evidence policy](program-goal.md) applies in full. Preparation may occur before blockers clear; candidate execution/promotion and completion require verified blockers. Scientific completion permits negative/inconclusive findings. Adoption requires the separately stated promotion rule.
