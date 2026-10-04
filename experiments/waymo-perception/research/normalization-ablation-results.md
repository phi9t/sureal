# Normalization experiment results

All four treatments used the same initialized convolution weights, training frame, full17 eligible targets, losses, seed17, Adam1e-4 and2000-update budget. Each11-checkpoint native scoring curve has separate live Insula geometry/export/native-metric audits. New treatments also have independent loss/timing and exact initial/final checkpoint replay.

| Treatment | Final mean LEVEL2 APH | First sampled mean ≥0.8 | Training-time crossing bracket | Remains ≥0.8 at later samples |
| --- | ---: | --- | --- | --- |
| Original BatchNorm | 0.737530 | (1000,1500] updates | (72.922,107.302] seconds | No |
| BEV GroupNorm8; pillar BatchNorm | 0.878552 | (300,500] | (19.835,32.812] seconds | Yes |
| BEV GroupNorm8; pointwise channel LayerNorm | 0.856792 | (200,300] | (12.942,19.245] seconds | Yes |
| No normalization, secondary decoder | 0.621318 | Not reached by2000 | 94.963 seconds for2000 updates | No pass |

Training wall time is synchronized cumulative step time, including transfers/checks; excludes native scoring/audit overhead. Some CPU evaluation overlapped other GPU runs, so timings are engineering observations rather than exclusive hardware benchmarks. Threshold crossings are checkpoint brackets, not exact crossing times.

Final vehicle/pedestrian/sign APH: BN0.998079/0.988051/0.226459; GN0.999841/0.999740/0.636074; GN+LN0.999583/0.999144/0.571648; no-norm0.675154/0.976562/0.212239. All variants fail the strict per-populated-class≥0.8 verifier. No cyclists exist in this fixture; three sign targets have no positive anchor. Preserve allGT and address assignment/localization before declaring architecture admission.

No-norm primary export failed because the original decoder exponentiated unused background boxes before applying score selection. Preserve that failure. A separately specified score-before-decode investigation enabled scoring without clipping dimensions or selecting byGT. It reproduced every field of all33 normalized checkpoint proposal exports exactly. No-norm secondary predictions passed independent literal geometry, protobuf and native metric replay for all11 checkpoints.

Decision: keep GN backbone and GN+pointwise LN as candidates. GN has higher final quality; GN+LN reaches the sampled mean threshold faster. This demonstrates BN is unnecessary for this fixed-batch detector, but does not establish heldout benefit or the best normalization for larger training batches. No-norm is worse with the unchanged bias-free architecture and optimizer; it is not a universal rejection of normalization-free models.

Machine-readable results and source/audit receipt hashes: [normalization-ablation-result.json](normalization-ablation-result.json). Original protocols and failures remain unchanged; task10 and the overall program remain open.
