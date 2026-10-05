# Native camera projection residual investigation

The unchanged double-precision Waymo C++ camera core projects all 157,870 native
TOP points in the engineering frame. All 21,234 supplied FRONT correspondences
have valid positive forward depth. L2 residual median/p95/max are
1.294/2.790/3.721 pixels. This is execution evidence, not exact pixel parity.

## Controlled observations

Live offline Insula receipts:
`camera-convention-diagnostic-verified.json` and
`camera-residual-structure-verified.json`. All retained artifacts were rehashed.

- Global shutter worsens p95 to 4.855 pixels.
- Converting global angular velocity to vehicle-frame components changes p95 by
  only approximately 0.005 pixels, insufficient to explain the discrepancy.
- Flooring recomputed coordinates reproduces both supplied integers for only
  4,875/21,234 slots. 16,359 slots lie outside the positive unit-square residual
  expected from integer flooring alone.
- Residual p95 remains approximately 2.71–2.84 pixels across forward-depth bins
  0–10, 10–20, 20–40, and 40–80 meters. Empty bins stay empty, not zero-error.
- Horizontal image quarters have p95 approximately 2.68–2.93 pixels. No fitted
  correction has been applied.

## Upstream explanation and limits

An [upstream discussion](https://github.com/waymo-research/waymo-open-dataset/issues/146#issuecomment-621376464)
attributes remaining multi-pixel discrepancies to rounding during range-image
construction. Earlier comments describe integer projection coordinates as
floored values and the direct camera implementation as double precision.
The selected API comments and retrieval response hash are retained in
`camera-projection-upstream-rounding-source.json`.

**Inference:** our residual scale is consistent with that explanation, and our
controlled tests disfavor global shutter, angular convention, and final integer
rounding as sufficient explanations. This does not isolate each source of error
in this frame. Do not alter native angular components or fit a pixel correction
merely to increase agreement.

## Consequence for research contracts

Use the supplied point-to-camera correspondence for native mask incidence;
retain its original measurement identity and its two camera slots. Recomputed
geometry supplies a separately identified approximate depth/projection estimate.
Do not describe the two as exact equivalents or treat valid projection/positive
depth as an occlusion certificate. Actor-motion compensation remains unavailable
in this static-world diagnostic.

The visibility-qualified semantic-support gate stays open. Its acceptance must
account for range-image quantization, mask boundary uncertainty, explicit
occlusion tests, and missing evidence. Validation should span multiple training
frames and cameras before any threshold is frozen; held-out data must not tune
these decisions.
