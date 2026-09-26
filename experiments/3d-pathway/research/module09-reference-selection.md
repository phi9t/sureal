# Module 09 maintained-reference selection

**Decision (research recommendation; historical cutoff 2026-09-25): land a
Nerfstudio `neus-facto` reference adapter first, pinned to
[`50e0e3c70c775e89333256213363badbf074f29d`](https://github.com/nerfstudio-project/nerfstudio/commit/50e0e3c70c775e89333256213363badbf074f29d).
It is a supported core method, rather than a wrapper around an abandoned paper
repository: that tree registers both `neus` and `neus-facto`, and its docs call
them supported surface models ([method registry](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/configs/method_configs.py),
[SDFStudio-extension documentation](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/docs/extensions/sdfstudio.md)).
It is a per-scene, photometrically supervised SDF fit which needs no downloaded
reconstruction checkpoint or redistribution-sensitive training corpus.  The
framework does eagerly initialize LPIPS, so its exact torchvision AlexNet
backbone is a separately hash-locked runtime asset even though LPIPS is not a
training loss or reported score here.  It is **not** a
pretrained shape-completion model, and its rendered novel views are a separate
claim from its extracted surface.

This is the most practical SDF/NeuS-family option that is still present in a
live general-purpose framework at the cutoff.  There is an important
qualification: the selected Nerfstudio commit is dated 2025-07-29.  Its
repository is not archived and it carries an Apache-2.0 project licence, but
no upstream source was found that explicitly validates its surface methods on a
B200.  Accordingly, B200 support is an adapter **build-and-smoke gate**, not a
claim of upstream certification.  The B200-native tiny-cuda-nn build below
removes the known old-architecture blocker.

## What the selected reference is (and is not)

`neus-facto` learns, for one scene, an SDF and geometry features from calibrated
RGB rays; an appearance MLP consumes position, view direction, normal and
geometry features.  The implementation uses two proposal density networks to
place samples, evaluates the SDF field, converts it to NeuS alpha/weights, and
volume-renders RGB, depth and normals ([field](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/fields/sdf_field.py),
[model](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/models/neus_facto.py),
[surface renderer and eikonal loss](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/models/base_surface_model.py)).
The underlying paper is [NeuS](https://arxiv.org/abs/2106.10689); this is a
framework implementation, not a reproduction of an official NeuS checkpoint.

Input is a **single calibrated scene**, not a latent code: RGB images plus
intrinsics and camera-to-world poses.  The SDFStudio parser reads each frame's
`3x3` intrinsics and `camtoworld`, converts COLMAP/OpenCV camera axes to
Nerfstudio axes by flipping camera Y/Z, then may auto-orient poses; it also
uses the supplied scene AABB ([parser](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/data/dataparsers/sdfstudio_dataparser.py)).
For a deterministic controlled adapter, generate an SDFStudio-style
`meta_data.json` from `shared-scene.json`, set `auto_orient=False`, use the
explicit AABB, and record the exact OpenCV-to-Nerfstudio transform.  The source
scene is OpenCV `+X right, +Y down, +Z forward`; all saved mesh and metrics must
be transformed back into that declared metric world frame before comparison.

Output is (1) a learned continuous scalar `sdf(x)` in the bounded scene, (2)
gradient normals, (3) RGB/depth/normal rendered rays, and (4) a marching-cubes
mesh.  The reference observes only the five context RGB views and their
calibration.  It observes neither hold-out target pixels nor either
`hidden-a`/`hidden-b`; the latter must be labelled `unsupported_completion`,
not truth or a successful inferred object.  This is per-scene optimization,
not amortized inference and not DeepSDF-style latent optimization.

## Exact source, dependency, licence, and network boundary

| Item | Pin / rule | Licence and operational consequence |
|---|---|---|
| Surface implementation | Nerfstudio source commit [`50e0e3c70c775e89333256213363badbf074f29d`](https://github.com/nerfstudio-project/nerfstudio/tree/50e0e3c70c775e89333256213363badbf074f29d), dated 2025-07-29 | [Apache-2.0](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/LICENSE); no model checkpoint is used. |
| CUDA/PyTorch runtime | Ubuntu 24.04's Python 3.12; `torch==2.7.1+cu128`, `torchvision==0.22.1+cu128`; CUDA toolkit 12.8.x and a C++17 compiler.  The source's development extra itself pins Torch 2.7.1, but its published install path was only tested with CUDA 11.7/11.8 ([project metadata](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/pyproject.toml), [upstream install text](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/README.md)). | The Insula records resolved runtime versions and its Dockerfile/base digest; do not call CUDA 12.8/B200 an upstream-supported combination. |
| Hash-grid binding | Build `tiny-cuda-nn` from commit [`0109538c37ac0bf613f2bac8de6cda48352feca7`](https://github.com/NVlabs/tiny-cuda-nn/tree/0109538c37ac0bf613f2bac8de6cda48352feca7), with `TCNN_CUDA_ARCHITECTURES=100`; install its `bindings/torch` after Torch. | Its binding build supports architectures through 120 when CUDA is at least 12.8 and takes the architecture from that environment variable ([setup.py](https://github.com/NVlabs/tiny-cuda-nn/blob/0109538c37ac0bf613f2bac8de6cda48352feca7/bindings/torch/setup.py)).  B200 is compute capability 10.0; compile and execute a kernel smoke rather than assuming a prebuilt wheel works. |
| Remaining direct runtime | Install Nerfstudio from the listed source commit, **not** floating PyPI, and pin Pillow 11.1.0 because this source calls the pre-Pillow-12 private encoder signature. | The project metadata has lower-bounded dependencies, so the recorded image ID and runtime manifest attest the executed environment; the OCI build is not claimed bit-reproducible ([metadata](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/pyproject.toml)). |
| Data/checkpoints | Generated RGB/calibration/ground-truth geometry comes from the repo-owned shared scene.  Torchvision AlexNet weights are fetched from `download.pytorch.org`, locked to 244,408,911 bytes and SHA-256 `7be5be79...cdee02`, and mounted read-only solely because model construction initializes LPIPS. | The adapter has no learned scene/category reconstruction checkpoint.  Every generated input and the incidental LPIPS asset are hash verified before offline execution. |

Only `build` and `fetch` may contact package/source endpoints: fetch
source by full commit, fetch exact wheels/source archives, verify their
SHA-256 where separately registered, build tiny-cuda-nn for `sm_100`, and
record the resulting immutable OCI image ID.  `reference` mounts that image,
the verified LPIPS asset, and generated shared-scene inputs with `--network
none`; it rejects a missing lock entry or hash mismatch.

Measured B200 practicality after the one-time native build: the 640x480,
five-view 1,000-step smoke fit plus `128^3` extraction took 42.9 seconds and
5.32 GB measured peak compute memory; the formal nine-view, 20,001-step run
plus `256^3` extraction took 582.9 seconds and 6.40 GB.  These are repository
measurements, not upstream benchmarks.  The upstream `neus-facto` preset is
20,001 iterations, 2,048 rays/batch, two proposal stages, and FP32
([configuration](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/configs/method_configs.py)).
Time, peak allocated/reserved GPU bytes, driver, CUDA runtime/compiler,
compute capability, and actual step rate are therefore required provenance,
not assumed values.

## Candidate comparison

| Candidate | What it observes / inference / output | Cutoff pin and status | B200 and licensing assessment | Outcome |
|---|---|---|---|---|
| **Nerfstudio NeuS-facto (selected)** | Per-scene calibrated multi-view RGB optimization; SDF plus view-dependent colour; volume-rendered image/depth/normal and extracted mesh.  No learned category prior or latent code. | Core source [`50e0e3c`](https://github.com/nerfstudio-project/nerfstudio/tree/50e0e3c70c775e89333256213363badbf074f29d), not archived; its docs explicitly list NeuS/NeuS-facto as supported. | Apache-2.0; no checkpoint/dataset required.  Native tcnn build is the main B200 risk, mitigated by CUDA 12.8+/`sm_100` build gate. | Best first actual surface-reconstruction reference. |
| **Nerfstudio NeuS (same source)** | Same per-scene SDF/ray supervision, but hierarchical NeuS sampling rather than proposal networks; source calls it slow. | Same core supported method and pin. | Same source/licence, but default is 100,000 iterations/1,024 rays and is less practical for the controlled first landing ([config](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/configs/method_configs.py)). | Keep as a semantic ablation, not the first adapter. |
| **SDFStudio** | Unified per-scene UniSurf/VolSDF/NeuS/MonoSDF variants; RGB, optional monocular cues, and mesh extraction. | [`370902a`](https://github.com/autonomousvision/sdfstudio/tree/370902a10dbef08cb3fe4391bd3ed1e227b5c165), last commit 2023-09-10.  Its README says CUDA 11.3 and Torch 1.12.1+cu113 ([README](https://github.com/autonomousvision/sdfstudio/blob/370902a10dbef08cb3fe4391bd3ed1e227b5c165/README.md)). | Apache-2.0 source but old compiled dependency stack; no B200 claim.  It is useful historical method coverage, not maintained enough for the first execution target. | Reject for first landing; Nerfstudio subsumes the two core variants. |
| **Official NeuS** | Per-scene RGB images, masks, and IDR-format world/image plus scale matrices; fitted SDF then mesh/render. | [`6e0a230`](https://github.com/Totoro97/NeuS/tree/6e0a2309d3f8d62d95c749183a965813558662ef), last commit 2024-02-28; official paper implementation. | MIT source; its README pins Torch 1.8.0 and NumPy 1.19.2 ([README](https://github.com/Totoro97/NeuS/blob/6e0a2309d3f8d62d95c749183a965813558662ef/README.md)), unsuitable as an unmodified B200 build.  No pre-trained scene checkpoint is needed, but it is not maintained. | Historical fidelity reference only. |
| **IDR** | Masked RGB plus rough/fixed cameras; jointly optimizes geometry, appearance, and optionally cameras, yielding an implicit surface and rendering. | [`44959e7`](https://github.com/lioryariv/idr/tree/44959e7aac267775e63552d8aac6c2e9f2918cca), last commit 2021-01-07; official [paper](https://arxiv.org/abs/2003.09852). | MIT; official README specifies Python 3.7/Torch 1.2 ([README](https://github.com/lioryariv/idr/blob/44959e7aac267775e63552d8aac6c2e9f2918cca/README.md)).  Camera optimization would also confound this calibrated-scene module. | Reject: stale stack and unnecessary pose ambiguity. |
| **DeepSDF** | A learned category decoder maps `(latent z, x)` to SDF; reconstruction optimizes `z` from sampled SDF/point data, not multi-view RGB inverse rendering. | [`48c19b8`](https://github.com/facebookresearch/DeepSDF/tree/48c19b8d49ed5293da4edd7da8c3941444bc5cd7), archived; official [paper](https://openaccess.thecvf.com/content_CVPR_2019/html/Park_DeepSDF_Learning_Continuous_Signed_Distance_Functions_for_Shape_Representation_CVPR_2019_paper.html). | MIT source, but requires a separately prepared mesh/SDF corpus and C++/Pangolin preprocessing; its README says the release has no completion code ([README](https://github.com/facebookresearch/DeepSDF/blob/48c19b8d49ed5293da4edd7da8c3941444bc5cd7/README.md)). | Do not bend it into an RGB surface-reconstruction adapter; later latent-prior lab only. |
| **Occupancy Networks** | Amortized image/point-cloud/voxel encoder plus occupancy decoder; mesh via thresholding.  It observes one of those inputs, not calibrated multi-view RGB rays. | [`406f794`](https://github.com/autonomousvision/occupancy_networks/tree/406f79468fb8b57b3e76816aaa73b1915c53ad22), last commit 2021-05-07; official [paper](https://arxiv.org/abs/1812.03828). | MIT source; official demo auto-downloads a checkpoint and full preprocessed ShapeNet is 73.4 GB ([README](https://github.com/autonomousvision/occupancy_networks/blob/406f79468fb8b57b3e76816aaa73b1915c53ad22/README.md)).  Its extension and legacy data path need a compatibility port. | Later amortized-completion comparison, with licence/data review; not first. |
| **Neuralangelo** | Per-scene known-pose video/RGB SDF reconstruction with hash grids and a large mesh extraction. | [`94390b6`](https://github.com/NVlabs/neuralangelo/tree/94390b64683c067c620d9e075224ccfe582647d0), last commit 2023-10-02; official [paper](https://arxiv.org/abs/2306.03092). | NVIDIA Source Code License limits use to non-commercial research/evaluation on NVIDIA processors ([licence](https://github.com/NVlabs/neuralangelo/blob/94390b64683c067c620d9e075224ccfe582647d0/LICENSE.md)); upstream Docker is dated and README requires at least 24 GB by default ([README](https://github.com/NVlabs/neuralangelo/blob/94390b64683c067c620d9e075224ccfe582647d0/README.md)). | High-quality later comparison only; licence, stale container, and operational weight rule it out first. |
| **PyTorch3D / nvdiffrast** | Differentiably rasterize an *already parameterized mesh* and optimize vertices/material/camera from images or silhouettes.  This is inverse graphics, but it does not supply a learned occupancy/SDF surface-reconstruction method or topology discovery. | PyTorch3D [`978cd992`](https://github.com/facebookresearch/pytorch3d/tree/978cd99221b9e0a6a568f1d427854d73363265cf), commit 2026-09-15, actively updated; official [mesh fitting tutorial](https://pytorch3d.org/tutorials/fit_textured_mesh).  nvdiffrast's method is [Laine et al.](https://arxiv.org/abs/2011.03277). | PyTorch3D BSD licence ([LICENSE](https://github.com/facebookresearch/pytorch3d/blob/978cd99221b9e0a6a568f1d427854d73363265cf/LICENSE)); its checked-in install guide only lists support through Torch 2.4.1 and requires source builds for newer stacks ([INSTALL](https://github.com/facebookresearch/pytorch3d/blob/978cd99221b9e0a6a568f1d427854d73363265cf/INSTALL.md)). | Best **later differentiable-mesh** extension, not a substitute for the selected field method. |

The GitHub commit links above are immutable trees at or before the cutoff.  A
repository being unarchived is not by itself a guarantee of active support;
the dates are deliberately shown so that the selected core-framework choice
and every historical-paper choice remain distinguishable.

## Adapter protocol

### Controlled data contract

Render the shared scene deterministically at its declared 640x480 OpenCV
intrinsics.  Smoke supplies the five declared context views; full supplies the
nine full context views (the existing fixture's calibrated path), while target
azimuths remain held out for evaluation.  Emit no masks unless the adapter
generates a foreground/background mask deterministically from the known scene;
the first run should use `background_model=none` and an explicit tight AABB to
avoid a learned unbounded background.  Store RGB as lossless PNG, intrinsics,
`camera_to_world`, source-frame convention, Nerfstudio-frame transform, AABB,
near/far, and image/metadata hashes.

Use fixed seed `260925`, deterministic flags where supported, TF32 state
recorded (off for the initial numerical reference), no camera optimization,
no monocular priors, `neus-facto`, `inside_outside=False` for the bounded
object-centric fixture, and fixed scheduler/settings copied into the run
configuration.  Start smoke at 1,000 steps with 1,024 rays/batch and a
`128^3` field query grid; full uses 20,001 steps, 2,048 rays/batch and
`256^3`.  These are adapter profiles, not paper-reproduction settings.  Export
the zero level set in blocks, record extraction wall time and peak memory, and
retain the unmeshed field checkpoint.

### Smoke gate, full gate, and recorded evidence

Before the fit, require all of the following: `torch.cuda.get_device_capability
== (10, 0)`; a tiny-cuda-nn hash-encoding forward/backward pass; Nerfstudio
`neus-facto` one-step forward/backward; and a 32-cube SDF extraction with
finite vertices/faces.  Failure is an `unsupported_environment` result, not a
silent fallback to CPU/PTX from a different architecture.

For every successful run, write an atomic reference result with:

- immutable source/dependency/wheel and container hashes; CUDA driver/runtime,
  compiler, GPU UUID/model/compute capability, `TCNN_CUDA_ARCHITECTURES`, seed,
  determinism/TF32 settings and executed command;
- input and generated-fixture hashes; frames/AABB/transform, exact config,
  sampler counts, iteration count, resource/time summary and field-checkpoint
  hash;
- `field.sdf_grid.float32.npy`, mesh PLY, validity/support masks, context and
  target RGB/depth/normal renders, a 2D residual montage, a sliced SDF SVG,
  and an `artifacts/failure_sweep.csv`;
- metrics separated into `geometry`, `rendering`, and `unsupported` families.

Geometry is scored only in the declared **common-visible** surface region.
Report directed predicted-to-truth accuracy, truth-to-predicted completeness,
F-score at 2 cm/5 cm/10 cm, directed RMSE, normal angular mean/median on
nearest pairs, mesh vertex/face counts, and extraction time.  Report the mean,
p95 and maximum of
`abs(||grad sdf|| - 1)` on a fixed random AABB sample separately as a field
residual; it is not surface accuracy.  The unobserved hidden region has its own
coverage/count field and is never added to completeness/F-score.

Render scores are separate: held-out target RGB PSNR plus camera-axis depth
RMSE/AbsRel on target pixels known to hit common-visible truth.  Context
rendering is a fitting diagnostic, not novel-view evidence.  There is no
generative/completion metric for this adapter; report it as not applicable.

**Measured acceptance tolerances** are controlled-fixture regression gates,
not third-party leaderboard or reconstruction-quality claims.  The first
verified B200 smoke runs produced common-visible F@10 cm of 0.433--0.490,
accuracy RMSE of 0.201--0.224 m, completeness of 0.473--0.582, mean Eikonal
residual of 0.089--0.097, and back-arc target PSNR of 8.15--8.24 dB.  The
formal 20,001-step full run produced F@5 cm 0.225, RMSE 0.205 m,
completeness 0.558, outward-normal error 60.9 degrees, Eikonal residual 0.032,
and target PSNR 8.40 dB.  Its denser 256-cube extraction exposed more
unsupported/spurious zero-level components, so full does not monotonically
improve surface precision even though field regularity improves.

The locked smoke bounds are therefore F@10 cm >= 0.35, RMSE <= 0.30 m,
completeness >= 0.45, outward-normal error <= 85 degrees, mean Eikonal
residual <= 0.20, and target PSNR >= 7 dB.  Full uses F@5 cm >= 0.15,
RMSE <= 0.30 m, completeness >= 0.45, outward-normal error <= 85 degrees,
Eikonal residual <= 0.12, and target PSNR >= 7 dB.  These margins detect gross
runtime, camera, SDF-sign, or asset regressions while preserving the observed
failure as evidence instead of redefining it as success.  Keep a
numerical revalidation tolerance of `rtol=1e-6`, `atol=1e-8` for persisted
float metrics; allow performance only as a recorded distribution, never a
pass/fail portability claim.

The maintained adapter's bounded failure sweep changes extraction resolution
(64/128/profile resolution) and records the indistinguishable hidden-object
counterfactual.  The repo-owned concept lab separately sweeps representation
resolution/storage, coarse topology, surface sampling, and hidden completion.
Hash-grid capacity, mask supervision, pose perturbation, and broader iteration
or view-count sweeps remain explicit extensions rather than fabricated landed
measurements.  Identical context evidence cannot justify claiming either
hidden object as recovered.

## Later extensions

After the field adapter is stable, add a **PyTorch3D differentiable mesh
inverse-graphics** adapter, pinned to the listed 2026-09-15 source commit, to
optimize a deliberately fixed-topology primitive from the same RGB/masks.  It
will teach rasterization gradients, visibility discontinuities and topology
dependence while remaining plainly distinct from SDF topology discovery.  Add
DeepSDF or Occupancy Networks only as an explicitly labelled amortized
category-prior/completion experiment with a separately licensed, hash-locked
corpus and checkpoint—never as evidence that unseen parts of this scene were
measured.  Neuralangelo and the historical official NeuS/IDR repositories are
useful comparison artefacts after a compatibility port, but should not become
the baseline execution dependency.
