# Tier 1: batch-overfit verifier for model architecture development

Status: required first development gate, requested2026-10-01. This supplements the original scientific protocol; historical thresholds/results and heldout rules are unchanged.

## Goal

Before a model architecture advances to tiny-cohort and heldout experiments, prove that it can learn a fixed training batch through its actual inference/export/evaluation path. Record quality, learning speed and resources. An aggregate loss reduction alone is insufficient.

## Fixed contract

Pin training-only batch keys, observations, supervision masks, target assignment, class support, model/candidate/runtime identities, seed, optimizer, update cap, checkpoints and native evaluation settings before execution. No augmentation or stochastic input resampling in the primary memorization fixture. Preserve complete native eligible GT, uncovered objects and measured support. Every architecture uses identical fixtures for a matched task. A task/head change must declare the corresponding verifier adaptation.

Current detection fixture is the first frame of the independently admitted16-frame manifest, seed17, Adam1e-4, clip10, batch1,2000 updates. It contains vehicle/pedestrian/sign GT, no cyclists; it cannot certify cyclist learning. All17 eligible GT remain in scoring. Subsequent fixed coverage fixtures must exercise every required class and supervision type before the whole model passes Tier1; fixture selection is frozen before candidate comparisons and never uses validation outcomes.

## Required acceptance and evidence

- Finite losses, gradients, optimizer states and predictions; physical input/target isolation.
- Declare loss criteria but require native task quality as well. For detection Tier1, report AP/APH for every populated class and require each populated class APH>=.8; report the original mean>=.8 gate alongside this stronger per-class diagnostic. Current one-batch sign result fails both. No claim of all-class acceptance on a fixture missing a class.
- Independently validated live Insula receipts for checkpoint replay/loss equations, decoding/NMS, original measurement metadata, native GT retention, export and native scoring.
- Time/update-to-first-quality-pass and time/update-to-sustained-pass (two consecutive sampled checkpoints including a final passing checkpoint). Keep the full curve; don't select a lucky peak. A checkpoint grid only brackets threshold crossing; report(last-fail,first-pass], not a falsely exact update count. If no checkpoint passes, report right-censored at the budget, not successful time-to-fit.
- Record synchronized cumulative training time, reserved device/wall time, checkpoint/evaluation/scoring overhead, per-step distributions, peak GPU/RSS/storage and device/runtime versions. Larger models' quality gains and learning speed must be compared with these costs.
- Record head/loss-component curves, positive/negative confidence, per-head gradient norms, clip frequency and train/eval discrepancies. These diagnose learning difficulty; they do not by themselves identify a causal bottleneck.

## Current evidence and diagnostic replay

[One-batch result](native-one-batch-overfit-result.json):2000 updates, final loss.0581429675, vehicle/pedestrian/sign APH.998079/.988051/.226459, mean.7375296667. Original final-checkpoint-only run took124.271s in-worker, with about120.064s training-loop wall time; this is budget cost, not measured time-to-fit. At that final-only stage, earlier quality was unknown. The independently audited checkpoint curve below now resolves the sampled crossing intervals.

Completed the same recipe with checkpoints0,25,50,100,200,300,500,750,1000,1500,2000. Preserve evaluation-mode heads for native scoring. Snapshot/restore BN buffers when taking training-mode diagnostics; no extra optimizer updates or changed trajectory. Reconcile the final heads against the already independently replayed2000-update baseline.

Hypotheses to test, not fixes: initial focal loss dominated by background; clipping constrains early optimization; slowly adapting BN statistics create inference lag; small/undercovered sign boxes are geometrically difficult. Measure component loss and gradient/confidence curves first, then per-object sign overlap/center/dimension/yaw errors and pre/post-NMS recall. Any remedy requires a matched, separately declared experiment.

## Progression

Tier1 fixed-batch correctness/memorization → Tier2 small multi-frame cohort → Tier3 controlled heldout experiments. Negative or missing Tier1 evidence keeps architecture claims open. Tier1 success is never a generalization claim; completion of the overall research goal still requires encoding, SAM and causal Motion comparisons with uncertainty/resources and decisions.

For segmentation and forecasting, declare task-appropriate native metrics and mask/target coverage before execution; detection APH is not a substitute for those contracts. Log optimization and native evaluation curves on frozen batches, with replay and time/resource evidence, before expanding to their small-cohort and heldout studies.

## Independently audited outcome

[Learning investigation](tier1-one-batch-learning-investigation-result.json) verifies all11 checkpoints and final-head equality to the original run. Vehicle/pedestrian APH>=.8 is first observed at750, bracket(500,750] updates and(38.006,53.718] synchronized training-step wall seconds. Mean APH>=.8 is first observed1500, bracket(1000,1500] and(72.922,107.302]s, but fails at2000. No populated-class pass or sustained final mean pass is established. The stronger whole-model Tier1 gate remains open; no cyclist coverage exists.

The initial total objective is99.91% negative-anchor focal loss. At200 updates evaluation loss already passes the80% reduction criterion while native APH remains0. This demonstrates why the loss ratio cannot define time-to-fit. At200, batch-statistics loss1.573 versus running-statistics inference loss100.139 exposes a large mode gap; those intermediate mode measurements are diagnostics, not proof of the sole cause.

At frozen final weights, one physical-only BN-statistics refresh with zero optimizer updates changes inference loss.058143→.007483 and meanAPH.737530→.864156. Independent live checks verify literal BN moments, unchanged weights, exact treatment heads and native metrics. This establishes BN statistics as a contributor to the final regression on this batch; it does not establish a heldout benefit or early-checkpoint speedup. Signs remainAPH.595564; three lack positive anchors. Thin-sign geometry diagnostics show centimetre-scale error sensitivity.

Instrumented run:146.448s synchronized training-step wall,152.134s total worker wall,215.302s additional native-curve scoring wall. Independent audit wall time is additional and is not included in these figures. The original less-instrumented loop took120.064s; report instrumentation/runtime variation rather than treating the replay as a clean training-speed comparison.327 of2000 updates were clipped; causal impact of clipping remains untested.
