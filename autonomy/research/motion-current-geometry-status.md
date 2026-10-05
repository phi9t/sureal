# Motion current-reference geometry gate

Separate live Insula producer and native scalar auditor reconstruct every positive return in two engineering pilots. The auditor reads native observation-only protobufs, decodes compressed tensors independently, and computes world→current-vehicle points directly, without producer metadata or transform helpers. Both returns and all five lasers remain intact, without ROI or point caps. TOP uses first-return pixel poses for both returns. Physical features contain range, intensity and elongation; NLZ is excluded.

| Pilot | Returns | Points | Maximum coordinate discrepancy (m) |
|---|---:|---:|---:|
| Training | 110 | 1,902,370 | 1.01608e-12 |
| Validation | 110 | 1,820,913 | 2.35012e-12 |

Absolute coordinate tolerance was declared as1e-6m. Every row/column key and all three float32 physical features match the native source. Analytic polar-column, SE3 forward/inverse and ordered RPY fixtures pass. Eight actual serialized corruptions fail: shifted/nonfinite XYZ, wrong pixel key, changed physical feature, extra feature channel, truncated/extra XYZ bytes and missing return. Disabling coordinate comparison admitted shifted XYZ and made the refusal fixture fail (live RED); enabling it refused all eight (live GREEN).

The [producer receipt](motion-current-geometry-producer-verified.json), [RED receipt](motion-current-geometry-audit-red-verified.json) and [independent audit receipt](motion-current-geometry-audit-live-verified.json) pin executed sources, native/runtime inputs and output hashes. Source fixtures relocate only the inventory include path. Native audit invocationsv1/v2 failed compilation and remain retained; onlyv3 reached the contract tests and is admitted.

This clears the two-pilot geometry preparation gate. Ticket19 remains open for full evaluator/cohort admission; scientific train/development/held-out protocol and forecasting baseline/sensor comparisons remain open. Frame-index historical access does not certify exact subscan wall-clock causality. Camera observations remain codebook features, not RGB.
