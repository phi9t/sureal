# Waymo AV research: session retrospective and MAC improvement opportunities

Observation cutoff: October 4, 2026, 11:56:47 a.m. Pacific
(`2026-10-04T18:56:47.276Z`). Repository reference:
`a553645ef22761aa7708abf1ee109952a6cd2c38`.

This is a retrospective of existing work, not a new scientific result, runtime
admission, task assignment, or change to acceptance criteria. Three separately
assigned `gpt-6-luna` agents examined session coverage/workflow, scientific
outcomes, and incident-to-MAC mappings. The lead consolidated their findings
and checked the retained evidence. Detailed review artifacts and their hashes
are listed in the companion evidence manifest.

## Main finding

The program has a strong reproducible engineering foundation and credible
detector-fitting evidence. It has not yet established a held-out architecture
winner or completed the segmentation, camera/SAM, and forecasting comparisons.
The immediate scientific opportunity is to explain the sixteen-frame detection
failure and select a small controlled follow-up portfolio.

MAC addresses observed coordination problems: repeated reconstruction of worker
status, manual handoffs, ambiguous ownership, accumulated work awaiting landing,
and recovery of a long-lived thread. Its prospective benefit is making accepted
work easier to coordinate and recover. It cannot provide data authorization,
extra GPU capacity, a better experimental hypothesis, or relief from model
service overload. No MAC throughput improvement has been measured.

## Scope and limits

The locally indexed history contains two named roots, `avperc-impl`
(`01a0ee75-f519-7c80-b3c2-dc39d09e0b24`) and `avperc-frontier`
(`01a10073-9fd4-7361-b4f2-e7034230800a`). Recursive persisted spawn edges identify
29 cutoff-eligible root/descendant threads. Same-checkout discovery additionally
identifies 22 automatic Guardian review sessions, for 51 indexed session
records. Three retrospective agents created after the cutoff are excluded from
historical coverage. These audit agents are separate from the MAC worker seats;
their launch does not demonstrate the managed two-worker protocol.

The agents enumerated indexed histories and sampled public messages across the
timeline, then followed scientific claims to pinned repository evidence. They
did not read every transcript end-to-end or independently replay all raw
rollout files. Discovery therefore covers the locally indexed graph, rather
than proving recovery of every possible external, deleted, or unindexed
session. The companion inventory records coverage per thread. Private reasoning,
credentials, and raw tool transcripts are not included in this report.

The implementation root records 960 turns: 955 completed, three failed, one
interrupted, and one in progress at observation. It contains 60 compaction
items. The frontier records 41 turns and eight compaction items. These are
persisted activity counts, not measures of wasted effort, cost, or scientific
productivity. Nonzero tool exits can be intended negative tests. Overlapping
thread durations and token counters must not be summed as elapsed work.

The implementation turn `01a1059f-6b12-7360-a6cb-6268290a4d1e` began at
`2026-10-04T06:34:56Z` and ended at `2026-10-04T14:18:20Z` with
`serverOverloaded` during remote compaction. Its recorded 27,804,061 ms duration
includes work before the error; it is not a measured outage or hang duration.

## What the program has accomplished

| Workstream | Established evidence | Remaining scientific question |
|---|---|---|
| Acquisition and initial tracer | Two scenes, 34 files across 17 component families; deterministic native-table processing and verified HDFS transfer | Ingestion does not establish model quality |
| Geometry and sensor inspection, 01–06 | Independently verified R0 runtime, geometry, reconstruction, inspection views, and deterministic repeat | Exposure-time projection/visibility claims require their specific evidence |
| Larger data foundation | 64 training-box sources; 103-scene semantic, shape, camera, and point-grid admissions | Task-specific eligibility and scientific protocol freeze remain required |
| Runtime and native evaluation, 08–09 | Torch GPU foundation and TensorFlow-free native detection/point-semantic evaluation | Camera, LET, panoptic and forecasting paths retain their separate gates |
| Detector fitting and architecture exploration | All 15 trainable all-class fixed-frame treatments fit; seven of eight expanded treatments fit; one sparse recipe does not fit within its cap | Diverse-scene learning and held-out representation value remain unresolved |
| Balanced16 diagnosis | Verified baseline/residual 2,000-update trajectories and negative all-class outcomes; supervision, normalization, and exposure hypotheses | Which cause dominates, and which matched intervention improves native quality? |
| Camera/SAM and point transfer | Coordinate, teacher-mask, native projection-incidence and sparse-depth/boundary diagnostics | Predicted-prompt benefit, semantic support, calibrated visibility, and held-out transfer are unproved |
| Motion | Native acquisition/linkage, causal-prefix/codebook/geometry and metric-handoff preparation | Learned tracks/maps baseline and sensor-feature utility comparisons remain open |
| Experiment tracking and retention | Registry, append-only journal, checkpoint/replay and HDFS retention evidence | Recovery must be rechecked for the exact new artifact/source epoch |
| Models/training ownership, 44–48 | Design and task contracts | Implementation-plan admission and behavior-preserving migration remain open |
| MAC | Ticket49 project/Kata foundation and audited closeout landed | Dispatch, verification/landing/recovery, retention/cleanup, overview and concurrent pilot remain gated |

The [task index](../../../experiments/waymo-perception/research-task-index.md)
and [program goal](../tasks/program-goal.md) own the distinctions between
preparation, implementation, fitting, and scientific completion. R0 details
are in [the geometric tracer report](../../../experiments/waymo-perception/research/r0-geometric-insula.md).
For larger-cohort admissions, preserve the index's distinction between
individually live-verified processing and host-rehashed aggregates.

## What worked well

1. **Real measurements and geometry came first.** Native keys, calibration,
   return/pixel identity, transforms, and missingness were preserved. Unresolved
   joins stayed unresolved instead of being repaired by an unjustified match.
2. **Independent live verification found meaningful errors.** Literal math,
   export/evaluator checks, corruption refusals, and checkpoint/RNG replay
   provided stronger evidence than a producer's pass message.
3. **The fitting gate answered a concrete question.** The compact 4.847M
   parameter baseline passed the selected all-class frame at 500 updates and
   confirmed at 750. Insufficient capacity is not an explanation for failure
   on that frame; diverse-scene capacity remains a separate question.
4. **Negative and limited results were preserved.** Balanced16 failure, the
   capped sparse recipe, oracle SAM prompts, sparse visibility limitations,
   and missing labels remained visible rather than becoming success claims.
5. **Independent analysis changed priorities.** It separated foreground
   learning, target coverage, normalization state, exposure, and held-out
   generalization instead of selecting a larger model from parameter count.

These findings follow the
[initial-experiment analysis](../../../experiments/waymo-perception/research/2026-10-03-initial-experiments-analysis.md)
and its independent evidence audit. The analysis distinguishes single-frame
learnability from scientific adoption.

## What needs improvement

### Scientific decisions should drive experiment breadth

Most selected-frame variants share a similar sampled fitting interval, so their
successful fitting does not rank their generalization. Balanced16 total loss
fell sharply while foreground/native class quality remained weak. The run also
provided only 125 visits per frame at 2,000 updates, unlike 500–750 visits in
the successful one-frame controls. Those are different exposures, not a
controlled capacity comparison.

Assignment leaves 30 training-eligible objects without positives. The GN
backbone still has pillar BN, with a substantial evaluation/batch-statistics
loss gap. Neither finding alone establishes the dominant native-quality cause.
The appropriate next evidence is the
[object failure ledger, 42](../tasks/42-object-failure-ledger.md), followed by
the [frozen-weight normalization diagnostic, 43](../tasks/43-frozen-normalization-diagnostic.md),
with [association ownership, 41](../tasks/41-prediction-target-association.md)
kept separate. More architecture rows are useful only when their controls and
expected failure signatures distinguish a hypothesis.

### Readiness should be easy to inspect

The user repeatedly requested worker state, current work, active worktrees,
message delivery, and landing status. Those requests are direct evidence of
information that was difficult to obtain. They do not quantify lost time.
Status needs one evidence-derived view of issue/spec, owner, attempt, exact
thread, last meaningful progress, blocker, next action, candidate, and landing.

### Implementation and infrastructure need bounded ownership

The implementation thread carried data acquisition, experiments, storage,
resource admission, reviews, integration, and later collaboration foundations.
The recorded compaction failure demonstrates an interruption and recovery
need, but does not prove that thread size caused provider overload. Bounded
task attempts and durable handoff briefs reduce how much history a replacement
worker must reconstruct. The persistent lead still needs concise durable
decisions; bounded workers alone do not bound the lead's context.

### Probe installed capabilities before building around assumptions

Ticket49's post audit misclassified source-relative review references; closure
wrappers also needed a schema correction. The installed daemon transport
differed from the planned byte proxy. Independent review caught landing-script
identity/output/timeout gaps. Preserve these failures as evidence and exercise
the exact installed capability before freezing an adapter contract. A verifier
also needs independent tests and source identity.

The [ticket49 closeout](2026-10-04-collaboration-ticket49-closeout.md) documents
the failures, corrections, exact-source acceptance, and remaining task50
transport/stop-coverage gate. It supersedes stale proposal-status prose for
ticket49's actual acceptance at this observation.

## How MAC would help

| Observed difficulty | Specified MAC mechanism | Residual limitation |
|---|---|---|
| Manual status reconstruction and message relay | Attributed summaries; issue/attempt/thread bindings; freshness and source coverage | An observer can be stale or wrong; displayed facts need independent reconciliation |
| Unclear ownership across branches and worktrees | One Kata owner; claim generation; distinct worktree/output scope per attempt | Worktrees share Git refs/objects; isolation is cooperative |
| Uncertain launch, restart or publication | Prepared/result receipts; exact-state reconciliation; retained unknown effects | Unknown effects can occupy a seat until resolved |
| Accumulated work awaiting integration | Bounded candidate and explicit verification/landing stages | Review and landing remain serial constraints |
| One worker lands while another has an old base | Retain stale candidate; explicit fresh attempt/base and fresh verification | This can duplicate verification effort even for disjoint changes |
| Long-lived thread interruption | Bounded turns; frozen briefs/source; retained reports and candidates | Provider capacity and lead-context growth remain external issues |
| GPU work leaves other work idle | Second seat for independent CPU preparation, analysis or verification | Two workers do not provide two GPUs or authorize overlapping GPU jobs |
| Producer reports overstate completion | Exact candidate/runtime binding and independent acceptance | Reviewers and auditors can also make mistakes; scientific design remains essential |

These are prospective benefits from the
[MAC specification](../../superpowers/specs/2026-10-03-sureal-serial-collaboration-design.md),
[runtime identity model](../../superpowers/specs/2026-10-03-codex-runtime-domain-design.md),
and [worker-state model](../../superpowers/specs/2026-10-03-worker-session-state-design.md).
Only ticket49 is accepted at the cutoff. The audit's use of ordinary subagents
is not proof of the MAC dispatch, overlap, recovery, or cleanup contracts.

## Acceleration without changing acceptance

1. **Prepare the next scientific work while MAC implementation proceeds.**
   Complete the models/training plan and frozen reference/comparison inventory;
   draft task-specific scientific protocols under07; prepare42/43 definitions
   and independently auditable fixtures from retained evidence. Preparation
   remains separate from implementation/optimizer admission.
2. **Finish the agreed MAC path with useful increments.** Preserve
   `50 → 51 → 52 → 53.0 → 54 → 53`; surface task50 capability blockers early.
   The final pilot proves actual concurrent sessions, stale-base handling,
   exact landing, retention and cleanup before scientific adoption.
3. **Use complementary tasks.** For the sequential models/training migration,
   pair the current implementation with independently scoped comparison
   preparation/review. After scientific admission, pair one GPU owner with a
   CPU-only analysis, input, or verification task using frozen inputs and
   separate outputs. The verifier must remain independent of its producer.
4. **Retain the approved detector investigation order.** Resource and exact
   continuation admission precede the unchanged four-case sustained study;
   preserve42 before43, isolate41.2, and keep conditional pillar-LN separately
   frozen. Do not merge target, norm, loss and architecture interventions.
5. **Promote a small controlled portfolio.** Keep the compact baseline; use
   normalization/coverage findings to select treatments, and compare point
   attention with its MLP control. Move capable treatments to segment-held-out,
   multiseed evaluation with full native GT and measured cost. Keep range and
   the current sparse recipe exploratory.
6. **Open the other scientific lanes deliberately.** Point segmentation,
   predicted camera baselines/SAM, and Motion require their own protocols and
   metrics. Oracle masks, untrained semantic exports, and oracle forecasting
   metrics cannot substitute for learned held-out comparisons.

The [approved scientific order](../../../experiments/waymo-perception/research/2026-10-03-approved-execution-order.md)
and [models/training design](../../superpowers/specs/2026-10-03-first-class-models-training-design.md)
remain authoritative. This retrospective does not reorder their execution.

## How to tell whether MAC actually improves the work

Suggested observational counters are time from admitted task to accepted
deliverable; last-progress and blocker freshness; first-pass review outcome;
repair and stale-refresh effort; resource wait versus execution time; recovery
from uncertain effects; duplicated external actions; and completed scientific
decisions per GPU-hour and elapsed time. Record task type and scope before
comparing periods. Small heterogeneous pilots cannot establish a general
speedup, and thread/turn count is not a throughput measure.

These counters are recommendations, not new implementation acceptance gates or
claims of measured improvement. The useful research finish line remains an
evidence-backed explanation of the sixteen-frame failure, a controlled next
treatment, and subsequently held-out multimodal/forecasting decisions.
