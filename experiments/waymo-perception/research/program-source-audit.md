# Research program source audit

Checked 2026-09-29 against primary Waymo pages and official source. Source links
below pin the locally recorded upstream revision
`99a4cb3ff07e2fe06c2ce73da001f850f628e45a`; current `master` source was also
read online. This is a contract audit, not evidence of model performance.

## Dataset boundaries and causal inputs

Waymo publishes separate Perception, Motion, and End-to-End Driving datasets.
They need separate adapters and identities, even where protos share definitions.
See the [official overview](https://waymo.com/open/about/) and these schemas:
[Perception Frame][frame], [Motion Scenario][scenario], [E2EDFrame][e2e].
E2EDFrame reuses Frame only for images/calibration/metadata; its context name
identifies a frame. It supplies historical ego states, future targets, intent,
and sparse preference trajectories. It does not imply that ordinary Perception
frames contain planning targets. [E2E schema][e2e]

Modular Perception lacks maps; the official page directs map users to v1.4.2.
The existing local release note identifies v1.4.3 as the current map-bearing
release. Do not infer map availability from v2 keys.
[Official modular-format description][perception]

Motion camera tokens are integer codebook indices, not JPEGs or raw pixels.
Scenario sensor extensions are version-dependent; camera-token and compressed
LiDAR sequences stop at `current_time_index`. Future states are targets, not
inference inputs. Causal feature materialization must enforce that cutoff and
retain validity flags. [Scenario schema][scenario], [camera-token schema][tokens]

## Annotation, taxonomy, and geometry contracts

NLZ is annotation coverage, not a physical obstacle class. Per-point range
channel 3 indicates NLZ membership; evaluation needs prediction overlap with
NLZ points across both returns. The metric Object has a separate
`overlap_with_nlz` field. [Official label/metric guidance][perception],
[metric schema][metrics]

Perception boxes encode sign=3/cyclist=4; Motion tracks encode cyclist=3/other=4.
Camera and LiDAR segmentation own separate semantic enums. Store the source
namespace beside every numeric ID; map through explicit task-specific tables.
[Box types][label], [Motion types][scenario], [LiDAR segmentation enum][seg],
[camera segmentation enum][camseg]

Panoptic instance IDs are image-local; sequence-scoped global mappings are
separate from bounding-box IDs. Preserve sequence ID and trackedness.
Frame time marks the first TOP scan; frame pose is approximately mid-frame and
defines the 3D-label coordinates. Camera pose has its own timestamp and rolling
shutter timing. TOP-only LiDAR segmentation is sparse across frames and can
omit individual points. Missing annotations must remain missing.
[Frame/sensor schema][frame]

## Official evaluation under the no-TensorFlow constraint

The user's no-TensorFlow constraint applies to the whole program, including
evaluation. Importing upstream Python sensor helpers is unsuitable: the cached
`v2/perception/lidar.py` imports TensorFlow. Raw Arrow/NumPy reading can preserve
the source contract without importing that helper.

Official C++ targets exist for detection, tracking, and LiDAR segmentation;
their declared direct dependencies do not list TensorFlow. A C++ Motion metric
library also exists. These are viable candidates for a separate **TF-free**
evaluator, not proof that its entire build/runtime dependency closure is TF-free.
[Official metric libraries][build], [official executable targets][tools]

Use the exact task configuration and release: detection/tracking configuration
includes matchers, difficulty, class IoU thresholds and LET options. Motion
reports minADE, minFDE, miss/overlap rates and mAP/soft mAP, with configured
sampling rates, horizon, K and class filters. Reporting a similarly named local
metric does not establish leaderboard equivalence.
[Detection/tracking schema][metrics], [Motion metric schema][motionmetrics]

**Open gate:** build the selected native evaluator without TensorFlow; inspect
transitive dependencies and runtime imports; run upstream fixtures and fixed
prediction/ground-truth cases; preserve official configuration and NLZ behavior.
Native camera-panoptic and E2E evaluation compatibility was not verified in this
audit. Until these gates pass, mark official metric equivalence unverified and
report local diagnostics under distinct names. No TF-based fallback is allowed.

## Local evidence boundary

The user requests broader research coverage; that request is scope, not proof
that every source family is acquired or processed. The existing
[real-data report](tracer-bullet-e2e.md) establishes a two-context Perception
v2.0.1 slice, structural/payload checks, and sparse-label observations. It
explicitly excludes point reconstruction, motion compensation, model execution
and training. Its unresolved camera-to-LiDAR links cannot be repaired by silently
borrowing another frame's label. Motion/E2E adapters, causal feature tests and
metric equivalence remain program gates; they are not tracer achievements.

[frame]: https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/dataset.proto
[scenario]: https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/protos/scenario.proto
[e2e]: https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/protos/end_to_end_driving_data.proto
[tokens]: https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/protos/camera_tokens.proto
[perception]: https://waymo.com/intl/es/open/data/perception/
[label]: https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/label.proto
[seg]: https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/protos/segmentation.proto
[camseg]: https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/protos/camera_segmentation.proto
[metrics]: https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/protos/metrics.proto
[motionmetrics]: https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/protos/motion_metrics.proto
[build]: https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/metrics/BUILD
[tools]: https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/metrics/tools/BUILD
