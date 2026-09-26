# Module 10 maintained-reference selection

**Decision (research recommendation; historical cutoff 2026-09-26): land the
standard Nerfstudio `nerfacto` field and optimizer preset as the first small
radiance-field reference, pinned to the already adopted Nerfstudio commit
[`50e0e3c70c775e89333256213363badbf074f29d`](https://github.com/nerfstudio-project/nerfstudio/tree/50e0e3c70c775e89333256213363badbf074f29d).**
At that pin Nerfstudio calls `nerfacto` its recommended real-time model and says
it will be continually updated; the project documentation calls it the default
for static real captures and estimates about 6 GB for the standard variant
([registry and exact preset](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/configs/method_configs.py),
[Nerfacto documentation](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/docs/nerfology/methods/nerfacto.md)).
There is no registered `nerfacto-small` method at this pin: “small” should mean
the repository's bounded smoke/full execution profiles, not an invented network
whose semantics drift from the maintained preset.

“Maintained” needs a narrow qualification.  At the cutoff, the official
default branch still resolves to this 2025-07-29 commit and GitHub reports the
repository as unarchived, but there have been no newer source commits.  The
selection is therefore a practical, supported core-framework reference that
this repository can maintain beside Module 09—not evidence of recent upstream
release cadence or upstream B200 certification
([official commit](https://github.com/nerfstudio-project/nerfstudio/commit/50e0e3c70c775e89333256213363badbf074f29d),
[official repository metadata](https://api.github.com/repos/nerfstudio-project/nerfstudio)).

This choice reuses Module 09's source pin, B200-native tiny-cuda-nn build,
container dependencies, generated RGB/calibration, and already locked LPIPS
AlexNet asset.  It adds no scene/category checkpoint and requires no external
training corpus: `nerfacto` is optimized independently for the supplied scene
([Module 09 selection](module09-reference-selection.md),
[pinned model implementation](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/models/nerfacto.py)).
The recommendation is therefore about practical maintained code, not about
Nerfacto being a paper-faithful “original NeRF.”  Nerfstudio describes it as a
combination of camera refinement, per-image appearance conditioning, proposal
sampling, scene contraction, and hash encoding rather than a single published
method
([official method overview](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/docs/nerfology/methods/nerfacto.md)).

## What the reference estimates

For each sampled position, the Nerfacto field uses a multiresolution hash
encoding and MLP to produce non-negative volume density plus geometry features;
another MLP maps direction encoding, those features, and—unless disabled—an
image appearance embedding to RGB.  Two smaller proposal density fields place
samples before the final field is evaluated
([field source](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/fields/nerfacto_field.py),
[model construction](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/models/nerfacto.py)).
The result is a per-scene density/radiance field rendered by transmittance
weights, not an SDF.  In particular, it has no distinguished zero level set and
does not make Module 09's extracted-surface claim.

The implementation renders RGB, accumulation, median depth, and expected depth.
Its median depth is the first sample at which cumulative ray weight reaches
0.5; when no sample reaches 0.5, the implementation clamps to the final sample.
Expected depth is the weight-normalized sample-distance mean
([depth renderer](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/model_components/renderers.py),
[Nerfacto outputs](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/models/nerfacto.py)).
Consequently, depth metrics must also report accumulation coverage and reject
rays below the fixed 0.5 accumulation threshold; otherwise an empty ray's far
sample is silently scored as geometry.  Nerfstudio's own point-cloud exporter
likewise forms points from rendered depth and filters opacity below 0.5
([exporter source](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/exporter/exporter_utils.py)).

Training minimizes RGB MSE together with the proposal interlevel loss and a
distortion loss; the pinned defaults weight interlevel by `1.0` and distortion
by `0.002`.  Camera-optimizer loss is present only when camera optimization is
enabled, and normal losses are absent because `predict_normals=False` by
default.  PSNR, SSIM, and LPIPS are evaluation metrics initialized by the
model, not terms in this training objective
([loss and metric implementation](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/models/nerfacto.py),
[loss definitions](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/model_components/losses.py)).

## Exact pinned semantics and controlled overrides

The adapter must deep-copy `method_configs["nerfacto"]`, save the resolved
configuration, and apply only the following declared overrides.  This makes the
comparison reproducible while preserving a recognizable maintained method.

| Setting | Pinned upstream value | Controlled Module 10 value and reason |
|---|---:|---|
| Training budget | 30,000 iterations; 4,096 train/eval rays per batch | Smoke: 1,000 x 1,024 rays; full: 20,001 x 2,048 rays.  These exactly match Module 09's ray-update budgets, though they do **not** equalize FLOPs because the samplers and fields differ. |
| Arithmetic | `mixed_precision=True` | Keep true and record autocast/scaler state; Module 09's FP32 result remains a different implementation property, not a numerical-equivalence claim. |
| Main field | 16 hash levels, resolutions 16--2048, `2^19` entries, two features/level, 64-wide density and colour MLPs; preset initial average density `0.01` | Unchanged. |
| Ray samples | proposal stages `(256, 96)`, then 48 final-field samples; two proposal iterations | Unchanged. |
| Proposal schedule | update interval 5 after a 5,000-step warm-up; weight anneal through step 1,000 | Unchanged and recorded. |
| Optimizers | Proposal fields and main field each use Adam (`lr=1e-2`, `eps=1e-15`) with exponential decay to `1e-4` over 200,000 steps | Unchanged; omit the separate camera optimizer because camera optimization is off. |
| Evaluation/render chunk | 32,768 rays | Unchanged unless a measured memory failure requires a declared smaller chunk; chunking may change resource use but not the requested camera rays. |
| Bounds/background | near `0.05`, far `1000`, scene contraction on, piecewise initial sampler, `last_sample` background | Use near `0.1`, far `6.0`, `disable_scene_contraction=True`, and a uniform initial sampler for the known metric `[-1,1]^3` AABB; keep `last_sample` and report background-sensitive metrics separately. |
| Camera optimizer | `SO3xR3` | `off`; the fixture supplies exact poses, so refining them would confound the controlled comparison. |
| Appearance code | 32 dimensions per training image; evaluation uses their mean | `use_appearance_embedding=False`; the synthetic fixture has fixed appearance, and an unseen target has no observed per-camera code. |
| Normals | `predict_normals=False` | Unchanged; do not invent a Nerfacto normal-quality claim. |
| Trainer evaluation | Ray-batch and one-image evaluation every 500 steps, all-image evaluation every 25,000, save every 2,000 | Disable periodic evaluation, keep target files outside every dataset, and save one final checkpoint; render declared cameras only after training. |

The upstream numbers and behavior in this table come from the pinned
[`nerfacto` trainer configuration](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/configs/method_configs.py),
[`TrainerConfig` defaults](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/engine/trainer.py),
[`NerfactoModelConfig`](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/models/nerfacto.py),
and [appearance-field implementation](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/fields/nerfacto_field.py).
The bounded overrides are adapter policy, not claimed upstream recommendations.

Use seed `260925`, one GPU, TF32 off, deterministic cuDNN flags where honored,
and no camera, mask, depth, normal, or monocular-prior supervision.  Lossless
context RGB is the sole optimized evidence.  Store every effective field,
optimizer, scheduler, sampler, precision, and determinism setting rather than
assuming the method name captures them.

## Identical-scene comparison with Module 09

Use the already landed analytic sphere fixture without changing a pixel: smoke
uses its five context azimuths, full uses its nine context azimuths, and both
evaluate the same three held-out target azimuths.  The fixture is 640x480 with
known intrinsics, exact RGB/depth/normal truth, an explicit `[-1,1]^3` model
AABB, and a `context-visibility-count>=2` common-visible support mask
([scene generator](../pipeline/reference_scene.py),
[shared scene](../shared-scene.json),
[Module 09 protocol](module09-reference-selection.md)).
The target RGB arrays must never appear in Nerfstudio's train/eval datasets;
only their camera intrinsics and poses are supplied at render time.  This is a
back-arc extrapolation test, not an ordinary nearby-view interpolation test,
because the context arc is -45 to +35 degrees while targets are 120, 150, and
180 degrees ([shared scene](../shared-scene.json)).

Nerfstudio `transforms.json` uses OpenGL/Blender camera axes (`+X` right, `+Y`
up, `+Z` back), whereas the fixture declares OpenCV axes (`+X` right, `+Y`
down, `+Z` forward).  Generate the training transforms by right-multiplying
each fixture camera-to-world matrix by `diag(1,-1,-1,1)`, set parser
`orientation_method="none"`, `center_method="none"`,
`auto_scale_poses=False`, `scale_factor=1`, `scene_scale=1`, and
`downscale_factor=1`; persist the transform and map rendered points back to the
fixture's metric model/world frame
([Nerfstudio data conventions](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/docs/quickstart/data_conventions.md),
[parser configuration and transforms](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/data/dataparsers/nerfstudio_dataparser.py)).

The paired interpretation is:

| Question | Module 10 Nerfacto | Landed Module 09 NeuS-Facto |
|---|---|---|
| Learned scalar | Non-negative volume density whose ray weights serve rendering | Signed distance whose zero level set defines a surface |
| Photometric supervision | RGB MSE plus proposal interlevel/distortion regularization | RGB reconstruction plus SDF/NeuS regularizers, including Eikonal loss |
| Rendering evidence | Held-out RGB, accumulation, median and expected depth | Held-out RGB, depth, and normals |
| Geometry evidence | Accumulation-qualified rendered depth/point samples; density thresholds only as a sweep | Extracted zero-level mesh, directed surface distances, normals, and Eikonal residual |
| Valid claim | A compact per-scene field can synthesize the declared held-out views | An SDF-oriented field can expose a surface on declared visible support |
| Invalid claim | Good PSNR proves a correct surface or hidden-object completion | A mesh or context fit proves novel-view fidelity or hidden completion |

NeuS-Facto's details and existing measured gates remain owned by the
[Module 09 note](module09-reference-selection.md).  Module 10 must not copy its
surface F-scores into the Nerfacto result or call an arbitrary density
isosurface equivalent to an SDF zero set.

## Train, render, and evaluation protocol

Before training, require compute capability `(10,0)`, a tiny-cuda-nn
hash-encoding forward/backward pass, construction of the pinned Nerfacto config,
and one finite training step.  After training, render all context cameras as a
fit diagnostic and the three target cameras exactly once without gradients.
Persist the checkpoint, resolved YAML, source commits, RGB, accumulation,
median depth, expected depth, camera rays/transforms, wall time, steps/second,
and peak allocated/reserved GPU bytes.  Also retain a fixed `128^3` smoke or
`256^3` full density grid over the common AABB for inspection; it is a field
diagnostic, not a mesh truth claim.

Report separate metric families:

- **Novel-view rendering:** target full-frame PSNR, SSIM, and AlexNet LPIPS;
  target foreground PSNR plus a fixed truth-bounding-box crop's SSIM/LPIPS; and
  context versions labelled `fit_diagnostic`.  The crop/mask is evaluation
  truth only and is never input to optimization.  Full-frame scores remain
  visible because the dark background can dominate this small sphere fixture.
- **Geometry:** on target pixels whose truth is foreground and common-visible,
  report accumulation coverage at `>=0.5`, median-depth and expected-depth
  RMSE/AbsRel, and directed distances/F-scores at 2 cm, 5 cm, and 10 cm for
  their back-projected points.  Nerfstudio depth is distance along its generated
  ray, while the fixture truth is OpenCV camera-axis depth: first reconstruct
  each predicted 3D point from the exact Nerfstudio ray, transform it into the
  declared fixture camera, and compare its `z`; never compare the two raw depth
  arrays as if their parameterizations were identical.  Give unsupported
  target pixels their own counts and errors; never merge them into
  common-visible completeness
  ([pinned ray construction](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/cameras/cameras.py),
  [fixture depth construction](../pipeline/reference_scene.py)).
- **Field diagnostics:** fixed-grid density quantiles, occupied volume at a
  preregistered raw-density threshold set `{0.1, 1, 10, 100}` in inverse model
  metres, and threshold-wise component counts.  Any marching-cubes output
  belongs only to this threshold sweep because density has no canonical
  surface threshold.
- **Comparison:** evaluate the Nerfacto and retained NeuS-Facto target arrays
  with one shared metric implementation and identical masks, colour range,
  crop, depths, and camera transform.  Show rendering and geometry columns side
  by side; do not collapse them into a composite rank.

For the render family, compute each metric per target in RGB `[0,1]`, retain
all three per-view values, and use their arithmetic mean as the primary
aggregate; define PSNR as `-10 log10(MSE)`.  Use the pinned implementation's
`normalize=True` AlexNet LPIPS semantics, and define the foreground crop as the
tight axis-aligned bounding box of the truth foreground mask with no padding.
These rules prevent package defaults, background area, or a change from macro
to pooled averaging from silently moving the regression target
([pinned metric implementation](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/models/nerfacto.py)).

Nerfacto's built-in image evaluator computes PSNR, SSIM, and LPIPS, while its
training loss remains distinct as described above
([image metrics source](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/models/nerfacto.py)).
The insistence on separate geometry follows the documented shape-radiance
ambiguity: NeRF++ identifies potential ambiguity between view-dependent
radiance and shape, and NerfingMVS exhibits high-quality rendered RGB with
substantially wrong depth
([NeRF++ paper](https://arxiv.org/abs/2010.07492),
[NerfingMVS paper](https://openaccess.thecvf.com/content/ICCV2021/html/Wei_NerfingMVS_Guided_Optimization_of_Neural_Radiance_Fields_for_Indoor_Multi-View_ICCV_2021_paper.html)).

The first landing should set regression tolerances only after at least two
verified B200 smoke runs and one full run.  Until those executions exist, record
outcomes as uncalibrated measurements rather than fabricating acceptance
numbers.  The mandatory failure sweep is context-view count (3, 5, 9) with the
same target cameras and the smoke budget held at 1,000 steps x 1,024 rays: use
azimuths `{-45,-5,35}`, the declared five-view set, and the generated nine-view
set respectively.  Fixed pose perturbation, target-only appearance change,
appearance-code re-enablement, and density threshold are labelled secondary
ablations.  Sparse-view degradation is expected in the literature, but every
repository threshold must come from its own controlled measurements
([RegNeRF paper](https://openaccess.thecvf.com/content/CVPR2022/html/Niemeyer_RegNeRF_Regularizing_Neural_Radiance_Fields_for_View_Synthesis_From_Sparse_CVPR_2022_paper.html)).

## B200, dependency, licence, and network boundary

| Item | Locked rule | Evidence and consequence |
|---|---|---|
| Nerfstudio | Commit [`50e0e3c`](https://github.com/nerfstudio-project/nerfstudio/tree/50e0e3c70c775e89333256213363badbf074f29d), Apache-2.0 | Install from the immutable source tree, not floating PyPI; `nerfacto` and `neus-facto` then share one audited framework pin ([licence](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/LICENSE)). |
| GPU runtime | Existing Ubuntu 24.04 / CUDA 12.8.1 / `torch==2.7.1+cu128` / `torchvision==0.22.1+cu128` image | PyTorch 2.7 introduced Blackwell support and CUDA 12.8 wheels; that supports the stack choice, not this method's numerical correctness ([PyTorch 2.7 release](https://pytorch.org/blog/pytorch-2-7/), [repository Insula lock](../insulas/locks.json)). |
| tiny-cuda-nn | Commit [`0109538c37ac0bf613f2bac8de6cda48352feca7`](https://github.com/NVlabs/tiny-cuda-nn/tree/0109538c37ac0bf613f2bac8de6cda48352feca7), built with `TCNN_CUDA_ARCHITECTURES=100` | NVIDIA lists B200 as compute capability 10.0, and CUDA 12.8 adds compiler support for `SM_100`.  The pinned binding reads that environment variable and permits architecture 100 with CUDA >=12.8 ([NVIDIA GPU table](https://developer.nvidia.com/cuda/gpus), [CUDA 12.8 release notes](https://docs.nvidia.com/cuda/archive/12.8.0/cuda-toolkit-release-notes/), [binding setup](https://github.com/NVlabs/tiny-cuda-nn/blob/0109538c37ac0bf613f2bac8de6cda48352feca7/bindings/torch/setup.py)). |
| Incidental learned asset | Reuse the Module 09 hash-locked torchvision AlexNet weights | The pinned model eagerly constructs LPIPS for evaluation, but this asset does not initialize the radiance field and is not a reconstruction prior ([model source](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/models/nerfacto.py), [Module 09 lock description](module09-reference-selection.md)). |

NVIDIA's Blackwell guide says CUDA 12.8 applications need native compute-10.0
cubin or compatible PTX; therefore the adapter must compile native kernels and
execute the smoke gate rather than infer compatibility from package versions
([Blackwell compatibility guide](https://docs.nvidia.com/cuda/archive/12.9.0/blackwell-compatibility-guide/index.html)).
The pinned Nerfstudio installation text says it was tested with CUDA 11.7/11.8,
not CUDA 12.8 or B200, so B200 readiness remains a repository
build-and-execution result rather than an upstream support claim
([pinned installation text](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/README.md)).  Build
and fetch may access the network; reference execution must verify source/image
and AlexNet hashes, mount inputs read-only, and run with networking disabled.
The existing [implicit-surface Dockerfile](../insulas/implicit-surface/Dockerfile)
is the dependency baseline; a shared or copied neural-rendering image must
record its immutable OCI ID and resolved package manifest.

## Candidate comparison

| Candidate | Primary-source semantics | Practical assessment | Outcome |
|---|---|---|---|
| **Pinned Nerfstudio Nerfacto** | Core recommended per-scene density/radiance method; hash field, two proposal networks, scene contraction, pose refinement and appearance codes are explicit components ([docs](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/docs/nerfology/methods/nerfacto.md)). | Reuses the exact framework, tcnn build, licence, LPIPS asset, and much of the container already exercised by Module 09; controlled config can remove pose/appearance confounders. | **Select.** Lowest-integration-cost maintained landing with a direct identical-scene comparison. |
| Nerfstudio `vanilla-nerf` | Two positional-encoding MLP fields, 64 coarse plus 128 importance samples, coarse/fine RGB MSE; registered as slow ([model](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/models/vanilla_nerf.py), [registry](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/configs/method_configs.py)). | Useful historical semantic control, but its pinned preset is wired to the Blender parser and omits the maintained fast-path choices this module is meant to exercise. | Later ablation; not the first maintained adapter. |
| Nerfstudio `instant-ngp-bounded` | Bounded hash field with scene contraction disabled, one occupancy-grid level, black background and 8,192 rays/batch ([exact preset](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/configs/method_configs.py)). | Same framework and a strong speed control, but its occupancy-grid/dynamic-batch pipeline changes more at once and gives a less direct comparison to NeuS-Facto's proposal-sampled path. | Secondary speed ablation. |
| Official original NeRF | Per-scene 5D MLP queried along rays and optimized from posed images through differentiable volume rendering ([paper](https://arxiv.org/abs/2003.08934), [official repository](https://github.com/bmild/nerf/tree/14c55567a6d0fbd75d3fd12b0411f98160ba3237)). | Historically authoritative, but the release specifies Python 3.7, TensorFlow 1.15 and CUDA 10.0, so it would add a second compatibility port solely to reproduce semantics already available in the pinned framework ([environment file](https://github.com/bmild/nerf/blob/14c55567a6d0fbd75d3fd12b0411f98160ba3237/environment.yml)). | Historical reference, not the maintained execution dependency. |
| pixelNeRF | Image-conditioned field trained across many scenes, then feed-forward novel-view synthesis from one/few posed images without per-scene optimization or explicit 3D supervision ([paper](https://openaccess.thecvf.com/content/CVPR2021/html/Yu_pixelNeRF_Neural_Radiance_Fields_From_One_or_Few_Images_CVPR_2021_paper.html), [official repository](https://github.com/sxyu/pixel-nerf/tree/91a044bdd62aebe0ed3a5685ca37cb8a9dc8e8ee)). | Its learned cross-scene prior, training corpus, and checkpoint are part of the evidence.  Substituting it would turn the test into amortized prior evaluation rather than the curriculum's declared optimized field. | Later generalization module only. |

## Historical boundary and caveats

Neural Volumes predates NeRF's per-scene continuous 5D field: it uses an
encoder-decoder to transform multi-view input into a dynamic 3D volume, learns a
latent dynamic-scene representation, and uses differentiable ray marching; its
paper explicitly introduces an irregular grid/warp to mitigate voxel memory and
resolution limits
([Neural Volumes paper](https://arxiv.org/abs/1906.07751)).
It establishes learned renderable volumes, but it is neither this adapter's
static per-scene inference procedure nor a geometry ground-truth method.

NeRF then represents a scene as a continuous function from 3D position and 2D
view direction to density and emitted radiance, optimizes that function for one
scene from known-pose images, and renders novel views with differentiable volume
rendering
([NeRF paper](https://arxiv.org/abs/2003.08934)).
Its success is a novel-view result; density-derived geometry is a distinct
evaluation claim because shape and view-dependent radiance can trade off
([NeRF++ analysis](https://arxiv.org/abs/2010.07492)).

Mip-NeRF's conical frustums and integrated positional encoding address
scale-dependent aliasing in NeRF renderings; they do not turn a per-scene fit
into an amortized model or make generic density a canonical surface
([Mip-NeRF paper](https://openaccess.thecvf.com/content/ICCV2021/html/Barron_Mip-NeRF_A_Multiscale_Representation_for_Anti-Aliasing_Neural_Radiance_Fields_ICCV_2021_paper.html),
[NeuS paper](https://proceedings.neurips.cc/paper/2021/hash/e41e164f7485ec4a28741a2d0ea41c74-Abstract.html)).

Generalizable fields such as pixelNeRF change the statistical problem: an image
encoder conditions the field, and multi-scene training supplies a learned scene
prior that permits feed-forward prediction from one or a few views
([pixelNeRF paper](https://openaccess.thecvf.com/content/CVPR2021/html/Yu_pixelNeRF_Neural_Radiance_Fields_From_One_or_Few_Images_CVPR_2021_paper.html)).
Their output may be useful, but the weights and training distribution are
additional evidence and cannot be compared to this no-checkpoint per-scene fit
as though only architecture changed.  Module 10 should teach that boundary
explicitly: radiance fields support rendering; geometry, generalization, and
completion require separate evidence and separate metrics.
