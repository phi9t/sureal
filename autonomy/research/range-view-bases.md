# Range-view branch: RSN as a frontend and selection reference

Checked 2026-09-29 against the full [RSN paper](https://arxiv.org/pdf/2106.13365), including Appendices A–C, and [Waymo’s research page](https://waymo.com/research/rsn-range-sparse-net-for-efficient-accurate-lidar-3d-object-detection/). Proposed experiments below are SUREAL adaptations, not published RSN semantic-segmentation results.

## Verified architecture and input scope

RSN uses a lightweight range-image U-Net, predicts foreground, gathers selected points plus range features, dynamically voxelizes them, and applies sparse convolutions with a modified CenterNet head. Foreground targets come from point membership in 3D boxes, trained with focal loss; they are **not scene semantic labels**. CarS/CarL/PedS/PedL use 2D pillars; CarXL uses 3D voxels. Paper experiments use only the long-range TOP LiDAR, **not all five sensors**, and choose the last return when multiple returns exist. Range input is `64×2650` with range/intensity/elongation, clipped/rescaled using maxima `79.5/2/2`. One- and three-frame variants are reported. Temporal branches share weights, encode each native range frame separately, transform gathered points to the current ego frame, and retain per-frame voxel statistics plus timestamp offsets before merging. Online inference caches previous range features and selections. The original implementation explicitly uses **TensorFlow**. [Paper §§3–4, Appendices A–B](https://arxiv.org/pdf/2106.13365).

Waymo’s official page confirms the foreground-selection/sparse-convolution design and CVPR 2021 publication, and links the paper. Its speed and leaderboard statements describe the historical detection experiments; they do not establish current rankings, a full scene semantic model, or a reproducible local runtime. No official source repository or checkpoint was verified in this bounded search. [Waymo research page](https://waymo.com/research/rsn-range-sparse-net-for-efficient-accurate-lidar-3d-object-detection/).

## Where this belongs in the program

Add a **parallel range frontend branch** alongside PointPillars → same pillars with a center head → SWFormer-style sparse attention. RSN addresses a different question: can native angular organization produce useful point features cheaply, and can detection-conditioned point selection reduce downstream work? It should not replace the pillar branch before that question is measured.

Use two explicit outputs from a shared range encoder:

- **Full semantic path:** classify every valid supported return using native semantic labels, preserving background classes such as road, building and vegetation. Gather logits/features back to original point IDs. The detection gate must not control which semantic points receive predictions or supervision.
- **Detection path:** learn a separate box-supervised foreground score, select high-recall points, then gather their range features into a sparse pillar/voxel backend and the shared detection interface. This path can discard likely background because its task is object detection.

This is a multitask extension inspired by RSN, not native RSN scene semantics. The word “semantic features” in the paper describes learned features; it does not imply semantic taxonomy supervision. Keep foreground targets, full semantic labels, valid-return masks and missing-label masks separate. For a shared vehicle/pedestrian/cyclist detector, specify how foreground scores are combined (for example, union of per-class selections); cyclist and multiclass behavior require an extension beyond the paper’s reported vehicle/pedestrian models.

## Concrete sequence

1. **Native range semantic baseline, one frame.** Retain the acquisition grid and implement a modest U-Net with full-resolution semantic logits. Validate point ↔ sensor/return/row/column ↔ XYZ mapping, invalid-pixel masks, beam calibration and motion compensation before learning. Add RGB only in a later fusion experiment. Do not synthesize a range image from aggregated all-sensor XYZ when native grids are available: that introduces collision/quantization changes into the frontend comparison.
2. **Ungated range-to-pillar hybrid.** Gather range features for all valid points and append them to the existing pillar encoder, holding the center head and point/sensor/return scope fixed. Compare against the pillar baseline using the same TOP/last-return subset. This isolates range features from selection and sparse backend changes. Label this a hybrid, not RSN reproduction.
3. **Foreground-gated detection branch.** Add the box-derived gate and sweep thresholds; compare identical downstream models with all points, predicted selection and oracle box selection. Keep full semantic predictions outside the gate. Start with sparse pillars before adding a 3D voxel backend; backend height resolution is a separate ablation.
4. **Three causal frames.** Encode native frames independently, align gathered XYZ/features to the latest ego frame, retain source-frame statistics and time offsets, and cache previous encoder outputs for streaming inference. Ego alignment does not remove moving-object motion. Compare cached streaming latency with cold-start latency and reset caches at scene boundaries.
5. **Expand sensor/return coverage only after the controlled test.** Process each sensor’s native grid separately with an explicit sensor/return schema, then fuse in Cartesian coordinates. Compare TOP last-return, TOP both-returns and all supported sensors under matched configurations. Preserve native semantic-label availability for each return instead of inventing labels for unsupported sensors/returns.

## Selection is a bottleneck to measure

The detector cannot recover information discarded by its gate. Therefore treat foreground recall as a first-class acceptance metric, not merely a segmentation score. Calibrate the threshold using validation data; report per-class point recall, object retention (at least one and at least k retained points), selected-point/voxel counts, and downstream AP/APH, stratified by distance, occlusion and point count. Overall recall can hide distant objects losing their last few points. Pair the oracle-selection upper bound with the all-points control to identify whether a failure is caused by filtering or the backend.

Use the following compact ablations before scaling training:

| Question | Comparison |
|---|---|
| Does range context help? | Raw point features vs added gathered range features, gate disabled |
| Does filtering buy enough speed? | All points vs threshold sweep, fixed backend/head |
| Is selection quality limiting detection? | Predicted vs oracle selection, matched retained-count diagnostics |
| Do detection targets harm semantics? | Full semantics alone vs joint box-foreground/detection/semantics |
| Are gains from extra measurements? | Matched TOP/last-return control, then sensor/return expansion |
| Is time useful? | One vs three frames, matched scope; streaming and cold-start costs |

## TensorFlow-free implementation boundary

Implement the U-Net, masks, feature gathering, semantic head and foreground loss in PyTorch first if minimizing porting risk. A JAX frontend is also feasible; a faithful RSN sparse-convolution backend requires its own supported kernels and dynamic-capacity strategy. RSN’s original TensorFlow implementation is evidence of a porting requirement, not a reason to import TensorFlow into SUREAL. No verified authors’ PyTorch/JAX code should be promised.

Keep ingestion outside the model boundary: the adapter must supply range channels, original point IDs, XYZ, validity, calibrated sensor poses, per-pixel acquisition/motion information where needed, and label masks. Verify that decoding native compressed range records and running official metrics are also TensorFlow-free; using a PyTorch model alone does not guarantee this. If the existing converted representation dropped native grid indices/calibration or return identity, extend that representation before implementing the range model.

Replacing RSN’s sparse convolutions with the existing SWFormer-style backend is a useful SUREAL hybrid and may share its center-head contract, but changes the architecture. Report it separately from faithful RSN. Measure local end-to-end costs, including range decoding, encoder, gathering, gate, backend and head; use the paper’s historical speed claims only as motivation.
