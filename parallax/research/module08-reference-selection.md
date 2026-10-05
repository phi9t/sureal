# Module 08 maintained-reference selection

**Decision (research recommendation; cutoff 2026-09-25): use Depth Anything V2
Metric Hypersim Small as the first maintained reference.**  It is a small,
official, single-RGB, metric-depth adapter with a direct `HxW` metres output.
That makes it practical to run deterministically on the shared calibrated scene
and, importantly, to report both the *unmodified* metric error and the
scale/shift-aligned diagnostic.  The latter must not replace the former: this
is an amortized monocular prior, so neither output establishes that its scale
or hidden geometry is measured by the input.

This is a reference for **visible per-view depth**, not a multi-view
reconstruction or a complete-scene model.  Mark every predicted pixel
`prior-conditioned`; mark pixels that are jointly visible and geometrically
consistent with the supplied context as `image-supported` only after a
separate comparison.  Do not render `hidden-a`/`hidden-b` to it: its
single-image output cannot select or represent a coherent completion
hypothesis.

## Adopted adapter contract

Input each declared reference RGB case in the repository's documented OpenCV
camera convention; preserve its original dimensions and record preprocessing.
The landed smoke profile uses the center shared-scene view plus focal-crop and
concave open-box stressors; full uses all nine shared-scene views plus those
same stressors. Each 640x480 case has exact float32 camera-axis depth for its
input-visible rays. Run the *indoor* metric Small checkpoint and write: float32
`depth_m[H,W]`, a validity mask, source-image hash, checkpoint SHA-256, source
commit, model configuration (`vits`, `max_depth=20`, default
`input_size=518`), runtime, and peak GPU memory. The upstream metric README says
this model is fine-tuned on Hypersim and returns metres. Pin its immutable
Hugging Face revision
`3bc65d4e14a6786a61acec16453c50e12bf5f338`: the official
[`depth_anything_v2_metric_hypersim_vits.pth`](https://huggingface.co/depth-anything/Depth-Anything-V2-Metric-Hypersim-Small/resolve/3bc65d4e14a6786a61acec16453c50e12bf5f338/depth_anything_v2_metric_hypersim_vits.pth)
is 99,222,290 bytes with LFS SHA-256
`b782898d8a3e8be1f639de33837ed85e9b4b73e40f8f5e5cd99067588d722545`.

Score only valid, visible truth pixels in two columns:

| Score | Meaning | Required interpretation |
|---|---|---|
| raw `RMSE_m`, `AbsRel` | prediction in declared metres versus shared-scene camera-axis depth in metres | primary metric-scale claim |
| affine-aligned `RMSE_m`, with recorded `s,t` | one least-squares `(s * prediction + t)` fitted jointly across the profile's declared evaluation mask | shape/order diagnostic only; never call it metric accuracy or silently fit per image |

The landed OOD checks are effective-focal change and concave/open-box geometry,
both scored separately. Per-plane residuals, depth-boundary error, known-pose
cross-view disagreement, and a texture-only counterfactual remain explicitly
deferred extensions; they are not claimed by this first maintained adapter.
Never score a target/disoccluded or `hidden-a`/`hidden-b` surface as if the
monocular model observed it.  A much better aligned score coupled with poor raw
scale, texture-sensitive plane warping, or an unsupported plausible surface is
the expected prior-failure evidence—not successful completion.

## Candidate comparison

| Candidate | Semantics and official I/O | Source / checkpoint licence and pin | Offline B200 assessment | Selection outcome |
|---|---|---|---|---|
| **[Depth Anything V2](https://arxiv.org/abs/2406.09414) Metric Small (recommended)** | Monocular RGB; the base models are explicitly **relative** depth, while the separate [metric inference](https://github.com/DepthAnything/Depth-Anything-V2/blob/a561b849ebae10a6f5ef49e26c83cbbcd36c71bf/metric_depth/depth_anything_v2/dpt.py) supplies `HxW` numpy depth in metres.  The 24.8M Small indoor model is trained on Hypersim; this scene is therefore an intentionally useful OOD probe, not a benchmark claim. | Repository [DepthAnything/Depth-Anything-V2](https://github.com/DepthAnything/Depth-Anything-V2), cutoff commit [`a561b849ebae10a6f5ef49e26c83cbbcd36c71bf`](https://github.com/DepthAnything/Depth-Anything-V2/tree/a561b849ebae10a6f5ef49e26c83cbbcd36c71bf) (2026-03-24).  The root README licenses Small under Apache-2.0 and Base/Large/Giant under CC-BY-NC-4.0.  The separately released metric-Hypersim Small [model card at revision `3bc65d4e14a6786a61acec16453c50e12bf5f338`](https://huggingface.co/depth-anything/Depth-Anything-V2-Metric-Hypersim-Small/blob/3bc65d4e14a6786a61acec16453c50e12bf5f338/README.md) declares Apache-2.0; the exact checkpoint hash and size are given above. | Very feasible: one small checkpoint and pure PyTorch/OpenCV inference with no pose, cost-volume, fusion, or custom CUDA stage.  The official [requirements](https://github.com/DepthAnything/Depth-Anything-V2/blob/a561b849ebae10a6f5ef49e26c83cbbcd36c71bf/requirements.txt) are unpinned, so B200 support is an adapter-container property: pin the direct runtime packages, attest the resulting image ID, read-only mount the hash-verified checkpoint, and run `--network none`. Transitive package resolution makes a rebuild less strict than the runtime attestation. | Best first landing: directly exposes the raw-versus-aligned lesson at low operational risk. |
| **Depth Anything V2 relative Small** | Monocular RGB -> relative `HxW` depth.  It is the cleanest gauge example, but raw metres are not meaningful. | Same source pin; official relative Small URL is [`depth_anything_v2_vits.pth`](https://huggingface.co/depth-anything/Depth-Anything-V2-Small/resolve/main/depth_anything_v2_vits.pth?download=true), and the official README states Apache-2.0 for Small. | Equally feasible offline after SHA-256 locking. | Good *secondary diagnostic* if the goal is solely affine ambiguity; reject as the maintained metric reference because raw metric error is intentionally undefined. |
| **[MiDaS 3.1](https://arxiv.org/abs/2307.14460)** | Monocular RGB -> depth map; MiDaS itself says it computes **relative** depth and points users needing metric depth to ZoeDepth.  The official [runner](https://github.com/isl-org/MiDaS/blob/454597711a62eabcbf7d1e89f3fb9f569051ac9b/run.py) returns an original-resolution float array and writes PFM plus a visualization. | Repository [isl-org/MiDaS](https://github.com/isl-org/MiDaS), cutoff commit [`454597711a62eabcbf7d1e89f3fb9f569051ac9b`](https://github.com/isl-org/MiDaS/tree/454597711a62eabcbf7d1e89f3fb9f569051ac9b), **archived**, MIT source.  Official release asset example: [`dpt_beit_large_512.pt`](https://github.com/isl-org/MiDaS/releases/download/v3_1/dpt_beit_large_512.pt). **Uncertainty:** no distinct weight licence was located in the official README/repository; do not infer one from the source licence. | The official [environment](https://github.com/isl-org/MiDaS/blob/454597711a62eabcbf7d1e89f3fb9f569051ac9b/environment.yaml) pins PyTorch 1.13.0, torchvision 0.14.0, and CUDA 11.7, so it is not a direct B200 recipe.  A modern port plus local weight locking is plausible, but an archived 2024 codebase and 345M best model make it a poor maintained target. | Historical baseline only; raw metric error would be misleading, aligned error is appropriate. |
| **[Apple Depth Pro](https://arxiv.org/abs/2410.02073)** | Monocular RGB -> `prediction["depth"]` in metres plus `focallength_px`; upstream describes zero-shot metric monocular depth and does not require supplied intrinsics.  Its [inference implementation](https://github.com/apple-aiml-research/ml-depth-pro/blob/9e65e4dbe9568d23c546fcec53302b10445e109e/src/depth_pro/depth_pro.py) resizes to 1536x1536 and returns depth at the original resolution. | Canonical repository [apple-aiml-research/ml-depth-pro](https://github.com/apple-aiml-research/ml-depth-pro), cutoff commit [`9e65e4dbe9568d23c546fcec53302b10445e109e`](https://github.com/apple-aiml-research/ml-depth-pro/tree/9e65e4dbe9568d23c546fcec53302b10445e109e) (2026-09-11). Official checkpoint URL: [`depth_pro.pt`](https://ml-site.cdn-apple.com/models/depth-pro/depth_pro.pt), 1,904,446,787 bytes. Its README says both code and weights use its [Apple licence](https://github.com/apple-aiml-research/ml-depth-pro/blob/9e65e4dbe9568d23c546fcec53302b10445e109e/LICENSE), a non-SPDX Apple grant with no patent licence. | Likely runnable because the official implementation uses ordinary PyTorch/torchvision/timm operations and no custom CUDA extension; its [dependencies](https://github.com/apple-aiml-research/ml-depth-pro/blob/9e65e4dbe9568d23c546fcec53302b10445e109e/pyproject.toml) are unpinned, no official B200 validation was found, and the CDN provides no published SHA-256.  Fetch, hash, and bake it before offline execution. | Strong metric comparator, but not first: licence, 1.9 GB weight, and larger operational footprint buy little for the module's affine-error teaching objective.  Report raw error first and aligned error only as a diagnostic. |
| **[Metric3D / Metric3Dv2](https://arxiv.org/abs/2404.15506)** | Monocular RGB plus camera intrinsics -> `pred_depth`, confidence, and (v2 ViT) normals.  The official [`hubconf.py` example](https://github.com/YvanYin/Metric3D/blob/eb5b6fac0dc155e4e52f576e304fbf11655ff339/hubconf.py) resizes/pads RGB to 616x1064, removes padding, restores the original size, and multiplies canonical depth by resized `fx / 1000` for metres.  Its documentation warns that an incorrect focal length distorts point clouds and defaults to nine focal settings when intrinsics are absent. | Repository [YvanYin/Metric3D](https://github.com/YvanYin/Metric3D), cutoff commit [`eb5b6fac0dc155e4e52f576e304fbf11655ff339`](https://github.com/YvanYin/Metric3D/tree/eb5b6fac0dc155e4e52f576e304fbf11655ff339), BSD-2-Clause source. Its official `hubconf.py` names the [v2-S Hugging Face checkpoint at revision `80d2d1410afb4b23cd9d18c6be9144483d4b70b6`](https://huggingface.co/JUGGHM/Metric3D/resolve/80d2d1410afb4b23cd9d18c6be9144483d4b70b6/metric_depth_vit_small_800k.pth): 150,120,967 bytes, LFS SHA-256 `b34b2a2be9148054991cef7e417930e1320602ba7bc503b0ee4e7888543728f6`. **Uncertainty:** that official HF repository has no model card or checkpoint-licence metadata, so BSD-2-Clause cannot safely be assumed for the weights. | The official [v2 requirements](https://github.com/YvanYin/Metric3D/blob/eb5b6fac0dc155e4e52f576e304fbf11655ff339/requirements_v2.txt) pin PyTorch 2.0.1, torchvision 0.15.2, xformers 0.0.21 and NumPy 1.23.1 while leaving mmcv/timm loose: not a direct B200 stack.  A modern pinned port is possible but materially riskier than DA V2. | Worth a future metric-plus-normal comparison, but not first: checkpoint licensing and focal canonicalization add confounders.  Keep raw and aligned errors. |
| **[PatchmatchNet](https://openaccess.thecvf.com/content/CVPR2021/html/Wang_PatchmatchNet_Learned_Multi-View_Patchmatch_Stereo_CVPR_2021_paper.html) (practical learned-MVS alternative)** | Calibrated multi-view RGB, per-view `4x4` extrinsics, `3x3` intrinsics, depth min/max and view-pair file -> metric depth/fused PLY.  Its official custom-data path converts COLMAP dense cameras and supports arbitrary image sizes/multi-camera setups.  This is matching-based MVS, **not completion**; occluded/hidden regions must remain unsupported. | Official [FangjinhuaWang/PatchmatchNet](https://github.com/FangjinhuaWang/PatchmatchNet), cutoff commit [`8dc6cb40bdb7053e856598b378425c76a9dcf5e0`](https://github.com/FangjinhuaWang/PatchmatchNet/tree/8dc6cb40bdb7053e856598b378425c76a9dcf5e0) (2025-09-19), MIT source.  The commit tracks [`params_000007.ckpt`](https://raw.githubusercontent.com/FangjinhuaWang/PatchmatchNet/8dc6cb40bdb7053e856598b378425c76a9dcf5e0/checkpoints/params_000007.ckpt) (2,839,519 bytes; locally verified SHA-256 `477b056c62355d82649cdd00a01086a34183ac11f2ce0ddabbf84efb0248d8d4`) and [`module_000007.pt`](https://raw.githubusercontent.com/FangjinhuaWang/PatchmatchNet/8dc6cb40bdb7053e856598b378425c76a9dcf5e0/checkpoints/module_000007.pt) (1,123,557 bytes; SHA-256 `ce053605b4f22e1478dcc82e844a567e0aabe8415bb7f89c49382ef2e21dd44e`).  Its README says these current weights were retrained by contributors; no separate model card/licence is present, so treat them as repository references, not the paper's original weights, and review weight licensing before redistribution. | Plausible in a pinned modern B200 PyTorch/CUDA image: [requirements](https://github.com/FangjinhuaWang/PatchmatchNet/blob/8dc6cb40bdb7053e856598b378425c76a9dcf5e0/requirements.txt) are only unpinned torch, torchvision, OpenCV, NumPy, plyfile, Pillow, and TensorBoard, with no compiled project extension.  Upstream says Python 3.8/CUDA >=10.1, not that B200 was tested.  The shared cameras, depth interval, pairs, fusion, and filtering still need a materially larger adapter. | **Recommended second reference**, once module 08 needs its multi-view evidence boundary exercised.  Raw error is meaningful in the supplied metric camera gauge; an aligned score is a diagnostic only and must not hide calibration/scale failure. |

## Source basis and reproducibility limits

The source commits above were resolved with GitHub's official commits API
using `until=2026-09-25T23:59:59Z`; each linked tree is therefore a verified
cutoff-or-earlier commit, not a floating default branch.  The official
documentation supporting the model semantics and interfaces is the
[DA V2 root README](https://github.com/DepthAnything/Depth-Anything-V2/blob/a561b849ebae10a6f5ef49e26c83cbbcd36c71bf/README.md),
[DA V2 metric README](https://github.com/DepthAnything/Depth-Anything-V2/blob/a561b849ebae10a6f5ef49e26c83cbbcd36c71bf/metric_depth/README.md),
[MiDaS README](https://github.com/isl-org/MiDaS/blob/454597711a62eabcbf7d1e89f3fb9f569051ac9b/README.md),
[Depth Pro README](https://github.com/apple-aiml-research/ml-depth-pro/blob/9e65e4dbe9568d23c546fcec53302b10445e109e/README.md),
[Metric3D README](https://github.com/YvanYin/Metric3D/blob/eb5b6fac0dc155e4e52f576e304fbf11655ff339/README.md), and
[PatchmatchNet README](https://github.com/FangjinhuaWang/PatchmatchNet/blob/8dc6cb40bdb7053e856598b378425c76a9dcf5e0/README.md).  The checkpoint-specific
Depth Anything licence evidence is its immutable
[metric-Hypersim Small model card](https://huggingface.co/depth-anything/Depth-Anything-V2-Metric-Hypersim-Small/blob/3bc65d4e14a6786a61acec16453c50e12bf5f338/README.md).

Before landing any adapter, `fetch` must download the listed weight through an
explicit network-only path, record URL, retrieved revision/redirect target,
byte size and SHA-256 in the asset lock, and make it available only through the
verified cache. `reference` must recheck that SHA-256, mount the file read-only,
and execute with networking
disabled.  The two official Hugging Face repositories expose their LFS
SHA-256 object IDs, and the repository-tracked PatchmatchNet files can be
hashed directly; MiDaS release assets, the Apple CDN, and the cited Google
Drive mirrors do not publish portable SHA-256 values.  No candidate source
supplied an official B200 validation, so claims beyond hermetic adapter
verification are deliberately left unmade.
