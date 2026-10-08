# Waymo research program: causal, evidence-indexed scene understanding

Date: 2026-09-29. Status: research-program draft for review; no new model
implementation or experiment results. This program develops the user's supplied
Perception-first specification and connects it to the completed acquisition
tracer and SUREAL's coherent-scene research direction.

The [primary-source audit](../../../experiments/waymo-perception/research/program-source-audit.md)
records dataset/schema constraints and TF-free evaluator candidates. The pasted
chat citation markers are not source links; this audit supplies reviewable ones.

## Scientific question and recommended approach

Given only measurements available by decision time t, does a representation of
geometry, objects, semantics and temporal memory improve scene estimates and
future prediction over task-specific baselines? Every assertion must identify
its evidence, temporal access, supervision and evaluability.

Three possible approaches are task-specific detection/segmentation first,
a shared scene representation evaluated through those tasks, or an immediate
language-conditioned world model. We recommend the second, with the first as
its mandatory controls. It directly tests the value of shared persistent scene
state while retaining measurable baselines. Immediate language/world-model
work creates too many simultaneous uncertainties about geometry, targets and
evaluation. Language distillation follows the geometric and semantic controls.

Perception anchors this program. Motion and E2E are separately acquired,
versioned downstream task suites. No cross-dataset scene correspondence is
assumed. The initial scientific contribution is an auditable comparison of
representations and evidence access; novelty of a learned architecture remains
an experimental question. Surflo is an inherited reconstruction baseline, not
proof of a new Waymo scene encoder.

## What has been established and what remains a prerequisite

The [tracer report](../../../experiments/waymo-perception/research/tracer-bullet-e2e.md)
establishes 34 checksum-verified source objects, two validation scenes,
1,200,154,353 bytes, all 17 available component families, 397 frames and
143,625 native manifest rows. HDFS upload/readback passed and two offline
processing runs produced identical manifests. Segmentation and keypoint
coverage is sparse. Of 7,074 camera/LiDAR associations, 337 lack same-frame
LiDAR box targets; these remain unknown, including 32 whose target object ID
was not seen elsewhere in the scene.

The current runner uses bubblewrap with a pinned Python environment and host
system libraries. It has not established the dedicated image/rootfs Insula
contract used by the maintained SUREAL experiments. Neither point conversion,
causal sensor alignment nor synchronized point/image visualization has run.
Thus acquisition/native-table plumbing is complete, while the full geometric
Insula tracer remains the first gate below.

The existing two validation scenes are engineering fixtures. They are not a
training set, a representative benchmark or evidence of generalization.

## Mathematical prerequisite

The [geometry foundation](2026-09-29-perception-geometry-foundation-design.md)
defines polar/range/BEV mappings, frame/time conventions, SO(3)/SE(3) calculus,
sensor projection and uncertainty verification. It precedes encoder comparisons
and strengthens R0. Radar is a generic/synthetic mathematical adapter because
the acquired Perception cohort has no radar data. SymForce is a candidate
derivation/codegen tool, conditional on convention and runtime checks.

## Information contract

Represent scene state as S_t=(G_t,O_t,M_t,Z_t,U_t), with independently
inspectable fields and task heads. Initially use PyTorch for learned models and
geometry kernels; JAX remains an allowed alternative when it answers a specific
experiment. No TensorFlow dependencies, SDK imports or TensorFlow evaluator
exception are authorized. PyArrow remains the table-reader boundary.

A SceneExample contains identity, observations, targets, supervision coverage,
derived evidence and provenance. Model-facing observations may contain sensor
measurements, acquisition times, calibration and permitted poses/history.
Annotation-derived fields are structurally excluded: NLZ, object IDs, difficulty,
box-derived counts, target velocities, panoptic identities and future states.
Sensor intensity/elongation are measurements; NLZ is coverage metadata.
Ground-truth tracks/maps used in the Motion baseline are explicit oracle inputs
for that task, not evidence of an end-to-end Perception capability.

For each observation store source key, event/acquisition time, available-at time
and reference-frame definition. A causal view contains only measurements whose
availability is no later than t. Exposure completion, scan intervals and
per-pixel pose support matter; a frame key alone does not certify causality.
Where publication omits online availability, record the assumption and label
the protocol as a dataset-time approximation. Report latency separately.
Sequence-refined assets, future information and full-sequence teachers are
restricted to declared offboard supervision, never causal inference inputs.

Preserve these identity namespaces separately: measurement point key
(frame, sensor, return, row, column); native 3D box ID; camera box ID;
image-local and sequence-consistent panoptic ID. Point projection, explicit
object association and projected box geometry are distinct relations.
The unresolved 337 associations cannot become positive/negative matching
labels by dropping or borrowing another frame's target.

Each task has its own taxonomy and coverage mask. Record the mapping version,
unknown/unmapped category and evaluation ontology. Do not equate integer labels
across box, LiDAR and camera schemas. Distinguish present-labeled, explicitly
labeled-empty, unlabeled, unavailable and unknown coverage. An absent v2 box
row cannot establish labeled-empty without a verified coverage source.

G contains measured points, estimated surfaces, ray-supported free space and
visibility support. Empty voxels are unknown unless valid rays support free
space. Multi-return/invalid rays need a declared conservative rule. O contains
instances and estimated physical state; benchmark boxes need not enclose all
clearance-relevant geometry. M retains histories and observation ages. Z
contains task-specific categories and evidence-grounded relations. U separates
measurement/coverage limitations from predictive uncertainty; masks are not
probability calibration.

## Hypotheses and decisive comparisons

| ID | Hypothesis | Controlled comparison | Primary evidence |
|---|---|---|---|
| H1 | Camera evidence improves point semantics beyond LiDAR alone | LiDAR-only vs direct fusion on identical labeled points | Class IoU/mIoU and localization diagnostics |
| H2 | Camera teaching improves a LiDAR-only inference representation | LiDAR-only baseline vs camera-teacher student, both LiDAR-only at inference | Same point metrics, teacher coverage and student cost |
| H3 | Persistent scene state improves temporal consistency and recovery | Per-frame + simple association vs causal memory, matched history access | Consistency, ID changes, stale-belief correction after reappearance |
| H4 | Surface/semantic state adds information beyond boxes | Box-only vs boxes + shape/semantics, with controlled object-state inputs | Clearance/geometry diagnostics and downstream gains |
| H5 | Sensor-derived scene evidence improves forecasting beyond tracks/maps | Motion tracks+map vs +LiDAR, +camera tokens, +fused state | Official-equivalent trajectory metrics and probability diagnostics |

H1 and H2 distinguish inference-time fusion from training-time supervision.
H3 must include a matched-history baseline so extra frames do not masquerade as
a memory-architecture benefit. H4 needs separately audited geometric targets;
box IoU cannot validate obstacle clearance. H5 is a later transfer experiment,
not an assumed result of improved Perception scores.

## Concrete model bases and reading sequence

Use [PointPillars](https://arxiv.org/abs/1812.05784) first to establish the
LiDAR encoding/detection seam, then [SWFormer](https://arxiv.org/abs/2210.07372)
to study sparse window attention. Insert a CenterPoint-style center head as a
small controlled bridge: compare the PointPillars reference head with a pillar
encoder + center head, then keep the center-head contract fixed when replacing
the backbone. The common-head sparse model is a SWFormer-style hybrid; its
heading encoding, losses and decoding differ from the paper's exact sparse head.
Evaluate a faithful head/diffusion recipe separately. Both encoders use XY
pillars, rather than this being a mandatory jump to height-binned 3D voxels.
No official SWFormer source/checkpoint was verified in the bounded review;
PyTorch implementation effort is therefore an explicit feasibility gate.
This is an ablation design, not a claim that the papers are one implementation lineage. A full SECOND/SST reproduction is optional reading,
not another mandatory project. See the [LiDAR source review](../../../experiments/waymo-perception/research/lidar-encoder-bases.md).

Run a camera branch alongside the working LiDAR baseline: FCOS3D for a
perspective-space control, BEVDepth for explicit-depth BEV construction,
and BEVFormer-S/temporal BEVFormer for spatial attention and memory. The
[LET reference](https://arxiv.org/pdf/2206.07705) supplies camera evaluation,
not an encoder. BEVDepth uses LiDAR depth supervision during training, which
must remain explicit even though inference is camera-only. BEVDepth and
BEVFormer are alternative representation mechanisms, not compulsory successive
full reproductions. See [camera models and evaluation](../../../experiments/waymo-perception/research/camera-encoder-bases.md).

Compare camera and LiDAR representations through a common metric-coordinate
BEV contract, then test fusion and distillation. Use camera-synchronized box
targets for the camera protocol and preserve LiDAR-reference targets for the
LiDAR protocol. Cross-modality comparison requires separately declared matched
time, coverage and target support. Report tolerant AP with affinity-weighted AP
and uncorrected localization errors; LET improvement alone cannot establish
more accurate physical geometry.

Paper reproduction and research adaptation are separate recipes. Freeze
classes, sensors/returns, number of historical frames, spatial extent, resolution,
augmentations, head, image pretraining, evaluator configuration and budgets.
First use current-time evidence for both modalities. Add history only after
single-time-step controls pass. Multi-task point semantics is an explicit head
and label-mask contract. PointPillars needs a research extension; SWFormer
already presents a preliminary joint detection/point-segmentation head in its
appendix, making it particularly relevant to the shared scene-encoder program.

### Range-view branch: RSN and full-scene features

Add [RSN](https://arxiv.org/abs/2106.13365) as a parallel representation
branch alongside pillars, rather than requiring it between PointPillars and
SWFormer. Its range-image frontend, learned foreground selection and sparse
3D detection stage test a different efficiency mechanism. The paper uses
TOP LiDAR, selects the last return and reports single-/three-frame models;
our five-sensor/both-return variants are declared adaptations. Its original
implementation uses TensorFlow, so a PyTorch/JAX port and sparse-kernel
compatibility check are required; no upstream runtime exception is allowed.
The [range-view review](../../../experiments/waymo-perception/research/range-view-bases.md)
records the source contract and implementation limits.

Start with a lightweight range-view feature encoder and a masked native-semantic
head over all valid TOP returns. Add a separate box-supervised objectness head,
then an RSN-style selected-point detection path. Full range features and
measurements stay available to geometry/semantics/memory; detection's foreground
selection cannot erase road, vegetation, unboxed obstacles or visibility evidence.
Invalid returns remain invalid and NLZ stays outside model observation features.
Preserve sensor/return/row/column keys through range-to-point and camera-feature
lookup. Handle sensor-specific shape, angular geometry and azimuth boundary
policy explicitly; do not resize away native point identity.

The decisive comparisons are range features off/on without selection, selection
off/on with the same features, and range-selected sparse convolution versus
range-selected sparse attention under a compatible fixed head/input contract.
The attention variant is an RSN/SWFormer research hybrid, not either paper's
reproduction. Include random or geometric selection matched on point count;
an oracle box-selector is a labeled diagnostic upper bound, never an inference
baseline. Fix sensor/return/history access, range, classes and evaluation support
across representations before interpreting gains.

Measure box-foreground point recall, objects retaining usable points,
class/distance/support breakdowns, selected-point and active-voxel counts,
latency including range encoding/gather/voxelization, memory, AP/APH and full
point semantics. Tune selector thresholds on development data and freeze them
before evaluation. False-negative selection is an information bottleneck that
the downstream detector cannot recover; efficiency alone is not acceptance.
Box-derived foreground background is not a free-space or exhaustive obstacle
label. Missing annotation coverage must not become a confident negative.

Recommended execution order after R0 is the small pillar and range-view
controls, followed by the center-head control and an RSN-style hybrid;
SWFormer then tests sparse attention and multiscale context. Camera baselines
can proceed once the shared geometry/target contract passes. These are gated
comparisons, not a requirement to fully reproduce every architecture before
asking a scientific question.

### Reference-object distance branch: R4D

[R4D](https://arxiv.org/html/2206.04831v1) complements camera-to-BEV methods
with target/reference relation reasoning. Its main task uses short-range LiDAR
and images to estimate distant object depth; the appendix also evaluates
image-estimated reference distances. It is not inherently a camera-only detector
or a complete box/occupancy representation. Its target distance is optical-axis
camera depth, distinct from Euclidean range and LET's line-of-sight localization.
The [source review](../../../experiments/waymo-perception/research/reference-distance-bases.md)
records paper-specific inputs, labels and metrics.

Add H6: reference relations improve target distance estimation beyond an
appearance-only estimate and a baseline with the same reference evidence but
no pairwise relation model. Run this after a camera distance baseline and
trustworthy measured-reference extraction; it need not await the full temporal
scene model. Evaluate separately with camera-estimated reference depths,
causally estimated LiDAR-backed reference states and oracle annotated references.
Oracle boxes/distances are diagnostic inputs only. The measured-reference
variant is multimodal at inference; its benefit cannot be called camera-only. The paper's main reference depths
come from a LiDAR detector; target 2D proposal provenance is not a fully specified
reproduction protocol. Freeze target proposals across distance-head comparisons, then separately
measure end-to-end detection plus distance and missed-target coverage.

Sweep reference count, depth noise, missing/incorrect associations and stale
reference age. Compare learned attention with pooling and shuffled relations;
include a no-reference fallback. Record evidence source, reference identity,
coordinate/time conversion and uncertainty for every relation. An attention
weight alone is not evidence of a causal explanation or calibrated confidence.
Do not use target ground-truth depth to select, associate or construct references.

The paper's long-range annotation extension is not established by our ordinary
v2.0.1 receipt. Verify downloadable release, access, schema, segment correspondence
and label provenance before promising replication at 80–300 m. Until then a
range-censored pilot can hide distant LiDAR evidence on targets with existing
labels while permitting nearer references. Censor derived features, cached
tracks and historical points too. Label it a within-release extrapolation test;
it does not establish performance beyond the native labeling range.

Report absolute/relative depth error, RMSE and threshold accuracies with fixed
range/support breakdowns, alongside target proposal recall and reference
availability. Keep these depth metrics separate from LET AP and downstream
safety claims. Use Torch/JAX and audit any reused detector or preprocessing
runtime. This branch concretely tests the value of evidence-indexed object
relations without making language or full-scene generation a prerequisite.

## Binding implementation completion gate

User-confirmed 2026-09-30: every implementation milestone must run live inside
its dedicated Insula to prove the implemented behavior works. Unit tests,
source inspection, dry-run plans and host execution are supporting evidence;
none can replace this gate. This requirement applies to geometry, readers,
exports, evaluation adapters, model heads, training and representation variants.

Milestone states are planned, implementing, implemented-awaiting-live-verification,
verified-complete, or blocked. A blocked record identifies the unmet prerequisite
and preserves completed work. Only verified-complete closes a milestone or
unblocks dependent scientific claims. Existing historical table-tracer results
remain evidence of their recorded scope, not proof of the dedicated-rootfs gate.

Every milestone declares its verification contract before implementation:
locked runtime, representative inputs, changed behavior, executable assertions,
required artifacts and resource budget. Verification consists of a real Insula
entry, an exercise of the changed behavior, and independent output validation.
It must check actual isolation, source integrity and runtime identity. No silent
host fallback, mocked execution, skipped required check or an environment flag
standing in for isolation proof is permitted.

The verification receipt records milestone ID, exact command/arguments, UTC
start/end, exit status, source/cohort hashes, code and runtime locks, observed
versions, assertion results, resource observations and artifact hashes/paths.
The verifier checks these against the current candidate implementation; a
receipt from older code or a different runtime cannot close a newer change.
Writes use staging and promote only after validation. Failure preserves a
bounded diagnostic receipt without publishing successful artifacts. A receipt
is necessary but is not self-authenticating: its checks must be independently
replayable and supported by captured live logs and output validation.

Runtime availability is checked before a milestone's expensive run. CPU work
uses a dedicated CPU Insula; learned tensor work uses the appropriate locked
Torch/JAX CPU/GPU Insula. Builds/acquisition can be networked separately;
processing/evaluation defaults offline. The runtime verifier tests inability to
reach a host listener, readonly sources, permitted output writes and absence of
credential mounts. Verify image/rootfs content identity rather than only a
marker file. GPU milestones additionally demonstrate actual device execution.

The [live verification contract](2026-09-30-live-insula-verification-design.md)
defines milestone-specific evidence. The current geometry core is
implemented-awaiting-live-verification, not complete. Recheck the previously
observed environment restrictions at execution time; do not assume they persist.

## Milestones and acceptance gates

### M0 — Prove Insula itself works

The first milestone is a live dedicated runtime proof, independent of Waymo
processing. Build/materialize and lock the CPU rootfs; verify real entry,
synthetic computation/Parquet/image IO, actual network and mount isolation,
private HOME and fail-closed behavior. Independently validate its receipt.
No native data replay, geometry or model work is required to pass M0.
All subsequent implementation gates depend on verified M0; see the
[live gate sequence](2026-09-30-live-insula-verification-design.md).

### R0 — Native replay and sensor-to-scene inspection after M0

Materialize a pinned CPU rootfs using existing repository Insula conventions;
separate networked builds/acquisition from offline processing. Lock the rootfs,
Python packages, code and source receipts. Verify that network access is blocked
using a connection test, read-only inputs and absence of credential mounts.
Replay the complete native-table tracer inside it and reconcile counts/hashes.

Implement and verify TensorFlow-free range conversion against pinned upstream
formulae and independent analytic fixtures: extrinsics, beam inclinations,
azimuth conventions, positive-range masking and TOP per-pixel poses. Preserve
both returns and originating pixel identity. Frame timestamps and pose
references must be explicit. Validate point/projection/label alignment through
filtering and concatenation; use negative tests for swapped returns and masks.

Deliver a top-LiDAR/overlapping-camera view with projected points, available
semantic overlays, native boxes, object histories and a coverage report.
Quantify projection discrepancies with support counts and timing assumptions;
identify whether using supplied projections or newly computed camera geometry.
A static projection is not evidence of rolling-shutter correctness. Extend
validation to all sensors/returns before claiming full geometric coverage.
Promote outputs only after these checks pass. This is the next engineering
implementation unit, not a model-training milestone.

### R1 — Small measurable Perception encoder

Acquire a separate training cohort through Waystone; freeze whole-segment
train/dev/evaluation manifests before tuning. Keep official partitions and
window source identity. Reserve an untouched official-validation cohort for
final comparisons; the existing debugging scenes remain development-only.
Choose cohort size after measuring labeled support, class coverage, memory and
throughput. Report scene counts, frames, valid labeled points and object counts;
frame count alone is an inadequate budget or supervision description.

Establish two independent workstreams: TOP point semantics/segmentation and
current 3D detection. Each has its own baseline, coverage, export and evaluation
gates. Do not make detection a second head of an already shared initial model. Use
per-task masked losses, with zero-supervision batches contributing zero rather
than fabricated negative labels. Gate scaling on small-subset overfit, correct
prediction export, independent numerical metric checks and interpretable
failure cases. Sparse labels make the current slice insufficient for broad
class-performance claims.

Verify official-evaluation compatibility without TensorFlow. Official native C++ detection, tracking, segmentation executables and a Motion
metric library are candidate paths; their transitive dependency closure remains
unverified. Establish a verified TF-free path where available, with fixed prediction
fixtures and parity against published definitions. Until established, report
local metrics as diagnostics and mark official benchmark scores unavailable.
Do not silently approximate AP/mAP and present it as an official score.

### R2 — Fusion and foundation-model distillation

Use one point encoder/head and frozen cohort/evaluation support for LiDAR-only,
direct image-feature fusion and camera-teacher/LiDAR-student experiments.
Record training inputs and inference inputs separately. Match optimization
steps, labeled examples and geometric support; report parameter count, teacher
precomputation, training compute, inference latency and memory separately.
Declare when an unavoidable compute difference prevents a matched-cost claim.

Audit feature projection, occlusion/reliability rules, teacher version,
pretraining data limitations and any target-derived teacher conditioning.
Include frozen image-feature control, shuffled-correspondence negative control
and sensor-drop tests. Language-aligned features are optional after H1/H2;
open-vocabulary claims need an audited held-out ontology/evaluation set.
Qualitative retrieval alone does not establish detection or localization.

### R3 — Causal persistent scene state and uncertainty

Compare memory against per-frame and matched-history aggregation baselines.
Retain acquisition time and track age; ego alignment does not remove actor
motion. Perturb camera availability, history frames, LiDAR support and visibility.
Predeclare corruption levels and recovery windows, then measure degradation,
recovery time and correction of stale geometry/identity.

Evaluate predictive confidence using held-out outcomes, calibration plots and
proper scores where the output distribution permits them. Never interpret
annotation coverage as calibrated confidence. Study coherent scene hypotheses
only after a deterministic baseline exists: shared scene-level samples should
be tested for cross-query consistency as well as pointwise accuracy, connecting
to SUREAL's [existing research direction](../../coherent-scene-hypotheses.md).

### R4 — Separate downstream task suites

Motion: acquire scenario-keyed historical extensions and native maps/tracks;
verify supported correspondence and causal cutoff. Camera tokens constrain the
available encoder interface. Compare tracks+map, +LiDAR, +camera tokens and
+fused state with a common forecasting decoder. Keep accurate-track input fixed
to test information beyond boxes rather than detector quality. Report native
trajectory configuration, candidate count, temporal sampling and probability
quality separately from best-of-K displacement errors.

E2E: independently acquire its camera/ego-history/intent records. Verify which
fields are actually populated. Compare image/trajectory baselines against
spatially structured representations; use numerical trajectories and supported
human-preference subsets. Explanations are hypotheses requiring an evidence
audit. No raw-RGB equivalence with Motion tokens or arbitrary dataset join is
assumed. R4 starts only after a credible Perception representation and verified
TF-free evaluation path; no downstream data acquisition is launched by this draft.

### Optional branches

Ray-derived geometric occupancy and Motion agent-occupancy forecasting retain
separate target generators, semantics and scores. Object-asset reconstruction
is another independently versioned branch, with auto-label and offboard-pose
provenance. Language, maps, flow shards and assets are not dependencies until
actual release availability and evaluation support are verified.

## Experimental decisions and stopping rules

Every run declares hypothesis, allowed information, cohort/split hashes,
coverage/masks, derivations, code/environment/checkpoint hashes, seed, budget,
metrics, uncertainty protocol and failure examples before execution.

Use at least three training seeds for claims beyond engineering pilots; report
per-seed results and uncertainty from resampling whole segments. Correlated
frames/points are not independent samples. Compare identical evaluable support
and publish exclusions. Do not tune on the final evaluation cohort. Record
sensor latency and offline teacher cost so information access and compute
cannot be hidden inside one score.

Before each expensive comparison, predeclare a practical effect threshold for
its primary metric using baseline variance, task meaning and measured cost.
The current evidence cannot justify a universal numerical threshold. Stop a
variant after the preregistered budget if it misses that threshold, fails a
robustness gate or violates causal/lineage invariants. Preserve the negative
result. Continue scale-up only when correctness gates hold and a result merits
additional compute; more capacity is not the default response to no gain.

## Artifacts and boundaries

Waystone owns storage resolution, complete-release HDFS ingestion and bounded
local materialization. SUREAL owns offline geometry, SceneExample contracts,
model experiments, exports and evidence-indexed reports. Runtime and pipeline
engineering remain in the existing implementation plan; scientific comparisons
are recorded here and receive their own bounded implementation plans.

Keep raw data, checkpoints, teacher caches and generated views outside git.
Commit small provenance locks, recipes, metric summaries and decision records.
Each scene assertion stores value, supporting source keys, evidence time,
derivation version, coverage status and predictive uncertainty if available.
A statement about an unseen region must remain an observation-limit claim;
causal intent, clearance and hidden actors need their own support and targets.

## Next decision

Review this program as the research charter. The immediate implementation scope
is R0: dedicated Insula plus trustworthy sensor-to-scene geometry and overlays.
The first scientific comparison after R1 is H1/H2, followed by H3. Motion/E2E,
open-vocabulary evaluation and occupancy remain separate gated workstreams.

R0 implementation is scoped in [the geometric Insula plan](../plans/2026-09-29-waymo-r0-geometric-insula.md).

## Research steering — 2026-09-30

User confirmed separate detection and segmentation work first. Investigate
[SAM](https://github.com/facebookresearch/segment-anything) and
[SAM3](https://github.com/facebookresearch/sam3) afterwards to choose a meaningful
combination mechanism. Prompted masks, semantic recognition, 3D lifting and
joint training/distillation are different proposed capabilities, not an approved
single architecture. Oracle prompts and predicted prompts require separate
protocols; pseudo-labels never become native ground truth by entering a loader.

The scene-understanding scope is not yet fixed. Research official Waymo metrics
and behavior-prediction/planning papers before choosing its concrete output and
scientific acceptance criteria. Existing H3–H6 and R4 are candidate questions;
they do not imply every downstream protocol is acquired, implementable or chosen.
The decision map tracks these evidence prerequisites.

## Evidence-informed proposals after Q1/Q2 review

The primary-source [SAM integration review](../../../experiments/waymo-perception/research/sam-integration-pathways.md) proposes frozen predicted-box mask refinement first, separate SAM 3 concept discovery, geometry-aware transfer, and offline distillation before optional joint training. Oracle prompts, measured LiDAR depth, predicted depth, and causal versus offline video are separate experimental conditions. These are proposals pending discussion, not approved architecture choices.

The [evaluation pathways review](../../../experiments/waymo-perception/research/scene-understanding-evaluation-pathways.md) proposes a controlled Motion forecasting probe using native tracks/maps and supported causal sensor extensions before planning experiments. Wayformer and MTR are forecasting anchors; UniAD motivates downstream task interfaces but does not establish transfer to Waymo. Perception quality, forecasting utility, offline ego-trajectory agreement, and closed-loop policy behavior remain distinct claims. No arbitrary Perception–Motion joins are permitted.

Evaluator compatibility is an implementation prerequisite: native C++ metrics and NumPy rater-feedback scoring are candidates requiring runtime/parity verification. Official occupancy-flow and Sim Agents Python metrics import TensorFlow, and Waymax ingestion has TensorFlow dependencies. Their TF-free replacements or ingestion paths are unverified. Every implementation and evaluation milestone retains the live-Insula gate, starting with M0.

## Selected follow-up directions — 2026-09-30

User approved frozen predicted-box mask refinement as the first SAM integration experiment and controlled forecasting utility as the first downstream target. The [detailed experiment contracts](2026-09-30-mask-refinement-and-forecasting-design.md) define treatments, provenance, geometry, causal access, evaluator requirements and separate implementation/scientific gates. Earlier proposals remain historical context; these selected directions supersede their pending status.
