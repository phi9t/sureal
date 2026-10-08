# Verified R0 sensor-to-scene engineering foundation

R0 is verified complete for the acquired two-scene validation fixture. This is pipeline and geometry evidence, not a trained-model result or an official held-out benchmark reproduction.

## Evidence

M0 proved dedicated locked CPU-rootfs entry, synthetic computation/IO, actual mount/network boundaries and fail-closed behavior. M1 independently reconciled 143625 native rows from 34 files/17 families. M2 passed 11 analytic/manifold/boundary/covariance fixtures live. M3 reconstructed all 397 frames, 3970 sensor/return records and 71891534 positive finite range points; independent source reconciliation and scalar-coordinate checks passed, maximum sampled coordinate difference 1.5756285165480222e-11 m. M4 independently validated 131 artifacts spanning four labeled/unlabeled frames, 20 camera views and 40 LiDAR-return views.

M5 repeated native, geometry, mathematical-fixture and inspection stages under unchanged candidates and runtime. Every geometry NPZ and native manifest matches bytewise; view reports/artifacts also match. Geometry producer runtimes were 73.0504 and 71.3895 seconds, with 695752 and 683824 KiB peak RSS. Each full geometry output is approximately 6.70 GB. Timing and logs can vary without changing deterministic data artifacts.

Compact verification records: [M0](m0-verified.json), [M1](m1-verified.json), [M2](m2-verified.json), [M3](m3-verified.json), [M4](m4-verified.json), [M5](m5-verified.json). Each points to hashed retained receipts and large artifacts outside git. [Execution ledger](r0-execution-ledger.md) includes failures and corrections.

## Replay

From the isolated worktree, use fresh output directories:

```bash
python3 experiments/waymo-perception/verify-m0.py "$HOME/.cache/waystone/waymo-perception/insula/m0-fresh"
python3 experiments/waymo-perception/verify-native.py "$HOME/.cache/waystone/waymo-perception/insula/m1-fresh"
python3 experiments/waymo-perception/verify-geometry.py "$HOME/.cache/waystone/waymo-perception/insula/m2-fresh"
python3 experiments/waymo-perception/verify-reconstruction.py "$HOME/.cache/waystone/waymo-perception/insula/m3-fresh"
python3 experiments/waymo-perception/inspect-scene.py "$HOME/.cache/waystone/waymo-perception/insula/m4-fresh"
```

Recipes verify the retained M0 prerequisite and pinned source/runtime state; inspection uses the verified m3-live-b geometry mounted readonly. Rebuilding requires a fresh rootfs destination; build.sh refuses replacement. No GCS credentials are mounted into offline processing.

## Boundaries

TOP uses supplied pixel acquisition poses and vehicle label-reference pose. Other LiDARs are explicitly uncompensated. Camera overlays preserve supplied projections rather than independently reproducing rolling-shutter/moving-point camera projection. Missing labels, undefined semantic support and unresolved associations stay explicit. NLZ is metadata separate from physical encoder features. Generic radar fixtures are synthetic; the acquired Waymo release supplies no radar modality.

The next gates are scientific cohort/protocol selection, GPU runtime verification and TF-free evaluator parity. Independent detection/segmentation, SAM comparisons and forecasting findings remain unexecuted. No R0 result answers those scientific hypotheses.
