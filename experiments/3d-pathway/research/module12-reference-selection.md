# Module 12 maintained-reference selection

**Decision (research recommendation; historical cutoff 2026-09-25): land
VGGT's feed-forward core first, with optimization disabled, pinned to upstream
commit
[`a288dd0f14786c93483e45524328726ab7b1b4ce`](https://github.com/facebookresearch/vggt/tree/a288dd0f14786c93483e45524328726ab7b1b4ce)
and the original `facebook/VGGT-1B` Hub revision
[`860abec7937da0a4c03c41d3c269c366e82abdf9`](https://huggingface.co/facebook/VGGT-1B/tree/860abec7937da0a4c03c41d3c269c366e82abdf9).**
Lock `model.safetensors` at SHA-256
`f164acf60724910d8fe1578bb499d800850c7bb0948db7555c413f9fbe60467e`
(5,026,367,224 bytes) and `config.json` at SHA-256
`a73e929a168b900546a84fe88cd70dfaaf2f8e39cf77355b12984eaa686f3855`.
Those exact bytes are already recorded in this repository's
[model lock](../../photoreal-scenes/model.lock.json), Surflo already vendors
and freezes a VGGT backbone, and an actual B200 scout has exercised the same
depth, camera, and pointmap path ([Surflo integration](../../../surflo/model/ffm.py),
[scout record](../../insula-scout/results.json)).  The scout does not itself
bind that run to the separate model lock; the exact-pin rerun required below is
therefore still a completion gate.

This is a **scientific reference**, not approval to redistribute or use the
weights commercially.  The selected original checkpoint is CC BY-NC 4.0, while
the current source is under Meta's custom VGGT licence and acceptable-use
policy
([checkpoint card](https://huggingface.co/facebook/VGGT-1B/blob/860abec7937da0a4c03c41d3c269c366e82abdf9/README.md),
[source licence](https://github.com/facebookresearch/vggt/blob/a288dd0f14786c93483e45524328726ab7b1b4ce/LICENSE.txt)).
The separately trained `VGGT-1B-Commercial` checkpoint is gated and has
different bytes and terms; it must be a separate adapter/result ID after the
user accepts those terms, not a silent replacement.  `DA3-BASE`, whose source
and model card both say Apache-2.0, is the **permissive fallback** when the VGGT
terms are unacceptable.  It predicts depth and cameras but not VGGT-style
tracks, and its pointmap must be formed by unprojection, so it is not a
drop-in-equivalent result.

The selected default is `vggt/direct`: one feed-forward pass followed only by
deterministic pose decoding and depth unprojection.  VGGT's optional
PyCOLMAP bundle adjustment, DUSt3R global alignment, and MASt3R sparse global
alignment remain explicitly named `optimization=on` follow-on interventions,
not implicit steps in this first direct-only adapter. They must receive
separate adapter/result IDs before execution and must never be included in the
direct runtime or accuracy result. This
preserves Module 12's amortized-inference claim while making the curriculum's
“alignment retained or removed” distinction enforceable
([curriculum entry](../curriculum.json)).

## Status and scope

The official name is **Depth Anything 3**, abbreviated **DA3** by its authors.
It first appeared as arXiv `2511.10647` in November 2025 and was a published
ICLR 2026 conference paper by the cutoff, so a source label such as
“DA3 2025” identifies the preprint year rather than its final venue
([arXiv record](https://arxiv.org/abs/2511.10647),
[ICLR paper](https://openreview.net/pdf/9d69fc515ade062e6a76a0e4c7e6835ad3e21402.pdf)).
It is not the same model as the monocular Depth Anything or Depth Anything V2.

All four methods estimate **visible, image-indexed geometry under learned
priors**.  A predicted point behind no observed pixel, a watertight surface,
and correct unseen-side completion are not guaranteed outputs.  “Pointmap”
means one 3D vector per image pixel with a declared coordinate frame; it does
not by itself mean a mesh, a projectively exact camera, metric scale, or a
single globally consistent surface.  The adapter must preserve that narrower
meaning.

VGGT's original repository announced VGGT-Omega as its successor in May 2026,
but Omega is a different source/checkpoint family and is not one of the four
Module 12 sources.  The original VGGT repository nevertheless received the May
2026 memory fix, training code, and current licence, so it remains a maintained
and considerably lower-integration-risk reference at the cutoff
([official update log](https://github.com/facebookresearch/vggt/blob/a288dd0f14786c93483e45524328726ab7b1b4ce/README.md#updates)).

## Pointmaps, cameras, depth, and gauge

### DUSt3R: pairwise pointmap regression plus optional global alignment

For images `I1` and `I2`, DUSt3R regresses dense pointmaps `X^{1,1}` and
`X^{2,1}` plus positive confidence maps.  Both pointmaps are expressed in
camera 1's coordinate frame; `X^{n,m}` means points observed by camera `n`
expressed in camera `m`'s frame.  The output retains the pixel-to-point
correspondence but the architecture imposes no explicit projective-camera
constraint, so a raw pointmap need not be exactly explainable by one pinhole
camera
([CVPR 2024 paper, Section 3](https://openaccess.thecvf.com/content/CVPR2024/papers/Wang_DUSt3R_Geometric_3D_Vision_Made_Easy_CVPR_2024_paper.pdf),
[official output contract](https://github.com/naver/dust3r/blob/4c24a6ebf04809f2cfe59915e51779c8984aaa40/README.md#usage)).

Pairwise scale is not metric.  Training divides prediction and ground truth by
their respective mean valid-point distance to the origin, then applies a
confidence-weighted regression loss of the form `C * l_reg - alpha * log C`.
Depth can be read as camera-frame `z`; focal length is fitted under a centered
principal-point/square-pixel model, and relative pose can be recovered by
Procrustes or PnP.  These are derived estimates, not extra network outputs
([paper, Sections 3.2–3.3](https://openaccess.thecvf.com/content/CVPR2024/papers/Wang_DUSt3R_Geometric_3D_Vision_Made_Easy_CVPR_2024_paper.pdf)).

For more than two views, official DUSt3R builds an image-pair graph and can
optimize a common pointmap per image together with per-edge rigid transforms
and scales.  A camera-aware variant constrains the common pointmaps to depths
and pinhole cameras.  The implementation initializes from a minimum spanning
tree and the official example runs 300 optimization iterations; an explicit
scale constraint fixes the otherwise free global gauge
([global-aligner example](https://github.com/naver/dust3r/blob/4c24a6ebf04809f2cfe59915e51779c8984aaa40/README.md#usage),
[optimizer source](https://github.com/naver/dust3r/blob/4c24a6ebf04809f2cfe59915e51779c8984aaa40/dust3r/cloud_opt/optimizer.py)).
Consequently `dust3r/pair` and `dust3r/global` are different inference modes.
Only the former is purely amortized.

### MASt3R: DUSt3R geometry with learned matching

MASt3R keeps DUSt3R's pairwise `X^{1,1}` and `X^{2,1}` convention and adds a
24-dimensional, unit-normalized descriptor at every pixel plus descriptor
confidence.  It trains the descriptors with a matching loss and uses fast
reciprocal nearest-neighbour and coarse-to-fine matching, addressing a task at
which raw 3D-point proximity is weak
([ECCV 2024 paper, Sections 3–4](https://arxiv.org/pdf/2406.09756),
[model source](https://github.com/naver/mast3r/blob/f5209afc300cec36239a7ac992263f36847bbba0/mast3r/model.py)).

“Metric pointmaps” needs a narrow interpretation.  When metric ground truth is
available, MASt3R trains the prediction against the ground-truth normalization
instead of independently removing predicted scale; nonmetric training samples
remain scale invariant.  A metric-named checkpoint therefore learns an
absolute-scale prior but does not turn arbitrary Internet imagery into
calibrated metrology.  The Hub card for the metric repository is internally
inconsistent: its model table and loading example name the **nonmetric** model
([pinned card](https://huggingface.co/naver/MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric/blob/06e7259f34c3060f322df5cb0c7b9094f57e41fc/README.md)).
The adapter must trust its locked repository/config/weight identity, validate a
known-scale scene, and record the observed scale behavior rather than infer it
from the repository name.

The original MASt3R paper evaluates binocular matching and explicitly does not
run DUSt3R global alignment.  The maintained repository now also contains
MASt3R-SfM's `sparse_global_alignment`: forward MASt3R, establish matches,
perform a coarse 3D optimization, refine 2D reprojection, and triangulate.  Its
defaults use 300 coarse and 300 refinement iterations and may optimize focal,
principal point, per-image scale/depth, and poses
([MASt3R-SfM paper](https://openreview.net/attachment?id=5uw1GRBFoT&name=pdf),
[pinned sparse optimizer](https://github.com/naver/mast3r/blob/f5209afc300cec36239a7ac992263f36847bbba0/mast3r/cloud_opt/sparse_ga.py#L119-L207)).
This is a useful retained-optimization comparison, not the feed-forward
default.  The repository labels its GLOMAP and kapture mapping scripts as toys
or not thoroughly tested; they are not maintained reference paths
([official README](https://github.com/naver/mast3r/blob/f5209afc300cec36239a7ac992263f36847bbba0/README.md)).

### VGGT: joint amortized cameras, depth, pointmaps, and tracks

VGGT accepts `[S,3,H,W]` or `[B,S,3,H,W]` RGB tensors in `[0,1]`.  Its direct
forward returns:

- `pose_enc [B,S,9]` and its iterative estimates;
- `depth [B,S,H,W,1]` plus depth confidence;
- `world_points [B,S,H,W,3]` plus point confidence; and
- when pixel queries are supplied, `track [B,S,N,2]`, visibility, and track
  confidence.

These are the exact maintained implementation shapes
([forward contract](https://github.com/facebookresearch/vggt/blob/a288dd0f14786c93483e45524328726ab7b1b4ce/vggt/models/vggt.py#L29-L91)).
The implementation's pose encoding is `[T_x,T_y,T_z, quaternion(4),
FoV_h,FoV_w]`, even though abbreviated prose may write `(q,t,f)`.
Decoding produces `3x4` **world-to-camera** `[R|t]` extrinsics in OpenCV axes
(`x` right, `y` down, `z` forward), pixel intrinsics, and a principal point
fixed at image center
([pose conversion](https://github.com/facebookresearch/vggt/blob/a288dd0f14786c93483e45524328726ab7b1b4ce/vggt/utils/pose_enc.py#L11-L120)).
Depth is camera `z`; unprojection inverts each world-to-camera transform to
produce shared-world points
([geometry source](https://github.com/facebookresearch/vggt/blob/a288dd0f14786c93483e45524328726ab7b1b4ce/vggt/utils/geometry.py#L15-L115)).

The paper trains cameras, depths, and pointmaps in a first-camera reference
frame after scene-scale normalization.  The first input image is therefore the
semantic reference and the remaining input order is permutation equivariant.
The global scale is learned/nonmetric.  Moreover, the network regresses this
gauge; a direct forward does not algebraically overwrite the first camera with
identity or renormalize every output.  The adapter must record the realized
first-camera residual and must not silently apply a similarity transform before
writing raw artifacts
([CVPR 2025 paper, Sections 3–4](https://openaccess.thecvf.com/content/CVPR2025/papers/Wang_VGGT_Visual_Geometry_Grounded_Transformer_CVPR_2025_paper.pdf)).

VGGT exposes two dense geometry routes.  The direct point head predicts
`world_points`; the authors say that unprojecting the predicted depth with the
predicted cameras usually gives more accurate points, and their ETH3D results
support that recommendation
([official example](https://github.com/facebookresearch/vggt/blob/a288dd0f14786c93483e45524328726ab7b1b4ce/README.md#detailed-usage)).
The selected canonical pointmap is therefore `unproject(depth, K, w2c)`.
Save the direct point-head output separately as `pointmap_direct` so head
disagreement remains measurable rather than discarded.

Official `demo_colmap.py` optionally predicts tracks with the VGGSfM tracker,
constructs a PyCOLMAP reconstruction, and runs bundle adjustment.  It still
contains TODOs for masks, iterative BA, radial distortion, more testing, and
more camera types
([pinned BA path](https://github.com/facebookresearch/vggt/blob/a288dd0f14786c93483e45524328726ab7b1b4ce/demo_colmap.py#L35-L60),
[bundle-adjustment call](https://github.com/facebookresearch/vggt/blob/a288dd0f14786c93483e45524328726ab7b1b4ce/demo_colmap.py#L142-L193)).
That path is `vggt/ba`, not part of `vggt/direct`.

### Depth Anything 3: depth-ray geometry with optional pose conditioning

DA3 takes any number of images and optionally known intrinsics and extrinsics.
Its core representation predicts depth `D` and, for every pixel, a ray with
world-space origin `t` and unnormalized direction `d = R K^-1 p`; the world
point is `P = t + D d`.  Camera parameters can be recovered from ray maps, and
a lightweight camera decoder provides a faster default pose route.  The plain
transformer alternates within-view and cross-view attention and a Dual-DPT
head jointly predicts depth and rays
([ICLR 2026 paper, Sections 3–4](https://openreview.net/pdf/9d69fc515ade062e6a76a0e4c7e6835ad3e21402.pdf)).

Like the other any-view models, the standard DA3 series is relative-scale.
Training normalizes all ground-truth views with a common mean norm of valid
reprojected points.  `DA3METRIC-LARGE` is monocular metric depth, while the
Nested series combines an any-view model with a metric model to scale the
scene; only those declared variants may emit `is_metric=true`
([model table](https://github.com/ByteDance-Seed/Depth-Anything-3/blob/3d835ec1a5802d64a8b8b15f817a1ab54809bfe4/README.md#model-cards)).

The maintained high-level API defaults to a 504-pixel upper-bound resize,
`use_ray_pose=False`, and `ref_view_strategy="saddle_balanced"` for at least
three images.  Supplying poses causes the API to normalize them to the first
camera and by median camera distance.  It then aligns prediction to the inputs
with Umeyama; with `align_to_input_ext_scale=True`, it replaces the output poses
with the inputs and rescales depth
([API source](https://github.com/ByteDance-Seed/Depth-Anything-3/blob/3d835ec1a5802d64a8b8b15f817a1ab54809bfe4/src/depth_anything_3/api.py#L133-L219),
[normalization source](https://github.com/ByteDance-Seed/Depth-Anything-3/blob/3d835ec1a5802d64a8b8b15f817a1ab54809bfe4/src/depth_anything_3/api.py#L327-L339),
[API documentation](https://github.com/ByteDance-Seed/Depth-Anything-3/blob/3d835ec1a5802d64a8b8b15f817a1ab54809bfe4/docs/API.md#pose-alignment-parameters)).
Those operations change gauge and must be recorded.  For the unposed Module 12
default, use `ref_view_strategy="first"` for comparability and provide no input
cameras.

There is a concrete schema discrepancy to test at preflight.  README and parts
of the API documentation describe returned extrinsics as `[N,3,4]`, while the
output processor documents and returns `[N,4,4]`
([README example](https://github.com/ByteDance-Seed/Depth-Anything-3/blob/3d835ec1a5802d64a8b8b15f817a1ab54809bfe4/README.md#basic-usage),
[output processor](https://github.com/ByteDance-Seed/Depth-Anything-3/blob/3d835ec1a5802d64a8b8b15f817a1ab54809bfe4/src/depth_anything_3/utils/io/output_processor.py#L42-L74)).
The existing Surflo adapter defensively accepts both
([baseline adapter](../../../surflo/eval/baselines.py)); the landed contract
must do the same and serialize canonical `4x4` matrices plus an explicit
`world_to_camera` tag.

## Candidate comparison

| Candidate | Direct output and retained optimization | Runtime/licence assessment | Outcome |
|---|---|---|---|
| **VGGT-1B (selected)** | One pass jointly exposes cameras, depth, direct world pointmaps, confidences, and queried tracks.  Canonical geometry uses depth unprojection.  Optional PyCOLMAP BA is separate. | Current upstream core is ordinary PyTorch; Surflo's corresponding path has run on B200 and the checkpoint has a separate byte lock.  Source uses the VGGT custom licence; original checkpoint is CC BY-NC 4.0. | **Land first as `vggt/direct`; research-only weight gate.** |
| VGGT-1B-Commercial | Same interface, separately trained weights, optional BA. | Manual-gated, custom VGGT/AUP terms, distinct 5 GB bytes.  Upstream reports similar rather than identical performance. | Separate opt-in adapter only after terms and bytes are accepted. |
| **DA3-BASE** | Depth, confidence, camera, pose conditioning, and ray-derived geometry; no track head. | Apache-2.0 source and model card; 0.12B/541 MB; newer and less integrated, with broad dependencies and a schema inconsistency. | **Permissive fallback**, separate result ID. |
| DA3-LARGE-1.1 | Same any-view interface; 0.35B.  `-1.1` is the refreshed post-training-bug checkpoint. | Official GitHub says CC BY-NC 4.0 while its official Hub card says Apache-2.0.  Treat as noncommercial until the publisher resolves the conflict. | Accuracy follow-on only; not the licence fallback. |
| DUSt3R DPT | Pairwise reference-frame pointmaps/confidence; multiview common geometry requires iterative global alignment. | CC BY-NC-SA 4.0 code/weights plus training-data terms; old, unpinned dependency stack and optional RoPE CUDA kernel. | Historical pointmap oracle and alignment-on comparison. |
| MASt3R metric | DUSt3R pointmaps plus dense descriptors/matching; MASt3R-SfM adds coarse/fine optimization and triangulation. | CC BY-NC-SA 4.0 plus especially restrictive dataset-derived checkpoint terms; Hub card naming mismatch; extra retrieval/matching dependencies. | Matching/alignment specialist, not first geometry reference. |

VGGT is selected because it is the only candidate that directly covers the
curriculum's complete camera/depth/pointmap/track surface, not because every
paper table says it is most accurate.  DA3 reports higher pose and geometry
accuracy under its own newer benchmark and training regime, but the selected
reference should first minimize interface and provenance ambiguity.  DA3 is a
required comparison, not evidence that the two papers' aggregate numbers are
directly comparable.

## Exact source, checkpoint, and term locks

There are no release tags for these exact maintained snapshots.  Full commits
and file hashes, not `main`, model aliases, or short SHAs, are required.

| Artifact | Exact revision and transitive source | Weight bytes and terms |
|---|---|---|
| DUSt3R | [`4c24a6ebf04809f2cfe59915e51779c8984aaa40`](https://github.com/naver/dust3r/tree/4c24a6ebf04809f2cfe59915e51779c8984aaa40), dated 2025-07-01; `croco` gitlink [`d7de0705845239092414480bd829228723bf20de`](https://github.com/naver/croco/tree/d7de0705845239092414480bd829228723bf20de). | Hub revision [`61c57447d7b0adc8a1a30b2b0adec7a8935aa2a3`](https://huggingface.co/naver/DUSt3R_ViTLarge_BaseDecoder_512_dpt/tree/61c57447d7b0adc8a1a30b2b0adec7a8935aa2a3); `model.safetensors` SHA-256 `7c300a89534113436bde52732d3151212bcbd90f0aa3c8d1496f86d84bfe4b42`, 2,284,790,056 bytes.  CC BY-NC-SA 4.0 plus every training-dataset/base-checkpoint term ([card](https://huggingface.co/naver/DUSt3R_ViTLarge_BaseDecoder_512_dpt/blob/61c57447d7b0adc8a1a30b2b0adec7a8935aa2a3/README.md)). |
| MASt3R | [`f5209afc300cec36239a7ac992263f36847bbba0`](https://github.com/naver/mast3r/tree/f5209afc300cec36239a7ac992263f36847bbba0), dated 2025-06-30; `dust3r` gitlink [`3cc8c88c413bb9e34c41db0e0eef99c2ee010b12`](https://github.com/naver/dust3r/tree/3cc8c88c413bb9e34c41db0e0eef99c2ee010b12), whose `croco` gitlink is `d7de0705845239092414480bd829228723bf20de`. | Metric Hub revision [`06e7259f34c3060f322df5cb0c7b9094f57e41fc`](https://huggingface.co/naver/MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric/tree/06e7259f34c3060f322df5cb0c7b9094f57e41fc); `model.safetensors` SHA-256 `0a615eb05fa9db654050aa655945ee5696e7c6c1b7f93f1ee8c37249010f6feb`, 2,754,661,648 bytes.  CC BY-NC-SA plus dataset terms; the official notice includes noncommercial and modified no-derivatives/research-sharing conditions ([notice](https://github.com/naver/mast3r/blob/f5209afc300cec36239a7ac992263f36847bbba0/CHECKPOINTS_NOTICE)). |
| VGGT source and original weights | [`a288dd0f14786c93483e45524328726ab7b1b4ce`](https://github.com/facebookresearch/vggt/tree/a288dd0f14786c93483e45524328726ab7b1b4ce), dated 2026-05-19. | Hub revision [`860abec7937da0a4c03c41d3c269c366e82abdf9`](https://huggingface.co/facebook/VGGT-1B/tree/860abec7937da0a4c03c41d3c269c366e82abdf9); selected safetensors hash/size above.  The alternative `model.pt` is SHA-256 `d15bf50a8615c8225ed48b51ea5cac673d82442ec0309036df555a053253afe0`, 5,026,874,952 bytes; do not allow either filename to satisfy the other's lock.  Source: custom VGGT licence/AUP.  Original weights: CC BY-NC 4.0. |
| VGGT commercial weights | Same VGGT source pin. | Gated Hub revision [`ebb29a532abe92960eeb6903a5530f16990ef4ab`](https://huggingface.co/facebook/VGGT-1B-Commercial/tree/ebb29a532abe92960eeb6903a5530f16990ef4ab); `model.safetensors` SHA-256 `2b766b284359bc47ce26be107254621f685b758a0282082ff109f3ff02788b53`, 5,026,367,224 bytes; `vggt_1B_commercial.pt` SHA-256 `1f941e207ab8734121f1fe5dbdac50061d4560e1fed13fecd561895b72690a4a`, 5,026,903,832 bytes.  Custom VGGT licence/AUP, including prohibited-use conditions; manual access gate. |
| DA3 source | [`3d835ec1a5802d64a8b8b15f817a1ab54809bfe4`](https://github.com/ByteDance-Seed/Depth-Anything-3/tree/3d835ec1a5802d64a8b8b15f817a1ab54809bfe4), dated 2026-07-27; code licence Apache-2.0.  Gaussian export additionally pins gsplat [`0b4dddf04cb687367602c01196913cde6a743d70`](https://github.com/nerfstudio-project/gsplat/tree/0b4dddf04cb687367602c01196913cde6a743d70), but that optional head is outside this reference. | `DA3-BASE`: Hub revision [`f4a6c9b3c95e41c82048423d3493a81ec3fa810e`](https://huggingface.co/depth-anything/DA3-BASE/tree/f4a6c9b3c95e41c82048423d3493a81ec3fa810e), SHA-256 `e01067dc1659613083d9145a9a2547ccdbe6ccbbf83c4fe7b3e8a4e2bdae78b5`, 541,518,028 bytes, Apache-2.0. |
| DA3 accuracy follow-on | Same DA3 source pin. | `DA3-LARGE-1.1`: Hub revision [`0e109ae307c5982f319a67cf6f9f99ccdc0ec97c`](https://huggingface.co/depth-anything/DA3-LARGE-1.1/tree/0e109ae307c5982f319a67cf6f9f99ccdc0ec97c), SHA-256 `739905c423cf0d6ccaf9e61a8401d82ba1ac32d7f4d3ee6dca8f92b377633f64`, 1,643,843,860 bytes.  The [Hub card](https://huggingface.co/depth-anything/DA3-LARGE-1.1/blob/0e109ae307c5982f319a67cf6f9f99ccdc0ec97c/README.md) says Apache-2.0, but the pinned [official source table](https://github.com/ByteDance-Seed/Depth-Anything-3/blob/3d835ec1a5802d64a8b8b15f817a1ab54809bfe4/README.md#model-cards) says CC BY-NC 4.0.  Apply the stricter term pending publisher clarification. |

The `-1.1` DA3 models were released after a training-bug fix; the authors mark
the original Giant, Large, and Nested checkpoints deprecated and recommend the
refreshed versions.  Do not compare a mutable `depth-anything/DA3-LARGE` alias
to a `-1.1` result without naming and hashing both artifacts.

The pre-landing audit found three provenance gaps that the Module 12 adapter
had to close:

1. `surflo/nn/vggt` is a locally modified vendored fork introduced at Surflo
   commit `85a6ec80a612c392efbc2c974b6a090b93cae28d`; imports and output plumbing
   differ from upstream, and no upstream commit is recorded beside the tree.
   The B200 scout is tied to Surflo commit
   `bf14c6375a92911c45795710cd00bf2af17e9a13`, not automatically to upstream
   `a288dd0`.  The adapter must either vendor the exact upstream pin or record
   every local file hash and pass a golden-output comparison.
2. The exact VGGT Hub revision and hashes are recorded in the photoreal-scene
   model lock, but the B200 scout recipe/result does not reference that lock or
   independently record the VGGT bytes.  Treat the scout as path/toolchain
   evidence, not an exact-pin reproduction.
3. The B200 scout's DA3 source is reproducibly the repository gitlink
   `3d835ec1a5802d64a8b8b15f817a1ab54809bfe4`, but the evaluation default names
   mutable `depth-anything/DA3-LARGE` and the scout records no Hub revision or
   checkpoint SHA-256 ([evaluation config](../../../configs/eval.yaml),
   [scout recipe](../../insula-scout/recipe.json)).  At the historical cutoff
   that Hub repository resolves to revision
   [`c54c26b16ec04d218e8d584ecf4bce082a9fcc20`](https://huggingface.co/depth-anything/DA3-LARGE/tree/c54c26b16ec04d218e8d584ecf4bce082a9fcc20),
   whose `model.safetensors` SHA-256 is
   `eaf2ae06df55889ad23eb245c82e2dd2a30c0cbf7e3d873a118fa5ed27a3e421`
   (1,643,843,860 bytes, CC BY-NC 4.0).  That observation cannot be
   retroactively assigned to an unrecorded cache.  The scout's DA3 timing and
   metric are useful execution evidence but not a fully reproducible
   checkpoint result.

The maintained adapter closes those execution gaps without claiming that the
older scout did. `foundation-models.lock.json` selects the exact upstream VGGT
archive at `a288dd0…` (archive SHA-256 `df4e7de…`, extracted-tree SHA-256
`ec486998…`) rather than executing Surflo's vendored fork. It rejects a dirty
DA3 checkout and verifies the complete tracked tree at `3d835ec…` (tree
SHA-256 `81d2a462…`). It locks the selected VGGT-1B and DA3-BASE checkpoint
bytes, and preflight hashes the complete resolved reused venv—40,069 records,
6,810,610,151 bytes, tree SHA-256 `65d28a33…`—before the read-only offline
container starts. The run record retains the complete file manifest,
distribution versions, native binaries, loaded-module hashes, CUDA compiler,
attention-backend flags, and model/source contracts.

## Runtime and B200 assessment

Upstream recipes are informative compatibility starting points, not a B200
contract:

- DUSt3R and MASt3R show Python 3.11 with PyTorch/CUDA 12.1 and optionally
  compile CroCo's CUDA RoPE kernel; their requirements are largely unpinned
  ([DUSt3R installation](https://github.com/naver/dust3r/blob/4c24a6ebf04809f2cfe59915e51779c8984aaa40/README.md#installation),
  [MASt3R installation](https://github.com/naver/mast3r/blob/f5209afc300cec36239a7ac992263f36847bbba0/README.md#installation)).
- VGGT's example requirements pin Torch 2.3.1, Torchvision 0.18.1, and NumPy
  1.26.1, while its package metadata requires Python 3.10+, NumPy `<2`, and
  pure-PyTorch core dependencies.  BA additionally pulls PyCOLMAP 3.10,
  PyCeres 2.3, and LightGlue
  ([core requirements](https://github.com/facebookresearch/vggt/blob/a288dd0f14786c93483e45524328726ab7b1b4ce/requirements.txt),
  [package metadata](https://github.com/facebookresearch/vggt/blob/a288dd0f14786c93483e45524328726ab7b1b4ce/pyproject.toml),
  [demo requirements](https://github.com/facebookresearch/vggt/blob/a288dd0f14786c93483e45524328726ab7b1b4ce/requirements_demo.txt)).
- DA3 declares Python 3.9–3.13, Torch `>=2`, NumPy `<2`, xFormers, Open3D,
  PyCOLMAP, and other broad/unpinned dependencies.  Its optional Gaussian head
  builds the exact gsplat commit listed above
  ([package metadata](https://github.com/ByteDance-Seed/Depth-Anything-3/blob/3d835ec1a5802d64a8b8b15f817a1ab54809bfe4/pyproject.toml#L8-L47)).

None of those upstream projects publishes a B200 validation matrix.  The
stronger local evidence is the repository's 2026-09-25 scout on an NVIDIA B200
with Python 3.10.20, Torch 2.9.1+cu130, Torchvision 0.24.1+cu130, CUDA compiler
13.2, and NumPy 1.26.4.  On one 16-view Tanks & Temples `Ignatius` scene, VGGT
raw geometry completed in 2.693 seconds excluding model startup, reached 8.825
GiB peak VRAM, normalized Chamfer 0.006064, and F1 0.8565.  DA3 completed in
2.751 seconds, reached 9.685 GiB, normalized Chamfer 0.006527, and F1 0.8212
([machine-readable results](../../insula-scout/results.json)).
This is one integration scout, not a benchmark aggregate; its DA3 weight
revision and scout-to-VGGT-lock gaps remain properties of that historical
record. The maintained adapter is a new exact-pin run and does not relabel the
scout.

The same scout found that TSDF post-processing made both methods worse on that
scene.  Therefore raw pointmaps and `+tsdf` are separate methods; TSDF may not
be presented as harmless export formatting.  The scout also removed an
incompatible cu128 xFormers wheel and verified the DA3-LARGE MLP fallback
without xFormers.  This is a workable B200 compatibility choice, not proof that
every DA3 model/head or xFormers version works
([scout notes](../../insula-scout/README.md#environment-and-compatibility-notes)).

Paper timings must not become acceptance thresholds.  The VGGT supplement
measures 336x518 inputs on H100 with FlashAttention 3 and reports backbone peak
memory rising from 1.88 GB for one frame to 40.63 GB for 200, before the May
2026 implementation fix that upstream says allows roughly 2–3x more frames
under the same budget
([VGGT supplement, Table 7](https://openaccess.thecvf.com/content/CVPR2025/supplemental/Wang_VGGT_Visual_Geometry_CVPR_2025_supplemental.pdf),
[fix announcement](https://github.com/facebookresearch/vggt/blob/a288dd0f14786c93483e45524328726ab7b1b4ce/README.md#updates)).
DA3 Table 8 measures average per-image throughput over 32 images at 504x336 on
an 80 GB A100: 34.1 FPS for the VGGT reference, 37.6 for DA3-Giant, 78.37 for
Large, 126.5 for Base, and 160.5 for Small.  That is neither end-to-end latency
nor B200 evidence
([DA3 paper, Table 8](https://openreview.net/pdf/9d69fc515ade062e6a76a0e4c7e6835ad3e21402.pdf)).

The landed preflight must run the exact selected bytes offline on B200, report
GPU name/compute capability, driver, CUDA runtime/compiler, Python, Torch,
Torchvision, attention backend, dtype, deterministic flags, source commit,
checkpoint hashes, input count and processed dimensions, forward time, total
time, and `max_memory_allocated`.  A successful import or the ability to load a
checkpoint is not completion.

## Controlled-scene adapter protocol

### Inputs and preprocessing

The common evidence is an ordered list of one or more unposed RGB images of one
nominally static scene.  Persist original bytes/hashes, original dimensions,
EXIF orientation action, selected reference image, final view order, processed
dimensions, resize/crop/pad transform, normalization, and any pixel mask.
Never infer that filename order is camera order.

For selected VGGT, use the pinned official loader's default `mode="crop"`
518-pixel, aspect-ratio-preserving preprocessing and record all resizing,
center cropping, and cross-image padding
([loader](https://github.com/facebookresearch/vggt/blob/a288dd0f14786c93483e45524328726ab7b1b4ce/vggt/utils/load_fn.py#L97-L230)).
Input 0 is the reference.  For DA3 comparison, set `process_res=504`,
`process_res_method="upper_bound_resize"`, `ref_view_strategy="first"`,
`use_ray_pose=false`, and supply no cameras.  A separate ray-pose result may set
`use_ray_pose=true`.  Do not let DA3's default automatic reference selection
change the view order invisibly.

For `S=1`, report a dedicated monocular condition.  VGGT supports a single
view, but its authors say it was not trained for that task and did not
quantitatively evaluate monocular depth themselves
([official single-view note](https://github.com/facebookresearch/vggt/blob/a288dd0f14786c93483e45524328726ab7b1b4ce/README.md#single-view-reconstruction)).
DUSt3R's common monocular evaluation duplicates an image into a pair; label
that construction rather than equating it to a native one-view network call.

### Canonical output record

Every run must write one self-describing record with at least:

| Field | Required meaning |
|---|---|
| `method_id` | Exact family and mode, for example `vggt/direct`, `vggt/ba`, `da3-base/camera-head`, `dust3r/global`, or `mast3r-sfm/sparse-global`; never only “foundation model.” |
| `source` / `checkpoint` | Full source commit, nested gitlinks, Hub repository/revision, filename, SHA-256, bytes, and locally accepted licence identifier. |
| `inputs` | Ordered image hashes; original and processed `H,W`; every geometric preprocessing transform; reference-view index before and after any reorder. |
| `cameras` | Canonical float32 `[S,4,4]` world-to-camera matrices; OpenCV `x-right/y-down/z-forward`; pixel `[S,3,3]` intrinsics at the stored depth resolution; source representation and conversion. |
| `depth` | Float32 `[S,H,W]`, explicitly camera-`z` or Euclidean/ray distance.  Selected VGGT uses camera `z`. |
| `pointmap_depth` | Float32 `[S,H,W,3]` shared-world points deterministically unprojected from the stored depth and cameras. |
| `pointmap_direct` | Native direct world-point head when available; absent for DA3.  Never overwrite `pointmap_depth`. |
| `confidence` | Raw head name, shape, activation/domain if known, and threshold.  Cross-model confidence values are not assumed calibrated. |
| `tracks` | Query coordinates and their resolution/frame, `[S,N,2]` tracks, visibility and confidence.  Unsupported for DA3/DUSt3R geometry adapters rather than fabricated. |
| `gauge` | Reference frame, first-camera residual from identity, metric/relative flag, learned/raw scale statistic, and every applied SE(3)/Sim(3)/input-pose alignment. |
| `optimization` | `none`, DUSt3R global, MASt3R sparse global, or VGGT/PyCOLMAP BA; iterations, objective/options, convergence, and its separate timing. |
| `validity` | Finite, positive-depth, in-frame, confidence, sky/background, and evaluation masks as separate counts. |
| `runtime` | Cold load, preprocessing, network, deterministic decoding/unprojection, optional optimization, export, total, and peak VRAM. |

Check round-trip geometry before scoring: reproject `pointmap_depth` through the
stored world-to-camera and intrinsics, require finite positive `z`, and measure
pixel residual.  For VGGT direct points, separately project
`pointmap_direct`; disagreement with the associated source pixel is a model
diagnostic, not a reason to mutate it.  Verify camera 0 residual, rotation
determinant/orthogonality, focal positivity, principal point, and depth-point
`z` consistency.  Reject a run whose shapes are merely squeezed into place
without proving the stored convention.

### Alignment and optimization matrix

Each geometry result is evaluated in at least these named forms:

1. `raw`: no estimated transform; preserves the model's realized gauge;
2. `se3`: one rigid transform estimated from the declared evaluation
   correspondences, no scale;
3. `sim3`: one similarity transform, including scale; and
4. `optimized`: only when the method's named global alignment or BA path ran,
   followed again by raw/SE(3)/Sim(3) reporting as applicable.

Do not optimize on evaluator geometry and then call the result feed-forward.
Do not report only the best alignment.  Metric checkpoints must still be
reported raw and SE(3); a large gain from Sim(3) is evidence against their
metric-scale claim on that episode.  Pose AUC uses relative rotation and
translation-angle protocols, with exact thresholds and view sampling recorded;
absolute trajectory metrics require their alignment mode in the metric name.

### Failure sweep and metrics

Land one deterministic factorial sweep spanning:

- view count: `1, 2, 4, 8, 16` where available, with fixed nested subsets;
- overlap: high, medium, low, and deliberately disconnected/no-overlap pairs;
- reference choice/order: fixed first image plus at least one permutation;
- observed versus unseen evaluation surface, defined by ground-truth camera
  visibility rather than model confidence; and
- direct versus retained optimization for every result that declares an
  optimization mode; this first direct-only adapter records supported optional
  BA as `not-run` rather than fabricating or silently applying it.

Report camera relative-pose AUC at declared angular thresholds, depth AbsRel
and threshold accuracy both raw and with the declared scale/shift alignment,
point accuracy/completeness/Chamfer/F1 at scene-normalized and metric
thresholds where valid, valid-point coverage, confidence-coverage curves, and
the runtime decomposition above.  Direct point-head and depth-unprojected
pointmaps are separate rows.  Do not score empty output as success or hide it
by aligning an empty/degenerate cloud.

The unseen-surface slice is especially important: these models return visible
pointmaps, so no output on an unobserved back surface is the honest supported
behavior.  Any apparent unseen completion comes from learned priors or a
downstream completion model and must be named accordingly.

## Evaluation caveats

Paper numbers are sensitive to different alignments, masks, and reconstruction
operators:

- DUSt3R's monocular depth tables align scale, and its multiview geometry
  evaluation uses dataset-specific alignment.  Its paper also notes training
  overlap concerns for ScanNet/Habitat and that regression is less
  subpixel-accurate than triangulation
  ([DUSt3R paper, experiments and limitations](https://openaccess.thecvf.com/content/CVPR2024/papers/Wang_DUSt3R_Geometric_3D_Vision_Made_Easy_CVPR_2024_paper.pdf)).
- MASt3R's headline results are primarily matching and relative-pose results
  under particular reciprocal-matching, RANSAC, and calibration choices.  They
  do not by themselves establish dense scene accuracy.
- VGGT camera AUC samples ten views in key benchmarks.  Its point-cloud
  evaluation similarity-aligns predictions with Umeyama and filters invalid
  points; optional BA changes both runtime and result.  The supplement reports
  degradation under extreme image rotations, lack of fisheye/panorama support,
  and failures with substantial nonrigid deformation
  ([paper](https://openaccess.thecvf.com/content/CVPR2025/papers/Wang_VGGT_Visual_Geometry_Grounded_Transformer_CVPR_2025_paper.pdf),
  [supplement](https://openaccess.thecvf.com/content/CVPR2025/supplemental/Wang_VGGT_Visual_Geometry_CVPR_2025_supplemental.pdf)).
- DA3 aligns predicted poses to ground truth with a robust/RANSAC Umeyama
  procedure before TSDF fusion.  Its HiRoom, ETH3D, 7Scenes, and ScanNet++
  geometry scores use different voxel sizes and F1 thresholds; DTU removes
  background with RMBG.  Its NVS comparison receives ground-truth COLMAP poses
  and retrains baselines under a unified protocol.  The paper lists dynamic
  scene reasoning as future work
  ([ICLR paper, Sections 6–8](https://openreview.net/pdf/9d69fc515ade062e6a76a0e4c7e6835ad3e21402.pdf)).

Training-set membership and scene overlap must be disclosed per evaluation
dataset.  “Zero-shot” does not mean that the model never trained on the same
dataset family, and a scene-level train/test split is different from an unseen
dataset.

## Completion and unsupported guardrails

The first maintained adapter is complete only when it:

- executes the exact source and selected checkpoint bytes offline on B200;
- emits the canonical camera/depth/two-pointmap/track-capability record and
  passes the geometry round-trip checks;
- keeps feed-forward and any separately landed BA/global-alignment artifacts,
  timing, and result IDs separate; the direct-only result records BA as
  `not-run`;
- lands the overlap/view-count/unseen/alignment sweep with raw, SE(3), and
  Sim(3) metrics; and
- records terms without embedding or redistributing restricted weights.

It supports claims about amortized cameras, visible depth-derived pointmaps,
native direct pointmaps, queried tracks, confidence, and measured runtime on
the tested inputs.  It does **not** support claims of metric scale, calibrated
uncertainty, watertight reconstruction, hidden-surface completion, dynamic
scene reconstruction, arbitrary camera models, universal order invariance,
paper-table reproduction, or upstream-certified B200 support.

The executable selection's technical gates are closed by running the exact
upstream VGGT pin, exact DA3 gitlink, selected checkpoint bytes, complete
environment lock, and fresh B200 smoke/full profiles. Legal acceptance of the
VGGT code/weight terms remains the deployer's responsibility. Publisher
clarification of the DA3-LARGE-1.1 licence conflict remains open but does not
affect the selected Apache-2.0 DA3-BASE checkpoint. The old scout remains
historical path/toolchain evidence and is not retroactively called an
exact-checkpoint reproduction.

The sealed runs are `module12-smoke-final-reviewed-20260927` and
`module12-full-final-reviewed-20260927`. The full profile executes fixed nested
1/2/4/8/16-view subsets, high/medium/low/disconnected overlap pairs, and an
eight-view permutation. Every case scores ground-truth observed and unseen
surface slices. The 16-view primary case measured observed-surface F1 at 5 cm
of 0.1491 for VGGT and 0.0835 for DA3-BASE; unseen recall was zero for both.
These are controlled-fixture measurements, not a paper-table reproduction.
