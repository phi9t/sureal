# Cohort pilot implementation plan

Spec: ../specs/2026-10-02-perception-cohort-pilot-design.md

- [x] Protocol RED→GREEN: duplicate/heldout/missing-class rejection, all-class quality gate.
- [ ] Live Insula source/GT/anchor coverage and protocol admission.
- [ ] Frozen-source baseline and residual-BEV 16-frame training, all4 checkpoint losses/heads and resources.
- [ ] Independent initial/final model replay, optimizer validation, literal loss reconstruction, literal proposal/GT/export/native score audits.
- [ ] Record fit gate and first/sustained timing. If negative, preserve results and defer two-scene pilot with concrete diagnosis. If positive, independently admit segment-disjoint whole-scene loading, restart and heldout pilot before full-dataset planning.

Ruling: user explicitly requested trying the readiness pilot despite the prior single-frame sign failure. This permits diagnostic16-frame execution; it does not waive the per-class fitting gate for downstream progression. Preserve original files and historical evidence, use new cohort namespaces, serialize GPU via the public runner lock, retain all GT. The fixed four-checkpoint grid bounds storage; intermediate checkpoint timing is bracketed.

Coverage record: balanced16 label-only selection improved cyclists3→34 observations and22 unique tracks. Native box sources and literal anchor assignments independently replayed; all34 cyclists anchor-covered. Original random16 trained and checkpoint/literal loss admissions passed; quality scoring remains required. Review strengthened coverage to independent covered identities and fit gates to mandatory replay receipts. Raw GCS selected reconstruction produced all16 physical frames; review requires frozen-helper independent re-admission before consuming those outputs. FRONT preview extraction and interactive explorer added under the user’s explicit request. All native GT, including29 uncovered signs and1 uncovered pedestrian in the balanced fixture, remain visible and evaluable.

### 2026-10-02 joint inspection and balanced fitting launch

Two selected scenes rendered in live CPU Insula with frozen helper/worker hashes. All supplied FRONT correspondences reconciled by native (LiDAR, return, row, column, slot) identity, with all-five-LiDAR BEV and native box overlays. Published static research illustrations to https://phi9t.github.io/sureal/waymo-scene-explorer/ (Pages commit 6bad91d). Projection reuse does not establish independent rolling-shutter correctness.

Original random16 baseline 2000-step native APH: vehicle .222358, pedestrian .064371, sign .003351, cyclist 0; all-class fit failed. Balanced16 matched baseline/residual-BEV study uses three checkpoints to respect the 15 GiB retention cap. Launch entry: `python experiments/waymo-perception/cohort/launch_balanced_study.py --run-id balanced20261002a`. Sequential GPU candidates launch only after all16 cache producer/reference admissions, then exact checkpoint/loss replays, then native proposal/export/metric audits. Status: `experiments/waymo-perception/research/balanced-study-balanced20261002a.json`. No full-dataset readiness claim.

### Balanced fitting continuation

Baseline `balanced20261002a`: 2000 updates completed; initial/final mean loss 1564.661722/1.073229872; synchronized optimization 138.047304 s. Exact all16 initial/final head and Adam-state replay passed; all48 literal losses passed. Residual-BEV launch initially blocked by conservative 1536 MiB reservation. Measured baseline artifact footprint justified 1400 MiB reservation without changing the 15 GiB cap, and retry `balanced20261002b` completed: final mean loss 1.266910361; synchronized optimization130.447545 s. Exact checkpoint/Adam replay and all48 literal losses passed. Final scientific retention14.863838 GiB. Matched native scoring and independent evaluator reruns underway; no all-class fit/readiness claim. Recovery status: `experiments/waymo-perception/research/balanced-study-recovery-20261002.json`.

Closeout: both balanced candidates completed with strict matched-input admission, exact checkpoint/Adam replay,48 literal losses each, and all three native proposal/export/evaluator audits. All-class fitting gates false for both. Authoritative result: `experiments/waymo-perception/research/balanced-study-recovery-20261002.json`; narrative: `research/balanced16-fitting-results.md`. Superseded partial serial scoring artifacts retained. No larger training launched; ticket34 specifies the next controlled diagnosis.
