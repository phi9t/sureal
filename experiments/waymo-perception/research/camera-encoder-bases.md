# Camera encoders and the LET evaluation contract

Date: 2026-09-29. Research recommendations; no model execution. This note
complements the [LiDAR paper review](lidar-encoder-bases.md).

## Recommended branch

Use FCOS3D as a small perspective-space detection control, BEVDepth as the
explicit-depth camera-to-BEV baseline, and BEVFormer as the attention/temporal
comparison. Start camera work alongside the first working LiDAR detector;
there is no need to wait for a full SWFormer reproduction. BEVDepth and
BEVFormer are alternative BEV construction mechanisms, not mandatory successive
upgrades of one architecture. Keep the initial comparison single-time-step;
add history in a separate matched-information experiment.

[FCOS3D](https://arxiv.org/html/2104.10956v1) extends a fully convolutional
image detector to predict 3D attributes in perspective space. Its original
experiments use nuScenes. Our Waymo adaptation needs calibrated camera
coordinates, class/size priors, camera-time targets and explicit per-camera
prediction merging. A front-camera pilot can debug depth and orientation;
it is not a full surround-camera benchmark. FCOS3D is a diagnostic baseline,
not a source of shared BEV scene features.

[BEVDepth](https://arxiv.org/pdf/2206.10092) constructs camera BEV features
with learned depth, camera-aware depth prediction, refinement and efficient
pooling. It explicitly supervises depth from projected LiDAR during training;
inference uses cameras. Its original benchmark is nuScenes. This makes it a
useful bridge to LiDAR BEV features, but Waymo conversion is new engineering.
The [authors' implementation](https://github.com/Megvii-BaseDetection/BEVDepth)
uses PyTorch and an older MMDetection3D/CUDA stack. It is reference code, not
a verified current Insula dependency set or ready-made v2 Parquet adapter.

[BEVFormer](https://arxiv.org/pdf/2203.17270) uses calibrated spatial
cross-attention and recurrent temporal attention to construct BEV features.
The paper includes a no-history BEVFormer-S control and Waymo experiments,
but that Waymo protocol evaluates vehicles, filters nonvisible boxes and samples
training frames. Its map experiments do not establish map availability in
Perception v2. Our all-class camera-synchronized protocol differs from those
paper settings; published scores are not acceptance thresholds. Audit image
backbone pretraining and any depth supervision before calling it camera-only
training. Temporal performance requires a matched-history control, not only
comparison to a single-frame model.

## LET is an evaluation reference, not a camera encoder

The [LET paper](https://arxiv.org/pdf/2206.07705), linked by the user's
[Waymo reference](https://waymo.com/research/let-3d-ap-longitudinal-error-tolerant-3d-average-precision-for-camera-only/),
introduces tolerant matching along the sensor line of sight. LET-3D-AP uses
that matching; LET-3D-APL additionally weights precision by longitudinal
affinity. It provides camera-synchronized box labels and compares camera
models including BEVFormer and MV-FCOS3D++. Its tolerance-dependent rankings
do not establish better exact geometry, clearance or driving safety.

For our camera track, freeze the actual evaluator configuration, sensor origin,
IoU/class thresholds, range/visibility selection and longitudinal tolerances.
Report LET-3D-AP and LET-3D-APL together, plus uncorrected longitudinal/lateral
center error and standard 3D detection diagnostics on explicitly matched target
support. Do not increase tolerance after seeing a result. Camera-time targets
and LiDAR-reference targets are separate protocols. Do not subtract scores
computed with different targets or visible-object populations.

Native C++ evaluation remains a candidate TF-free path, with transitive build
closure and configuration parity unverified; see the
[source audit](program-source-audit.md). TensorFlow is not an allowed fallback.

## Information-access table

| Variant | Training sensor evidence | Inference sensor evidence | Purpose |
|---|---|---|---|
| FCOS3D adaptation | Images; permitted labels; audited pretraining | Images | Perspective-space depth/localization control |
| BEVDepth-style adaptation | Images + LiDAR-derived depth targets | Images | Explicit-depth BEV encoding |
| BEVFormer-S adaptation | Images; audited pretraining/targets | Images | Attention-based BEV without memory |
| BEVFormer temporal adaptation | Causal image windows | Causal image windows | Temporal representation comparison |
| LiDAR + camera fusion | LiDAR and images | LiDAR and images | Inference evidence benefit |
| Camera-teacher / LiDAR-student | LiDAR and image teacher | LiDAR | Camera teaching benefit for LiDAR inference |

All supervised detectors also consume task labels during training; this table
separates sensor evidence, not labels. LiDAR-to-camera distillation would be a
separate direction from the existing camera-to-LiDAR hypothesis.

## Shared representation and controls

Define BEV contracts by metric origin, axes, extent, grid resolution, height
handling, time reference and coverage, not merely tensor dimensions. Keep
modality masks and native point identities. Camera BEV is an estimate derived
from pixels, not a measured occupancy grid. Shared feature coordinates do not
remove camera timing, occlusion or depth uncertainty.

For encoder comparisons, keep the detector head and training/evaluation
support fixed where feasible; label adaptations separately from faithful
paper reproductions. For multimodal training, apply joint coordinate/image
augmentation or disable incompatible LiDAR object copy-paste: inserting a
3D object without corresponding image evidence corrupts the fusion control.
Point semantics need a point readout with original measurement identities;
BEV detection heads alone do not establish pointwise semantic accuracy.

## Reference-object extension

[R4D source review](reference-distance-bases.md) adds a separately gated
object-distance relation experiment. Compare identical target proposals and
reference evidence with/without pairwise reasoning. Camera-estimated and
LiDAR-backed references are distinct inference protocols. Long-range labels
require a verified extension; the acquired v2 slice is not proof of availability.
