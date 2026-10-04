# SAM integration pathways after separate baselines

Research note, 2026-09-30. Establish independent native-label detection and semantic-segmentation baselines first. The experiments below are proposed extensions, not reported Waymo results or an architecture commitment. No packages, models, or datasets were downloaded or installed for this review.

## What the models actually provide

| Model | Operational prompt and output | Consequence for this program |
| --- | --- | --- |
| SAM | Released inference accepts spatial points, boxes, or masks and returns class-agnostic masks; automatic generation samples prompts. | A detector can supply both a box prompt and class identity. An automatic mask has no native semantic class. |
| SAM 3 | Concept segmentation accepts noun phrases or visual exemplars and finds matching instances; spatial interaction is a separate mode. Video adds tracked identities. | Evaluate concept discovery separately from matched detector-box mask refinement. Video identities are not cross-camera or 3D identities. |

SAM uses a cached ViT image embedding, prompt encoding, and a lightweight mask decoder, with multiple candidate masks for ambiguous prompts. Its SA-1B masks do not carry category names. The paper's preliminary text experiment should not be confused with the released standard API. Detector-box-to-mask composition is already demonstrated in the paper. [SAM paper](https://arxiv.org/html/2304.02643), [official repository](https://github.com/facebookresearch/segment-anything).

SAM 3 combines a concept-conditioned detector, mask prediction, and a memory-based tracker. A presence head separates whether a concept exists from individual localization confidence. It also has a **binary, prompt-conditioned semantic head**; this is not a mutually exclusive Waymo semantic taxonomy. A positive exemplar box can request *all matching objects*, unlike a spatial prompt selecting one instance. Its staged training separates detector and tracker training. [SAM 3 paper](https://arxiv.org/html/2511.16719).

The builder exposes interactive instance mode through `enable_inst_interactivity`, disabled by default. Select and verify that mode for a fair SAM-versus-SAM-3 box-prompt experiment; do not substitute concept exemplars without changing the experiment's name and controls. [SAM 3 model builder](https://github.com/facebookresearch/sam3/blob/main/sam3/model_builder.py).

## Bounded experiment sequence

1. **Frozen mask refinement.** Feed identical predicted 2D boxes to SAM and SAM 3's spatial mode; preserve the detector's class and score. Compare raw box support, each model's masks, and the native segmentation baseline. Count missed detector objects and false prompts in end-to-end evaluation; matched-object quality alone hides detection failure. Ground-truth boxes belong only in a separately reported oracle upper bound.
2. **Concept discovery.** Run SAM 3 independently with a fixed, validation-selected set of class phrases or exemplars. Compare discoveries against the detector rather than silently merging them. Specify how phrases map to the native taxonomy, how overlapping concept masks resolve, and when ambiguous pixels remain unknown. Broad detection classes cannot supply finer semantic identities without additional evidence. Never label every unclassified SAM mask as a native class or every uncovered pixel as background.
3. **Geometry-aware transfer.** Attach image masks to visible calibrated LiDAR points, or lift them with a fixed predicted depth source. Compare the same depth and association rules with boxes versus masks. Test mask boundaries and uncertainty before adding temporal or multi-camera association.
4. **Offline distillation.** Generate teacher artifacts only for the training split; train a native-label student with a separate auxiliary loss and confidence/visibility gating. Compare native supervision alone, extra teacher supervision, and compute/data-matched controls. Preserve supervision for the full semantic scene, including areas outside object masks. Teacher confidence is not a correctness guarantee.
5. **Joint training only after evidence.** Compare separate students against a shared detector/semantic encoder without SAM first, then add mask distillation or trainable adapters. Hold labels, sampling, optimization budget, and depth source constant. Report task interference and inference cost. A frozen teacher, a fine-tuned teacher, and a jointly optimized student are different treatments.

This sequence tests complementary information rather than assuming two foundation segmenters should be stacked. Simple detector prompting or projecting masks into 3D is not itself a novelty claim. A research hypothesis would be that calibrated visibility, class compatibility, and geometric uncertainty make mask transfer improve sparse or distant native-label predictions.

## Geometry and label contract

A 2D mask defines camera rays, not metric distance, object centers, occluded shape, or a 3D box. For LiDAR transfer, project timestamp-aligned points with the correct camera model and extrinsics; handle rolling shutter, image transforms, occlusions, and competing surfaces. A point behind a foreground mask is not automatically part of that object. Gate associations by visibility and depth consistency; keep conflicts unknown. Multi-camera masks need explicit geometric association before sharing identities.

Camera-only lifting must use a declared predicted depth source and propagate its uncertainty. Optical-axis depth and radial range are different quantities. Ground-truth depth is an oracle; measured LiDAR at inference makes the method multimodal. Keep these conditions separate from camera-only comparisons. See [geometry source audit](geometry-foundation-sources.md) and [camera bases](camera-encoder-bases.md).

Store teacher/checkpoint version, prompt origin, prompt mode, class mapping, mask confidence, image-coordinate transform, camera/time, association identity, depth source, and visibility decisions with each artifact. Keep teacher pseudo-labels distinct from native labels. Derive point labels only where native supervision and sensor coverage allow evaluation; never promote mask identities directly into Waymo semantic ground truth.

## Training and runtime constraints

The official SAM implementation is PyTorch, with Python >=3.8, PyTorch >=1.7 and torchvision >=0.8; CUDA is strongly recommended. Its ONNX export covers the lightweight mask decoder, not the complete image pipeline. Budget image encoding and all camera prompts in end-to-end timing. [SAM repository](https://github.com/facebookresearch/segment-anything).

SAM 3 currently documents Python >=3.12, PyTorch >=2.7 and a CUDA GPU with CUDA >=12.6. Checkpoint access requires approval and authentication. The repository now also includes SAM 3.1 Object Multiplex: pin the code and checkpoint, and treat 3.1 as a separate version, especially in tracking cost comparisons. No checkpoint access or local performance was verified here. [SAM 3 repository](https://github.com/facebookresearch/sam3).

Official SAM 3 fine-tuning configurations exist, but a Waymo training adapter and its label contract still need implementation. Neither cited repository establishes a supported JAX implementation. PyTorch is the verified implementation route; these models do not require adopting TensorFlow, while the complete data/geometry adapter still needs its own dependency audit. [SAM 3 training instructions](https://github.com/facebookresearch/sam3/blob/main/README_TRAIN.md).

Joint training requires explicit differentiable paths: inference wrappers, hard prompt selection, thresholding, NMS, and discrete assignments do not provide an automatic gradient path. Begin with detached teacher targets; make any trainable encoder/decoder or prompt adapter an explicit ablation. Avoid claiming that calling the public predictor jointly trains detector and segmenter. [SAM predictor source](https://github.com/facebookresearch/segment-anything/blob/main/segment_anything/predictor.py).

Measure native class mIoU and detection AP/APH alongside prompt coverage, mask quality, false discovery, and class conflicts. Stratify distance, occlusion, thin objects, and lighting. For temporal tests, distinguish causal past-only tracking from offline propagation using future frames. Report encoder, prompt/query processing, memory, transfers, and all cameras in latency and peak-memory measurements; browser decoder timing is not a full perception-system benchmark.

## Pinned preprocessing preparation (2026-10-01)

Official SAM commit `dca509fe793f601edb92606367a655c15ac00fdf` is pinned. `research/sam-transform-verified.json` records live execution of its exact ResizeLongestSide source: PIL image resize parity, rounded native dimensions and separate actual width/height prompt scaling. The 1280×1920 example resizes to683×1024; do not reuse a generic half-pixel prompt transform. Torchvision CPU NMS actually executes in the locked runtime. The Torch image path remains distinct from the PIL image path expected by the model, as stated in the [pinned upstream transform](https://github.com/facebookresearch/segment-anything/blob/dca509fe793f601edb92606367a655c15ac00fdf/segment_anything/utils/transforms.py). Official ViT-B checkpoint HEAD is accessible and declares375,042,383B; no checkpoint has been acquired and no SAM image inference has been run. `research/sam-source-access-observation.json` records access metadata only.

## First native teacher execution (2026-10-01)

`research/sam-native-image-independent-verified.json` records official SAM ViT-B93,735,472-parameter frozen inference on a native1280×1920 engineering camera image with three explicitly tagged native-camera-box oracle prompts. Public checkpoint SHA256 `ec2df62732614e57411cdcf32a23ffdf28910380d03139ee0f4fcbe91eb8c912`, code commit `dca509fe793f601edb92606367a655c15ac00fdf`, all retained artifacts and current source hashes agree. Independent CPU low-resolution upsample/crop/native-resize/threshold reproduces all original-image mask pixels. Model load1.114s, image encoding0.401s, batched decode0.085s, peak allocated GPU2,905,302,528B, zero optimizer updates. This accepts frozen teacher engineering execution only. Predicted camera prompts, calibrated visibility, point-semantic support transfer, held-out comparisons and SAM3 access remain open.
