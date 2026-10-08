# 01 — M0: prove the dedicated Insula runtime

**Goal / what to deliver:** Establish a locked CPU Insula that genuinely executes isolated computation and IO.

**Blocked by:** None — first execution frontier

**Status:** verified-complete — current M0 candidate and independent receipt validated

**Lane:** core

**Verifier:** Enter the actual rootfs twice; reopen synthetic NumPy, Parquet and image artifacts with an independent checker; test a reachable host listener before checking network isolation; execute mount and failure-injection probes.

## Acceptance criteria

- [x] Runtime-content identity and interpreter/dependency paths match the lock, with no host fallback.
- [x] Both live entries reproduce expected synthetic values; inputs are readonly, output writable, HOME private and unintended host paths/credentials absent.
- [x] Host listener is reachable outside and unreachable inside the offline namespace.
- [x] Wrong lock, missing rootfs, failed assertion and failed child command return nonzero and cannot promote outputs.
- [x] Independently validate live Insula receipt, candidate/input/runtime identities, required assertions, output hashes and measured resources; missing or failed checks prohibit closure.
- [x] Publish a reviewable evidence summary with exact replay recipe, observed outcome and limitations; existing host tests or historical receipts alone do not close this ticket.

## Binding completion policy

[Program goal and evidence policy](program-goal.md) applies in full. Preparation may occur before blockers clear; candidate execution/promotion and completion require verified blockers. Scientific completion permits negative/inconclusive findings. Adoption requires the separately stated promotion rule.

Progress evidence: [M0 execution ledger](../../../experiments/waymo-perception/research/m0-execution-ledger.md).
