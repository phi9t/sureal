# Expanded architecture fixed-batch results

All eight treatments are terminal. The independent live closure checks 384 stage receipts. Seven reached two consecutive sampled all-class native APH >= 0.8; the sparse transformer did not reach this gate by the 10,000-update cap.

| Treatment | Updates | Training seconds | Vehicle APH | Pedestrian APH | Sign APH | Cyclist APH | Result |
|---|---:|---:|---:|---:|---:|---:|---|
| grid_fine | 750 | 57.37 | 0.978169 | 0.998992 | 0.927627 | 0.999547 | sustained native overfit |
| grid_coarse | 750 | 48.80 | 0.986726 | 0.999121 | 0.926807 | 0.999561 | sustained native overfit |
| ragged_pillars | 750 | 51.27 | 0.998744 | 0.997880 | 0.927527 | 0.999431 | sustained native overfit |
| point_attention | 750 | 110.58 | 0.984122 | 0.998716 | 0.926812 | 0.997981 | sustained native overfit |
| point_mlp_control | 750 | 87.57 | 0.880378 | 0.996736 | 0.811483 | 0.998172 | sustained native overfit |
| range_fusion | 750 | 224.76 | 0.946316 | 0.997990 | 0.926328 | 0.995888 | sustained native overfit |
| zero_range_control | 750 | 223.68 | 0.999391 | 0.999123 | 0.926970 | 0.998910 | sustained native overfit |
| sparse_bev_transformer | 10000 | 1925.60 | 0.741925 | 0.990472 | 0.926840 | 0.998926 | failed to overfit by 10000 updates |

Successful treatments first pass in the sampled update interval (300, 500], with confirmation at 750. Sparse-transformer time-to-fit is right-censored at 10,000 updates / 1,925.60 training seconds. Time excludes native scoring and audit overhead and was measured under shared GPU contention; it is not a hardware throughput comparison.

These are one-frame, training-only engineering diagnostics with the historical eligible ROI GT contract. They do not establish held-out architecture gains. Range fusion and its zero-range control both fit; this does not demonstrate that range information improves generalization. The transformer negative result remains evidence for investigation, not a reason to discard transformers generally.

All eight expanded payloads now have verified HDFS archival, exact readback, live recovery and manifest admission, followed by local release (1,264 files / 830,511,030 bytes). Recovery locations and hashes are recorded in advanced-expanded20261002a-hdfs-retention-index.json. Sustained balanced16 fitting, official full-native-GT evaluation, and held-out research remain pending.

Evidence: advanced-expanded20261002a-results.json and advanced-closure-expanded20261002a-verified.json.
