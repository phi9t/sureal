# Prediction–target association experiments

Status: specified / not runnable. No association treatment has been implemented or trained by this documentation update. Historical architecture, normalization and optimization results keep their original targets and source pins.

Goal: eliminate unassigned eligible objects through distinct prediction ownership, then measure whether better association improves native detection fit and time-to-fit. [Design](../../../docs/superpowers/specs/2026-10-03-prediction-target-association-design.md), [implementation plan](../../../docs/superpowers/plans/2026-10-03-prediction-target-association.md), [ticket41](../../../docs/research/tasks/41-prediction-target-association.md), [parent34](../../../docs/research/tasks/34-rare-class-learning-diagnosis.md).

## Initial experiment matrix

| Treatment | Status | Goal | First acceptance |
| --- | --- | --- | --- |
| A0 `legacy` | planned reference replay | Reproduce the unchanged matcher and current fitting behavior | Exact16-frame legacy targets and30 uncovered IDs; independently admitted native curves. |
| A1 `coverage_bev` | planned | Fix global ownership while keeping nearest-BEV cost | Full1,053-object coverage, independent target/oracle checks, then fixed-batch fit. |
| A2 `coverage_3d` | planned | Improve matches using center-Z,size androtated3Doverlap | A1 correctness gates plus independent geometry/cost replay and fixed-batch fit. |
| A3 `coverage_prediction` | planned | Adapt reservations to learned class/box quality | A2 gates plus detached cost, exact per-update assignment/resume replay and fixed-batch fit. |

Each treatment changes reservations on the same prediction-independent candidate graph; unreserved legacy positives, negative/ignore rules, current losses and decoder stay fixed. Positive-count and normalizer changes are measured outcomes. Initial weights, seed17, baseline GN8/PFN-BN, packing, anchors and Adam/clip are matched. Manifest identity includes all treatment parameters, graph/targets, ordered native frames, sources, runtime locks and decoder version.

Conditional follow-ups: positive quota, object-balanced positive loss, NMS and query heads. They are absent from this executable matrix until separately specified and admitted. Planned controls must never appear as trained successes in the generated tracker.

## Proposed operator interface

The following commands are the interface to implement; they do not exist yet. Do not send these treatments through the existing architecture runner, which does not support association variants.

```bash
python experiments/waymo-perception/association/run.py list
python experiments/waymo-perception/association/run.py prepare --run-id UNIQUEID
python experiments/waymo-perception/association/run.py run --run-id UNIQUEID --treatment coverage_bev --tier fixed-batch
python experiments/waymo-perception/association/run.py run --run-id UNIQUEID --treatment coverage_bev --tier balanced16
python experiments/waymo-perception/association/run.py verify --run-id UNIQUEID
```

`prepare` freezes all four recipes, source/runtime/input hashes and prediction-independent graphs. It produces independently admitted target/oracle receipts before any optimizer launch. `run` acquires the existing architecture GPU lock, preserves the namespace and refuses changed hashes; balanced16 requires that treatment's admitted fixed-batch fit. `verify` re-admits retained evidence without training. Resume must be explicit, source-identical and replay-checked; it must not overwrite partial outputs.

Use the existing admitted cache at`~/.cache/waystone/waymo-perception`; an optional global`--cache-root PATH` selects another already admitted cache. This runner must not download data, authenticate, alter runtime roots or implicitly change budgets. Run IDs follow the existing1–64 character letters/digits/underscore/hyphen rule, starting with a letter or digit.

## Live proof and acceptance

Every implementation milestone needs locked live Insula execution plus separate independent admission. The full design defines red fixtures, exhaustive small-graph oracles, real524,288-slot replay, costs, gradients, A3 restart and suppression probes.

- Target gate: all1,053 eligible balanced16 objects covered with unique reservations; unchanged eligible IDs and1,279 native evaluation GT. Report zeros/poor overlaps and encoded residuals, not just a coverage percentage.
- Annotation-only oracle: reproduce ROI APH0.917384/0.947955/0.868421/0.918919 within1e-6. It bypasses NMS and establishes coverage only.
- Fixed-batch gate: the admitted 73-object/all-class frame; native LEVEL2 APH >=0.8 for every class at two consecutive scored samples including terminal, within 10,000 updates or 7,200 synchronized training seconds, with the 2,000-update primary ceiling reported. A lone passing time-censored terminal sample is unconfirmed.
- Balanced16 gate: same per-class sustained threshold within32,000 updates or7,200 synchronized training seconds. Preserve the fixed checkpoint grid and confirmation rule in the design. A finite negative is a diagnostic; runtime/admission failure remains unresolved.
- Report bracketed optimizer updates, per-frame exposure and training time, with solver/scoring/audit/HDFS overhead separate. Trace assignment,input support,localization,score,top-K andNMS for the original30 missing objects and new misses.

Caps remain scientific 15GiB unique-inode payload, raw 2GiB, allocated GPU 8GiB, process RSS 16GiB, reserve 2GiB per active case. Reuse legacy arrays read-only; retain sparse reservation overrides and per-update owner vectors/digests, rebuilding complete targets during replay. Native scoring timeout is 14,400 seconds, host 14,700 seconds. HDFS upload/exact readback/independent live recovery precede declared local release; a retention failure keeps local evidence and blocks new budget-exceeding work.

## Tracking and research journal

During implementation, add a separately versioned study to the existing experiment registry only after its runtime/source/input contract can be frozen. Register A0–A3 with explicit expected gates; status begins planned, not runnable/admitted. Do not hand-edit generated`research/experiments.json`, `experiment-tracker.md` or append-only journal files.

Use the existing tracker CLI for later hypothesis/observation/decision/follow-up entries. Each entry binds its treatment/configuration, frozen parent receipt, native frame/GT scope and immutable evidence paths. Record covered IDs, positive counts, cost/match distributions, class curves, fit brackets, stop reason and HDFS recovery receipt. A host note or this specification is not an Insula receipt. No journal entry or tracker refresh is performed by this documentation-only update.

## Research interpretation

The study compares ownership, geometry and learned match quality, not larger-versus-smaller backbones. [Primary papers and first-principles constraints](../../../docs/superpowers/specs/2026-10-03-prediction-target-association-design.md#public-research-and-limits-of-transfer) explain why adaptive-positive selection and continuous transport need explicit final coverage checks. A3's phase coverage and assignment churn must accompany a convergence claim. No result here establishes held-out, segmentation, camera, forecasting or planning benefit.
