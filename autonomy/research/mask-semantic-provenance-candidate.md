# Candidate semantic provenance for box/mask-to-point comparisons

Preparation, 2026-09-30. Not frozen under ticket 07 and not an implementation or model result.

The primary point comparison retains native LiDAR IDs 1–22 and identical valid labeled TOP points for B0/B1/B2. Ground-truth semantic support decides evaluation eligibility only. A camera prediction cannot narrow that support or choose which classes count.

## Information contract

The native 2D detector supplies spatial prompts, box class and confidence. Its coarse vehicle class does not supply a fine car/truck/bus/other-vehicle semantic label. SAM supplies spatial support, not an independently supervised native semantic category. Therefore the same frozen predicted camera semantic head supplies fine semantic evidence for all three support treatments. Its training and checkpoint provenance belong to ticket 14. Pooling/candidate selection thresholds must be frozen using training/development data, without accessing held-out camera or point labels.

Each predicted prompt retains two different namespaces: detector box class and camera semantic distribution. Do not overwrite one with the other. Native object IDs and panoptic IDs remain separate. Predicted fine categories must be compatible with the prompt category under a declared compatibility table; conflicts abstain with a reason.

B0 rectangle, B1 SAM and B2 SAM 3 consume identical detector prompts and predicted semantic evidence. The only changed evidence is spatial support. A frozen independent LiDAR segmentation prediction provides the full-scene fallback in all three treatments. A transfer can replace that prediction only where projection/visibility, unique semantic mapping and conflict rules pass. Unknown or ambiguous camera semantics preserve the fallback; their points remain in the primary metric. This makes the research question a controlled point-semantic refinement study rather than a score measured only on successful camera prompts. Report a transfer-only diagnostic separately, including abstentions; do not replace the full-support primary result with it.

## Mapping constraints from pinned schemas

Inspected local upstream revision `99a4cb3ff07e2fe06c2ce73da001f850f628e45a`:

- [Camera taxonomy](https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/protos/camera_segmentation.proto)
- [LiDAR taxonomy](https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/protos/segmentation.proto)

Names and numeric IDs differ. Examples: camera car 2 → LiDAR car 1; camera truck 3 → LiDAR truck 2; camera pedestrian 9 → LiDAR pedestrian 7. These are candidate category correspondences, not proof of identical physical annotation boundaries.

A conservative mapping must retain ambiguity: camera vegetation 24 includes tree trunks, which LiDAR separates into vegetation 15 and tree trunk 16; camera sidewalk 23 includes curbs, which LiDAR separates into curb 17 and sidewalk 22. Camera trailer, ego vehicle, animals, pedestrian-associated objects, sky and generic dynamic/static labels must not be silently assigned to a convenient LiDAR class. The complete versioned correspondence/abstention table remains to be reviewed and frozen. Undefined predictions do not become a background class in LiDAR supervision.

## Required live verifiers and acceptance

Before scientific promotion, independently verify that swapping a coarse box class or an ambiguous semantic category cannot manufacture a fine label; held-out annotation injection into predicted semantic evidence is refused; fallback predictions and original point keys are identical across treatments; all eligible native classes and points remain in the primary confusion matrix; camera-only support and transfer eligibility are reported independently. Trace each transferred prediction to image hash, predicted prompt, semantic-head checkpoint, segmenter checkpoint, mapping revision and calibrated measured point.

Freeze semantic pooling, confidence, compatibility, ambiguous-class abstention, fallback and overlap arbitration before examining mask comparison results. Verify the complete pipeline live inside the locked GPU Insula, then report paired whole-segment uncertainty and full detector/semantic-head/segmenter/transfer costs. Positive camera-mask scores alone do not establish improved point semantics.

A [live candidate mapping fixture](semantic-mapping-candidate-verified.json) now verifies conservative label/fallback behavior. The implementation retains ambiguity for camera sidewalk, vegetation and generic ground. Interface origin declarations reject explicit annotations and coarse boxes; independent checkpoint/data provenance still requires the complete task pipeline. This preparation does not freeze the correspondence table or close tickets 17/18.
