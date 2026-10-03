# Experiment tracker

fixed all-class training batch; no heldout, segmentation or full-dataset completion claim

| Experiment | Stage | Confirmation update | Train seconds to confirmation | Worst terminal APH |
|---|---|---:|---:|---:|
| overfit20261002b/baseline | verified_overfit | 750 | 133.6 | 0.927 |
| overfit20261002b/deep_pfn | verified_overfit | 750 | 150.6 | 0.928 |
| overfit20261002b/context_pfn | verified_overfit | 750 | 60.6 | 0.927 |
| overfit20261002b/masked_pfn | verified_overfit | 750 | 53.5 | 0.927 |
| overfit20261002b/residual_bev | verified_overfit | 750 | 65.6 | 0.927 |
| overfit20261002b/window_bev | verified_overfit | 750 | 64.9 | 0.928 |
| overfit20261002b/coarse_mlp | verified_overfit | 750 | 146.5 | 0.926 |
| overfit20261002b/retain64 | verified_overfit | 750 | 173.6 | 0.927 |
| overfit20261002b/all_pillars | verified_equivalence_control | — | — | — |
| overfit20261002b/full_bn | verified_overfit | 3000 | 218.7 | 0.925 |
| overfit20261002b/point_ln | verified_overfit | 750 | 103.3 | 0.928 |
| overfit20261002b/no_norm | verified_overfit | 8000 | 434.8 | 0.830 |
| overfit20261002b/foreground_prior | verified_overfit | 1000 | 72.6 | 0.927 |
| overfit20261002b/lr3e4 | verified_overfit | 750 | 54.3 | 0.927 |
| overfit20261002b/no_clip | verified_overfit | 4000 | 273.8 | 0.926 |
| overfit20261002b/class_balanced_focal | verified_overfit | 750 | 53.3 | 0.928 |
| expanded20261002a/grid_fine | native_fit_pending_closure | 750 | 57.4 | 0.928 |
| expanded20261002a/grid_coarse | native_fit_pending_closure | 750 | 48.8 | 0.927 |
| expanded20261002a/ragged_pillars | native_fit_pending_closure | 750 | 51.3 | 0.928 |
| expanded20261002a/point_attention | native_fit_pending_closure | 750 | 110.6 | 0.927 |
| expanded20261002a/point_mlp_control | native_fit_pending_closure | 750 | 87.6 | 0.811 |
| expanded20261002a/range_fusion | native_fit_pending_closure | 750 | 224.8 | 0.926 |
| expanded20261002a/zero_range_control | native_fit_pending_closure | 750 | 223.7 | 0.927 |
| expanded20261002a/sparse_bev_transformer | running_or_verifying | — | — | 0.766 |

Each row’s goal, complete recipe, verifier contract and acceptance criteria are in [experiments.json](experiments.json). Definitions are in [experiment-registry.json](experiment-registry.json). Notes are in [research-journal.md](research-journal.md).

Refresh: `python experiments/waymo-perception/tracking/cli.py refresh`
Follow active runs: `python experiments/waymo-perception/tracking/cli.py watch`
