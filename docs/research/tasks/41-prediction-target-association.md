# 41 — Prediction–target association and supervision coverage

Status: 41.1 independently live-admitted; 41.2 implementation next. Operator not runnable. No optimizer updates or A0–A3 fitting runs yet.

Goal: give every eligible object distinct, geometrically plausible prediction responsibility and establish whether ownership, 3D geometry or prediction-aware association improves native detection fitting and time-to-fit.

Parent: [34 — rare-class diagnosis](34-rare-class-learning-diagnosis.md). Dependencies: existing live runtime/evaluation gates 01/08/09, independently audited cohort/fixed-batch fixtures from 33/35, and this study's frozen protocol under ticket 07 plus runtime and retention admission. This does not require scientific completion of ticket 10 to diagnose its baseline. A balanced16 case additionally requires that treatment's fixed-batch fitting pass.

Design: [association specification](../../superpowers/specs/2026-10-03-prediction-target-association-design.md). Plan: [41.1–41.6 implementation tasks](../../superpowers/plans/2026-10-03-prediction-target-association.md). Experiments: [operator handbook](../../../experiments/waymo-perception/research/prediction-target-association-study.md).

## Evidence motivating the work

In balanced16, 29 eligible signs and one pedestrian have no positive assignment. Independent replay establishes 28 strict-overlap conflicts and two ties, all with positive maximum overlap; 28 conflicts are within the same class. The annotation-only sign APH control is 0.759399 for covered targets and 0.868421 for all eligible ROI objects against unchanged full native GT. These are supervision diagnostics, not model/NMS results or an unconstrained prediction ceiling. See [coverage report](../../../experiments/waymo-perception/research/balanced16-coverage-oracle-status.md).

## Work packages and verifiers

| Subticket | Clear goal | Mandatory live verifier | Acceptance |
| --- | --- | --- | --- |
| 41.1 Contract/runtime | Freeze a reproducible association comparison | CPU Insula contract fixtures and separate source/input/runtime/hash admission; new M0 if the solver root changes | Exact baseline, frames, recipes, budgets and independent solver identity; no active-root mutation. |
| 41.2 Ownership | Implement globally distinct coverage using existing BEV cost | Exhaustive tiny-graph oracle; independently rebuilt 16 full grids, owners, residuals and directions; annotation-only native oracle | Zero uncovered among 1,053 eligible GT, unique reservations, preserved unreserved legacy labels and all 1,279 native GT; explicit bounded-graph failure. |
| 41.3 Geometry/quality | Implement independently testable 3D and detached learned costs | Analytic rotation, height, zero-IoU and cost fixtures; actual-frame CUDA forward/backward; independent loss, gradient and target audits | Exact specified A2/A3 costs, warm-up and ownership; no GT feature leak or hidden loss/decoder change. |
| 41.4 First-tier fit | Test A0–A3 on the admitted all-class frame and measure learning cost | Complete native curves, exact model/Adam/RNG/head/assignment restart replay and class-complete metric admission | Every class LEVEL2 APH >=0.8 at consecutive samples including terminal within 10,000 updates or 7,200 step seconds, or an admitted finite negative; no cohort promotion for a failed case. |
| 41.5 Cohort signal | Test admitted cases on balanced16 and distinguish remaining failures | Independent full-GT native scoring, per-object support/score/top-K/NMS traces and complete trajectory replay | Same sustained all-class gate within 32,000 updates or 7,200 step seconds; honest time/update censoring, no weaker gate substitution. |
| 41.6 Tracking/retention | Make results inspectable, resumable and durably recoverable | Live operator, registry projection and journal tests; actual HDFS upload/readback and independent Insula recovery; whole-study admission | Immutable treatment/evidence identity, exact retained results, bounded local storage and an evidence-backed decision table. |

## Experiment treatments

- A0 `legacy`: matched unchanged reference.
- A1 `coverage_bev`: global reservations, current nearest-BEV cost; retain legacy positives on unreserved slots.
- A2 `coverage_3d`: shared graph/reservation policy with encoded center/size and rotated 3D overlap cost.
- A3 `coverage_prediction`: A2 warm-up, then detached current class/box/direction/3D-overlap costs with exact assignment replay.

Losses, decoder, backbone, initial weights, optimizer and eligibility stay fixed across A0–A3 except the named matching treatment. A0 retains its original matcher; the shared candidate graph applies to A1–A3. Report changed positive counts and background normalizers as treatment effects. Quota, object normalization, NMS and query-head follow-ups require separately frozen controls and remain conditional.

## Acceptance and decision

Close the engineering study only when all planned stages/cases have independently admitted outcomes or explicitly scoped conditional non-execution, real-target/oracle checks pass, fixed/cohort curves and failure attribution are retained, HDFS recovery is verified and a matched decision is recorded. Runtime, verification and resource failures remain unresolved implementation outcomes; a finite fit failure is useful research evidence.

An improvement candidate must pass both fixed-batch and balanced16 all-class native gates, preserving full GT, source identities and unchanged resource caps. Coverage alone does not pass training. An admitted study with a negative result closes its diagnostic question without promoting a model. Held-out benefit, scientific model adoption, segmentation, camera, forecasting and planning remain open.

Resources: the existing single-GPU lock; allocated GPU 8GiB, RSS 16GiB, raw 2GiB, scientific 15GiB unique-inode payload, reserve 2GiB per active case. Scoring 14,400s / host 14,700s is independent of 7,200s training. Local release requires upload, exact readback and independent live HDFS recovery; no historical deletion or auth mutation.

## Execution checkpoint — 2026-10-03

41.1 adds the isolated `association/contract.py` protocol and 31 live CPU
fixtures, including loss-equation drift rejection. Both original locked roots
lack SciPy. Separate hash-locked CPU/training images and exported roots were
created without mutating the original roots; SciPy 1.18.1 retains NumPy 2.5.3.

The separate CPU verifier reopens actual numeric/Parquet/image artifacts,
checks isolation, independently enumerates tiny solver optima, and rehashes the
exact 16-frame inputs: 1,053 eligible, all 1,279 native GT, and the fixed frame's
73 eligible objects. Current contract tests pass 31/31 in live Insula.
These are runtime/engineering checks, not model fitting or native oracle results.

The training-root M0 attempt refused the held architecture-experiments lock
before GPU launch. The existing sustained-controller run remains active and
unchanged. The concrete manifest at
`~/.cache/waystone/waymo-perception/insula/association-runs/contract20261003a/manifest.pending.json`
has null admission references and is deliberately inadmissible.
41.1 remains open; 41.2–41.6 have not advanced. No local payload was released,
no HDFS recovery was claimed, and no runnable registry entry was added.

Retained execution ledger: `.superpowers/sdd/2026-10-03-prediction-target-association/`.
Independent CPU audit: `independent-cpu-audit/live/receipt.json` within that ledger;
its immutable journal evidence snapshot records the exact receipt bytes.

## 41.1 accepted checkpoint — 2026-10-03

The held GPU lock was subsequently released by its existing owner. Additive CPU
and training roots passed independent runtime admission; the actual GN8 fixed
frame ran CUDA forward/backward with zero optimizer updates. Both roots contain
SciPy 1.18.1. All four initial model hashes agree. Original roots, controller
runs and historical evidence remain preserved.

Final source-v4 contract checks pass **41/41 live CPU Insula**, with all 41
tests independently collected without archival import collisions. The separate
auditor rehashed seven reconstructed input preimages, 172 unchanged model/input
source pins, all 85 historical proof-index entries, all 1,053 eligible and 1,279
native GT, and the fixed frame's 73 eligible objects. Five pre-existing cohort
source drifts are recorded explicitly; no claim is made that all historical
source files remain unchanged. Review also closed contradictory metadata and
very-large-step schedule cases. Historical red probes and earlier receipts stay
retained; their old pending/accepted manifests are not rewritten.

[Final contract evidence](../../../experiments/waymo-perception/research/association41-contract-final-20261003d/status.json)
binds manifest `d062ae9734e872cd2560013da54b00ee55faf6a2731370728740f87c29a427b9`
to independent acceptance receipt
`62cb43600cfef0f1c5b3a890745382eb6c3c47e65c1c57526d0ffaf1aed43dd9`.
This closes 41.1 only. Graph/target/native-oracle admission, learned costs, fitting,
registry/operator admission and HDFS recovery remain required. No payload release.
