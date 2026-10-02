# 08 — Verify a locked GPU model runtime

**Goal / what to deliver:** Prove the intended Torch/JAX GPU execution path works within Insula before any model milestone.

**Blocked by:** [01](01-insula-runtime.md)

**Status:** verified-complete — live B200 computation, independent numerical checks, isolation and failure injections passed

**Lane:** core

**Verifier:** Live device computation and representative forward/backward with independently checked known outputs, finite gradients, runtime identity and isolation probes.

## Acceptance criteria

- [x] Actual GPU computation passes, rather than only device enumeration.
- [x] Code, package closure, CUDA/device and checkpoint identities are recorded; TensorFlow is absent.
- [x] Isolation and fail-closed checks pass with required device mounts.
- [x] Measured memory and latency are recorded; this closes only runtime readiness, not model quality.
- [x] Independently validate live Insula receipt, candidate/input/runtime identities, required assertions, output hashes and measured resources; missing or failed checks prohibit closure.
- [x] Publish a reviewable evidence summary with exact replay recipe, observed outcome and limitations; existing host tests or historical receipts alone do not close this ticket.

## Binding completion policy

[Program goal and evidence policy](program-goal.md) applies in full. Preparation may occur before blockers clear; candidate execution/promotion and completion require verified blockers. Scientific completion permits negative/inconclusive findings. Adoption requires the separately stated promotion rule.

## Evidence and replay

[GPU runtime evidence](../../../experiments/waymo-perception/research/gpu-runtime-verified.json) links the independently reconciled computation and isolation receipts. Run `python3 experiments/waymo-perception/gpu/verify-live.py <fresh-output-directory>` followed by `python3 experiments/waymo-perception/gpu/verify-isolation.py <fresh-output-directory>`; the isolation runner currently selects candidate `gpu-live-d`, whose identity it verifies. Use that recorded candidate for exact replay or update the selection explicitly when validating a new candidate. The image locks Torch 2.9.1+cu130, Python 3.12, CUDA 13 wheel dependencies, and the rootfs; driver inputs are separately hashed. Analytic matrix outputs and both gradients are independently derived in a separate live NumPy invocation. Private HOME, absent credential environment, offline host-listener rejection, read-only source/code/root, writable bounded output and single physical GPU exposure passed. Three numerical artifact mutations were rejected. No trained checkpoint was used; this closes runtime readiness only. Multi-GPU and custom sparse kernels remain outside this gate.
