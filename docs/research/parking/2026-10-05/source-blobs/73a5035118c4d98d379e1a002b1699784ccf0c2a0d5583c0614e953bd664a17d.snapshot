# 04 — M3: reconstruct real calibrated sensors

**Goal / what to deliver:** Recover real LiDAR points with camera correspondences and semantics while preserving measurement identity and timing.

**Blocked by:** [02](02-native-replay.md), [03](03-geometry-math.md)

**Status:** verified-complete — full-cohort reconstruction independently checked live

**Lane:** core

**Verifier:** Live reconstruction of both scenes; independent selected-ray analytic reconstruction and conservation checks across sensors, returns, range pixels, projection arrays and semantic masks.

## Acceptance criteria

- [x] Every emitted point retains frame, laser, return, row and column identity; counts reconcile to valid ranges.
- [x] Calibration and TOP pixel poses use the documented frame reference; camera exposure/rolling-shutter limitations are recorded.
- [x] Labels and camera correspondences remain aligned after filtering; unsupported labels are masked.
- [x] Reference fixtures meet preregistered numerical tolerances; incorrect extrinsics/order/return fixtures are rejected.
- [x] Independently validate live Insula receipt, candidate/input/runtime identities, required assertions, output hashes and measured resources; missing or failed checks prohibit closure.
- [x] Publish a reviewable evidence summary with exact replay recipe, observed outcome and limitations; existing host tests or historical receipts alone do not close this ticket.

## Binding completion policy

[Program goal and evidence policy](program-goal.md) applies in full. Preparation may occur before blockers clear; candidate execution/promotion and completion require verified blockers. Scientific completion permits negative/inconclusive findings. Adoption requires the separately stated promotion rule.

Evidence: [M3 verification](../../../experiments/waymo-perception/research/m3-verified.json); timing/projection limitations are recorded in the R0 execution ledger.
