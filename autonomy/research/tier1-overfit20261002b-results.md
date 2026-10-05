# Fixed-batch architecture and optimization sweep

The earlier study cycled over 16 frames. This tier uses one fixed training frame with 73 native eligible objects: 36 vehicles, 18 pedestrians, 14 signs and 5 cyclists. All ground truth is retained. No TensorFlow is used.

Acceptance is native LEVEL2 APH ≥ 0.80 for each class at two consecutive sampled checkpoints, including the terminal checkpoint. Reported fit intervals are sampled bounds, not exact crossing times. Training times are synchronized GPU execution times; shared GPU contention limits timing comparisons. No held-out or generalization claim is made.

| Treatment | First stable fit update interval | Confirmation update | Train seconds to confirmation | Terminal V / P / S / C APH | Result |
|---|---:|---:|---:|---|---|
| baseline | 300–500 | 750 | 133.6 | 0.972 / 0.999 / 0.927 / 0.999 | Pass |
| deep_pfn | 300–500 | 750 | 150.6 | 0.985 / 0.999 / 0.928 / 0.999 | Pass |
| context_pfn | 300–500 | 750 | 60.6 | 0.998 / 0.983 / 0.927 / 0.999 | Pass |
| masked_pfn | 300–500 | 750 | 53.5 | 0.999 / 0.999 / 0.927 / 0.999 | Pass |
| residual_bev | 300–500 | 750 | 65.6 | 0.999 / 0.998 / 0.927 / 1.000 | Pass |
| window_bev | 300–500 | 750 | 64.9 | 0.999 / 0.999 / 0.928 / 0.999 | Pass |
| coarse_mlp | 300–500 | 750 | 146.5 | 0.998 / 0.998 / 0.926 / 0.998 | Pass |
| retain64 | 300–500 | 750 | 173.6 | 0.976 / 0.999 / 0.927 / 0.999 | Pass |
| full_bn | 1500–2000 | 3000 | 218.7 | 0.999 / 0.998 / 0.925 / 0.998 | Pass |
| point_ln | 300–500 | 750 | 103.3 | 0.981 / 0.998 / 0.928 / 0.998 | Pass |
| no_norm | 4000–6000 | 8000 | 434.8 | 0.830 / 0.910 / 0.902 / 0.984 | Pass |
| foreground_prior | 500–750 | 1000 | 72.6 | 0.999 / 0.999 / 0.927 / 0.999 | Pass |
| lr3e4 | 300–500 | 750 | 54.3 | 0.934 / 0.990 / 0.927 / 0.997 | Pass |
| no_clip | 2000–3000 | 4000 | 273.8 | 0.998 / 0.998 / 0.926 / 0.999 | Pass |
| class_balanced_focal | 300–500 | 750 | 53.3 | 0.999 / 0.999 / 0.928 / 0.999 | Pass |

The `all_pillars` treatment is an exact observation-equivalence control: the 20,000-pillar cap does not bind on this frame. Live GPU initial and terminal head equivalence establishes the same inference outcome; it is not an independently trained winner.

A versioned yaw decoder correction was necessary: normalize angles before applying the direction-bin branch. Rescoring identical saved 2,000-update heads raised pedestrian APH from 0.759 to 1.000 and sign APH from 0.714 to 0.928 without changing AP or training. The legacy code and evidence remain preserved.

The baseline already has sufficient capacity to fit this batch. Its first native pass was at 500 updates and confirmation at 750; its retained trajectory ended at 4,000 because the decoder issue was diagnosed after training. Initial negative focal loss was about 1,267 times positive focal loss. These results motivate foreground-loss and inference-normalization diagnostics; they do not establish parameter count as the cause of the 16-frame learning difficulty.

Sign AP is not expected to reach one under this fixed decoder: NMS suppresses one overlapping pair, giving 13/14 ≈ 0.929. No ground-truth object is removed.

Verification includes independent literal loss coverage for every sampled checkpoint, score-first decode/NMS and physical metadata audits, native metric replay and export reread, exact complete model/Adam/RNG/head trajectory replay, immutable source/artifact hashing with declared release ledgers, resource admission, and final live Insula closure.

Evidence: [closed comparison](tier1-overfit20261002b-closed.json), [full curves](tier1-overfit20261002b-results.json), [live final closure](tier1-closure-live-final-v4-verified.json), [terminal cap control](tier1-terminal-cap-equivalence-verified.json).
