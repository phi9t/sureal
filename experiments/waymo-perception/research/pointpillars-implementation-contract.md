# PointPillars implementation contract for native Waymo points

Date: 2026-09-30. Preparation only; no upstream installation, training,
checkpoint download, or ticket closure. Ticket 10 remains blocked by scientific
protocol 07. This note aligns with the program's independent detection baseline,
geometry convention, and subsequent controlled center-head bridge.

## Source identity and recommended route

The [PointPillars paper, v2](https://arxiv.org/html/1812.05784v2) explicitly links
the authors' `nutonomy/second.pytorch` repository. It describes XY pillars,
learned point features, a 2D backbone and an SSD-style box head. Its experimental
contract is KITTI, with image-visible points, separate car and pedestrian/cyclist
networks, and KITTI difficulty/AP/AOS evaluation. Our Waymo experiment changes
dataset, supervision, classes, geographic coverage and evaluator; it must be
called a PointPillars adaptation, not a reproduction of its published scores.

Source pin verified using `git ls-remote ... HEAD`:
`449c7c0d081eaad44f08159f64af26d2a59f1f4c`. All code links below use this immutable
revision. Recommend a small native Torch implementation of the inspected
mathematical contract, with NumPy/Arrow acquisition and the already verified
native evaluator. Do not run this old repository's complete environment or
convert Waymo into KITTI coordinates merely to fit its loader.

## Encoder: exact source-compatible core

[PillarFeatureNet and PFNLayer](https://github.com/nutonomy/second.pytorch/blob/449c7c0d081eaad44f08159f64af26d2a59f1f4c/second/pytorch/models/pointpillars.py)
define the following recipe:

- For each nonempty XY cell, retain points `(x,y,z,r)` and append three offsets
  from that pillar's XYZ arithmetic mean and two offsets from its metric XY
  cell center. This is nine channels. `with_distance=false` excludes an optional
  Euclidean-distance channel. There is no independent height bin.
- A single final PFN layer maps 9→64 using a bias-free linear layer,
  BatchNorm1d (`eps=1e-3`, `momentum=0.01`), ReLU, and a maximum **over points**.
  The result is one 64-vector per pillar, not a maximum over feature channels.
- Padded point decorations are zeroed before the PFN. Upstream BN sees padded
  slots, and padding is not remasked after BN/ReLU. An implementation that masks
  only valid points during BN or max is a potentially useful deviation, not exact
  source compatibility. Freeze padding policy and test it explicitly.
- Scatter uses coordinate order `[batch,z,y,x]`, flattened index `y*nx+x`, and
  produces `[batch,64,ny,nx]`, with zero empty cells. Preserve singleton dimensions:
  upstream's unrestricted `squeeze()` should not become a one-pillar shape bug.

For native Waymo, use compensated vehicle-reference XYZ and the native physical
intensity channel as the declared analogue of reflectance. This does not assert
that Waymo intensity has KITTI reflectance's distribution. Initially exclude
elongation to retain the nine-channel contract; adding it is a separately named
feature ablation. Neither NLZ status, semantic labels, box IDs, point counts in
boxes, nor difficulty metadata enters the encoder.

Keep original `(segment, timestamp, laser, return, row, column)` in a sidecar
through range validity filtering, ROI clipping and sampling. Both returns and
the chosen sensor inventory must be identical across encoding comparisons.
Declare finite half-open ROI bounds, random sampling seed/order, maximum pillars
and points, clipped-point counts, and retained source identities. A single
vertical extent is an ROI constraint; it is not height-binned voxelization.
Current-frame observations are the initial contract; temporal aggregation is
a later controlled change. These are project recommendations, not upstream
Waymo functionality.

## Backbone, neck and anchor head

The pinned [car 0.16 m config](https://github.com/nutonomy/second.pytorch/blob/449c7c0d081eaad44f08159f64af26d2a59f1f4c/second/configs/pointpillars/car/xyres_16.proto)
and [RPN implementation](https://github.com/nutonomy/second.pytorch/blob/449c7c0d081eaad44f08159f64af26d2a59f1f4c/second/pytorch/models/voxelnet.py)
specify stage channels `[64,128,256]`, incremental strides `[2,2,2]` and
`layer_nums=[3,5,5]`. The initial strided convolution is additional, giving
4/6/6 convolutions per stage. It uses explicit zero-padding before each first
strided 3×3 convolution, then normalization/ReLU. Transposed-convolution strides
`[1,2,4]` each output 128 channels; all reach stride 2 and concatenate into 384
channels. Normalization uses the same epsilon/momentum as PFN. The dense head
predicts sigmoid class logits, seven residuals and two direction logits for each
anchor. Do not mistake this for a center-based heatmap head.

Code-compatible anchor assignment uses
[NearestIouSimilarity](https://github.com/nutonomy/second.pytorch/blob/449c7c0d081eaad44f08159f64af26d2a59f1f4c/second/core/region_similarity.py):
convert rotated BEV rectangles to their nearest axis-aligned representation and
compute axis-aligned IoU. This is distinct from exact rotated IoU and from full
3D evaluation IoU. [Target assignment](https://github.com/nutonomy/second.pytorch/blob/449c7c0d081eaad44f08159f64af26d2a59f1f4c/second/core/target_ops.py)
marks anchors at/above the positive threshold positive, below the negative
threshold negative, and the gap ignored. Tied best-overlap anchors are forced
positive; zero-best-overlap GT is excluded from that forcing. With no GT all
eligible anchors become background. The negative overwrite is followed by
reinstatement of forced matches. Config disables positive-fraction subsampling.
Any occupancy-based anchor pruning also needs an explicit contract; the pinned
config has `anchor_area_threshold=1`.

The pinned car anchors use width/length/height `[1.6,3.9,1.56]`, rotations
`[0,1.57]`, and positive/negative thresholds `.6/.45`. Its ROI is
`[0,-39.68,-3,69.12,39.68,1]`; anchor stride is `.32` and offset
`[.16,-39.52,-1.78]`. These are source values, not suitable defaults for Waymo.
Upstream [box coding](https://github.com/nutonomy/second.pytorch/blob/449c7c0d081eaad44f08159f64af26d2a59f1f4c/second/core/box_coders.py)
and its backing box operations must be checked together when porting bottom-Z
storage to Waymo center-Z. Never silently interpret the anchor offset as center-Z.
The paper's car ROI, height and reported center-Z differ from this config.

## Losses, decoding and inference

Follow [voxelnet loss/decoding](https://github.com/nutonomy/second.pytorch/blob/449c7c0d081eaad44f08159f64af26d2a59f1f4c/second/pytorch/models/voxelnet.py)
and [loss kernels](https://github.com/nutonomy/second.pytorch/blob/449c7c0d081eaad44f08159f64af26d2a59f1f4c/second/pytorch/core/losses.py):
XY residuals normalize by the anchor width/length diagonal, Z by anchor height,
and dimension residuals use logarithmic ratios. Store additive yaw residuals;
the regression comparison uses sine-difference encoding. Predicting `asin` of
a sine target is not equivalent to the source decoder. Direction targets use
the sign of reconstructed GT yaw, and inference adds π when the predicted sign
disagrees with the direction bin. Canonicalize final yaw at the Waymo boundary.

Use sigmoid focal classification (`alpha=.25`, `gamma=2`), seven-coordinate
weighted SmoothL1 (`sigma=3`, equal code weights), and two-class direction CE.
Weights are localization 2, classification 1, direction .2. Positive counts
normalize each sample, clamped to at least one; box and direction losses apply
only to positives, classification excludes ignored anchors. Define the all-empty
batch case before training. The sine comparison must be checked on wrap-boundary
and π-flipped boxes independently of the direction CE.

Pinned inference uses axis-aligned enclosing-rectangle NMS, IoU .5, score floor
.05, pre-NMS 1000 and post-NMS 300; it chooses the highest class score per box
when multiclass NMS is disabled. The Waymo adaptation must preregister whether
to retain this class-agnostic behavior or use per-class NMS. Changing to rotated
NMS, class-specific heads, anchor dimensions or class counts changes the contract.
The config's Adam schedule begins at `.0002`, exponential factor `.8`, weight
decay `.0001`, and a KITTI-specific fixed-step schedule. Its step counts must not
be copied to a different scene/frame cohort without explicitly defining updates
and total budget.

## TensorFlow assessment and implementation boundaries

Static inspection of all `.py` files at the pin found no `import tensorflow` or
`from tensorflow` statements. Matches were comments/docstrings plus the Torch
trainer's [tensorboardX SummaryWriter](https://github.com/nutonomy/second.pytorch/blob/449c7c0d081eaad44f08159f64af26d2a59f1f4c/second/pytorch/train.py).
TensorFlow-author copyright headers and `.tfrecord` strings in configs are not
proof of a runtime TensorFlow dependency. This is a source-inspection finding,
not a resolved transitive-dependency or modern B200 compatibility claim.
Historical compiled operations and the old environment remain unverified.

A faithful new Torch core avoids importing the whole legacy package: implement
the inspected PFN/scatter/backbone/anchor math, reuse project-native measured
point records and native evaluator exports, and provide separately verified
IoU/NMS kernels. If source is copied rather than reimplemented, retain applicable
MIT/Apache notices. Dependency closure and absence of TensorFlow still require
a live dedicated Insula check; this research note does not supply that proof.

## Decisions required before execution and acceptance evidence

Freeze train/development/held-out scenes, sensor/return inventory, ROI and pillar
caps, class mapping (Waymo vehicle is broader than KITTI car; sign is additional),
training-only anchor estimates, assignment thresholds, intensity normalization,
augmentation policy, padding, pruning, NMS, update budget and checkpoint selection
under ticket 07. GT-object database augmentation, if used, must source only training
scenes and carry provenance; removing it is a documented adaptation. Do not choose
anchors or hyperparameters from held-out performance.

Before ticket 10 closes, live Insula must verify exact decoration values, padding
and singleton behavior, permutation invariance when sampling is absent, scatter
index orientation, anchor/box encode-decode and yaw wrap, assignment thresholds
and ties/no-overlap/no-GT cases, positive-count normalization, and deterministic
NMS ties. Then require finite forward/backward, the preregistered tiny training-only
overfit target, independent export checks, held-out per-seed AP/APH and distance
errors, uncertainty, and complete acquisition/preprocessing/training/inference
resource accounting. Fixtures establish correctness, not scientific improvement.

Preserve the anchor-head reference first. The program's pillar+CenterPoint bridge
changes targets, assignment, heading representation, losses and decoding; name
it separately. Compare heads while holding pillar inputs/backbone fixed, then
hold the center-head contract fixed for SWFormer/RSN representation comparisons.
A common-head hybrid is not a faithful full-model reproduction of either paper.
