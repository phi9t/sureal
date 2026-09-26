# Module 11 maintained-reference selection

**Decision (research recommendation; historical cutoff 2026-09-26): land
Nerfstudio `splatfacto` first, pinned to Nerfstudio commit
[`50e0e3c70c775e89333256213363badbf074f29d`](https://github.com/nerfstudio-project/nerfstudio/tree/50e0e3c70c775e89333256213363badbf074f29d)
and `gsplat` `v1.4.0` commit
[`4d3a3b69db4de0326f983ccf7b7b255271a17b01`](https://github.com/nerfstudio-project/gsplat/tree/4d3a3b69db4de0326f983ccf7b7b255271a17b01).**
At this pin `splatfacto` is a core registered method, uses a full-image data
manager, and depends on exactly `gsplat==1.4.0`
([method registry](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/configs/method_configs.py#L592-L647),
[project dependency](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/pyproject.toml#L57-L68)).
It therefore reuses this repository's already exercised `radiance-field`
Insula—CUDA 12.8.1, Torch 2.7.1+cu128, `TORCH_CUDA_ARCH_LIST=10.0`, and the
same Nerfstudio commit—rather than introducing a second legacy CUDA stack
([repository lock](../insulas/locks.json),
[Dockerfile](../insulas/radiance-field/Dockerfile)).

The direct `gsplat` 3DGS trainer at the same source commit is the **fallback**.
It exposes a smaller paper-shaped surface area, with explicit SfM/random
initialization, 30,000 steps, the default adaptive strategy, and direct
Gaussian parameter checkpoints
([trainer configuration](https://github.com/nerfstudio-project/gsplat/blob/4d3a3b69db4de0326f983ccf7b7b255271a17b01/examples/simple_trainer.py#L36-L154),
[parameter construction](https://github.com/nerfstudio-project/gsplat/blob/4d3a3b69db4de0326f983ccf7b7b255271a17b01/examples/simple_trainer.py#L179-L250)).
Use it only if the pinned Nerfstudio wrapper cannot be made to execute; do not
silently switch implementations under one result ID.  The official original
3DGS repository remains the historical oracle, but its Python 3.7/Torch
1.12.1/CUDA 11.6 environment and research-only licence make it a poor first
B200 execution dependency
([official environment](https://github.com/graphdeco-inria/gaussian-splatting/blob/54c035f7834b564019656c3e3fcc3646292f727d/environment.yml),
[licence](https://github.com/graphdeco-inria/gaussian-splatting/blob/54c035f7834b564019656c3e3fcc3646292f727d/LICENSE.md)).

This recommendation is deliberately a **novel-view rendering reference**.
Neither a 3DGS PLY nor a cloud of anisotropic Gaussians is a triangle mesh,
an SDF zero set, or proof of an accurate physical surface.  The default
adapter must therefore report mesh extraction and hidden-surface completion as
unsupported.  SuGaR and 2DGS are documented below as surface-aware follow-ons,
not post-hoc permission to label ordinary Splatfacto output a reconstruction.
This matches the Module 11 survey's intentionally hybrid scope—posed RGB or
feed-forward features, 3D or surfel-like primitives, rendering and surface
metrics, and primitive-count/view-sparsity/surface-regularization sweeps—while
requiring each executable reference to declare which subset it actually
supports ([curriculum entry](../curriculum.json)).

## Historical credit and the 3DGS contribution

Splatting did not begin with 3DGS.  Pfister et al. introduced surfels as
surface elements in 2000, and Zwicker, Pfister, van Baar, and Gross's 2001
*Surface Splatting* directly rendered opaque and transparent point-sampled
surfaces without connectivity using a screen-space Elliptical Weighted
Average filter
([official ETH publication list](https://cgl.ethz.ch/research/past_projects/surfels/publications.html),
[archived paper and bibliographic record](https://dash.harvard.edu/entities/publication/73120378-88f8-6bd4-e053-0100007fdf3b)).
Kerbl et al. explicitly credit this point-rendering lineage and use Zwicker et
al.'s affine projection of a 3D covariance to image space
([3DGS paper, Sections 2.3 and 4](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/3d_gaussian_splatting_low.pdf)).

The 2023 contribution is the combination of (1) optimized anisotropic 3D
Gaussian radiance primitives, (2) optimization interleaved with adaptive
density control, and (3) a fast differentiable visibility-aware tile
rasterizer; the paper does not claim to have originated splatting
([official paper and project page](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/),
[paper, Introduction](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/3d_gaussian_splatting_low.pdf)).
Module 11 should preserve the registry's existing credit caveat rather than
using “Gaussian splatting” as a synonym for all point-based rendering
([source registry](../sources.json)).

## Original 3DGS semantics

### Evidence, representation, and renderer

Original 3DGS takes images of a **static** scene plus calibrated cameras and
normally initializes from the sparse point cloud produced during SfM; the
paper reports that random initialization also works well on the synthetic
NeRF dataset
([paper, Sections 1 and 3](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/3d_gaussian_splatting_low.pdf)).
Each primitive has a 3D mean, opacity, anisotropic covariance, and spherical
harmonic coefficients for view-dependent colour.  To keep covariance positive
semidefinite during gradient descent, it is parameterized as a rotation and
three scales, `Sigma = R S S^T R^T`
([paper, Sections 3–4](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/3d_gaussian_splatting_low.pdf)).

The renderer projects each 3D covariance through the viewing transform and
the Jacobian of the local affine projection, drops the third row and column to
obtain a 2D covariance, evaluates opacity-weighted 2D Gaussians, and composites
them front-to-back
([paper, Equations 3–6](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/3d_gaussian_splatting_low.pdf)).
The original CUDA algorithm uses 16x16 tiles, culls splats whose 99% confidence
interval misses the frustum, duplicates each surviving splat for every tile it
touches, and radix-sorts a key formed from tile ID and view-space depth once
per frame.  It does not re-sort per pixel, so alpha ordering is approximate
when large splats overlap; pixels stop once accumulated opacity saturates
([paper, Section 6 and Appendix C](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/3d_gaussian_splatting_low.pdf)).

The image formation is radiance compositing, not ray/surface intersection.
The primitive extent and alpha can explain pixels without identifying one
view-consistent surface, and spherical harmonics can absorb view-dependent
appearance.  The paper itself frames mesh reconstruction as future work and
places Gaussians between volumetric and surface representations
([paper, Discussion](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/3d_gaussian_splatting_low.pdf)).

### Objective, optimization, and density control

The original photometric objective is
`(1 - lambda) * L1 + lambda * D-SSIM`, with `lambda=0.2`
([paper, Equation 7](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/3d_gaussian_splatting_low.pdf)).
Adam updates position, scale, rotation, opacity, and SH parameters.  After a
warm-up, the original method densifies every 100 iterations: high view-space
position-gradient Gaussians are cloned when small and split when large;
low-opacity and overly large primitives are pruned, and opacity is periodically
reset to control floaters and runaway primitive counts
([paper, Section 5.2 and Algorithm 1](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/3d_gaussian_splatting_low.pdf)).

Pinned Splatfacto is recognizably 3DGS but not a byte-for-byte reproduction.
It represents the same mean/log-scale/quaternion/opacity/SH parameter groups,
uses the same `0.8 L1 + 0.2 (1-SSIM)` objective by default, and calls gsplat's
tile rasterizer
([model construction](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/models/splatfacto.py#L190-L286),
[render call](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/models/splatfacto.py#L485-L605),
[loss](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/models/splatfacto.py#L652-L710)).
Its defaults also use absolute projected gradients (`absgrad=True`), an opacity
cull threshold of `0.1`, progressive image resolution, and gsplat's
`DefaultStrategy`; these are implementation choices beyond the 2023 paper
([Splatfacto config](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/models/splatfacto.py#L88-L171),
[pinned strategy](https://github.com/nerfstudio-project/gsplat/blob/4d3a3b69db4de0326f983ccf7b7b255271a17b01/gsplat/strategy/default.py#L11-L94)).
The adapter must describe itself as “pinned Splatfacto/gsplat,” not “an exact
reproduction of Kerbl et al.”

### Assumptions, evaluation, and limitations

The paper evaluates held-out-view novel-view synthesis on Mip-NeRF 360,
Tanks & Temples, and Deep Blending with PSNR, SSIM, LPIPS, training time,
render FPS, and memory; its 7k and 30k schedules are rendering benchmarks, not
surface-reconstruction benchmarks
([paper, Section 7 and Tables 1–2](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/3d_gaussian_splatting_low.pdf)).
It assumes a static capture with sufficient multi-view overlap and calibrated
cameras, and normally an SfM initialization.  The reported real-time result is
for the authors' renderer, hardware, scene sizes, and resolution; it must not
be copied into a repository acceptance threshold
([paper, Sections 1, 3, and 7](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/3d_gaussian_splatting_low.pdf)).

The authors report artifacts in poorly observed regions, elongated or
“splotchy” Gaussians, popping from large Gaussians and depth-order changes,
possible need to lower position learning rate for very large scenes, and peak
training memory above 20 GB in their unoptimized prototype.  They also report
several hundred MB for large trained scenes plus 30–500 MB of rasterizer
memory
([paper, Section 7.4](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/3d_gaussian_splatting_low.pdf)).
Those limitations matter here: held-out PSNR can be good while depth or a
post-hoc mesh is wrong, sparse back-arc views are extrapolation rather than
interpolation, and more Gaussians need not mean a cleaner surface.

## Surface-aware variants and mesh semantics

### SuGaR

SuGaR starts from a trained 3DGS scene and adds regularization that encourages
Gaussians to be flat, opaque, well distributed, and aligned with a surface.
It derives an idealized distance function from Gaussian density and matches it
to depth-map-based distance estimates, with an additional normal-alignment
term
([CVPR paper, Sections 4.1 and Equations 8–10](https://openaccess.thecvf.com/content/CVPR2024/papers/Guedon_SuGaR_Surface-Aligned_Gaussian_Splatting_for_Efficient_3D_Mesh_Reconstruction_and_CVPR_2024_paper.pdf)).
Mesh extraction is not “save the Gaussians as PLY”: SuGaR renders training-view
depth, searches each sampled ray for points on a chosen density level set,
attaches density-gradient normals, and applies Poisson reconstruction.  Its
optional final stage binds thin Gaussians to mesh triangles and jointly
optimizes mesh vertices and bound splats
([paper, Sections 4.2–4.3](https://openaccess.thecvf.com/content/CVPR2024/papers/Guedon_SuGaR_Surface-Aligned_Gaussian_Splatting_for_Efficient_3D_Mesh_Reconstruction_and_CVPR_2024_paper.pdf)).

The official repository at cutoff is commit
[`7c10c4ae4a267dece512f5c7f40ed212a0a2ab44`](https://github.com/Anttwo/SuGaR/tree/7c10c4ae4a267dece512f5c7f40ed212a0a2ab44),
dated 2024-09-24.  It recommends a 7k-iteration 3DGS warm-up and in practice
performs separate foreground/background Poisson reconstructions
([official README](https://github.com/Anttwo/SuGaR/blob/7c10c4ae4a267dece512f5c7f40ed212a0a2ab44/README.md)).
Its environment locks Python 3.9, Torch 2.0.1+cu118, PyTorch3D 0.7.4,
Open3D 0.17.0, and CUDA 11.8, and it carries the original 3DGS
research-only licence
([environment](https://github.com/Anttwo/SuGaR/blob/7c10c4ae4a267dece512f5c7f40ed212a0a2ab44/environment.yml),
[licence](https://github.com/Anttwo/SuGaR/blob/7c10c4ae4a267dece512f5c7f40ed212a0a2ab44/LICENSE.md)).
No official B200 recipe or test is provided, so SuGaR is a later compatibility
port, not the first maintained reference.

### 2D Gaussian Splatting

2DGS replaces volumetric ellipsoids with oriented elliptical disks.  It uses
explicit ray–disk intersection for perspective-correct splatting and adds a
depth-distortion loss that concentrates ray weights plus a consistency loss
between splat normals and normals obtained from rendered depth
([SIGGRAPH paper, Sections 4–5 and Equation 16](https://arxiv.org/pdf/2403.17888)).
The representation is more surface-biased, but it is still optimized from
posed images and still composites semi-transparent primitives.  The paper
notes failures on semi-transparent/high-intensity regions, texture-favouring
densification, and a rendering/geometry trade-off that can oversmooth surfaces
([paper, Limitations](https://arxiv.org/pdf/2403.17888)).

Its published mesh is a **TSDF fusion of rendered multi-view depth maps**,
using a chosen depth statistic, voxel size, truncation distance, and camera
set; it is not the union of disk boundaries and is not uniquely determined by
the splat checkpoint
([paper, Section 6.1](https://arxiv.org/pdf/2403.17888),
[official extraction options](https://github.com/hbb1/2d-gaussian-splatting/blob/f3e3b9fa67bbd1c75e05167ff37391d8dab2a678/README.md#bounded-mesh-extraction)).
The official repository warns that bounded extraction needs `depth_trunc`
tuning and that its ideal-pinhole path can fail when the principal point is
off center
([official FAQ](https://github.com/hbb1/2d-gaussian-splatting/blob/f3e3b9fa67bbd1c75e05167ff37391d8dab2a678/README.md#faq)).

The official 2DGS repository is still receiving commits at cutoff; pin
[`f3e3b9fa67bbd1c75e05167ff37391d8dab2a678`](https://github.com/hbb1/2d-gaussian-splatting/tree/f3e3b9fa67bbd1c75e05167ff37391d8dab2a678),
dated 2026-08-25.  Its checked-in environment nevertheless specifies Python
3.8.18, Torch 2.0.0, Torchvision 0.15.0, and Open3D 0.18.0, and its custom
CUDA rasterizer is a submodule rather than the already locked gsplat kernel
([environment](https://github.com/hbb1/2d-gaussian-splatting/blob/f3e3b9fa67bbd1c75e05167ff37391d8dab2a678/environment.yml),
[submodule manifest](https://github.com/hbb1/2d-gaussian-splatting/blob/f3e3b9fa67bbd1c75e05167ff37391d8dab2a678/.gitmodules)).
It also inherits the 3DGS research-only licence
([licence](https://github.com/hbb1/2d-gaussian-splatting/blob/f3e3b9fa67bbd1c75e05167ff37391d8dab2a678/LICENSE.md)).
It is the best paper-faithful later surface adapter, but its B200 source-build,
TSDF parameters, and licence need their own gate.

Pinned `gsplat` also contains an Apache-2.0 2DGS example with normal and
distortion losses, which is a useful **porting fallback**, not automatically a
paper reproduction: those losses are disabled in the example defaults and its
script does not perform the official TSDF mesh extraction
([example configuration](https://github.com/nerfstudio-project/gsplat/blob/4d3a3b69db4de0326f983ccf7b7b255271a17b01/examples/simple_trainer_2dgs.py#L36-L164),
[loss assembly](https://github.com/nerfstudio-project/gsplat/blob/4d3a3b69db4de0326f983ccf7b7b255271a17b01/examples/simple_trainer_2dgs.py#L581-L629)).

### Required vocabulary for artifacts and metrics

| Artifact | What it means | What it does **not** mean |
|---|---|---|
| `gaussians.ply` / parameter checkpoint | Means, scales, rotations, opacity, and SH/colour for renderable primitives | A point cloud sampled from a physical surface, a watertight mesh, or an SDF |
| 3DGS expected/median depth | A statistic of ordered alpha-compositing weights along a camera ray | The first intersection with a view-consistent surface |
| SuGaR mesh | Poisson reconstruction of selected density-level points and normals sampled through training views | A canonical isosurface of vanilla 3DGS |
| 2DGS mesh | TSDF fusion of selected rendered depth maps under fixed voxel/truncation/camera settings | The raw 2D disk set or a parameter-free extraction |
| Mesh rendered with bound splats | A hybrid appearance representation whose splats are attached to mesh triangles | Ordinary textured-mesh rasterization or evidence that triangle geometry alone explains the pixels |

Any mesh result must name the extractor, its source commit, all extraction
parameters, camera set, coordinate transform, and checkpoint hash.  It must
not be entered under the vanilla Splatfacto result ID.

## Feed-forward splat prediction is a different inference problem

The registry's amortized source is Splatt3R.  It adds a Gaussian decoder to a
frozen MASt3R pointmap backbone and predicts one set of pixel-aligned
Gaussians from each of two uncalibrated images in one forward pass; it neither
optimizes a fresh scene from the five/nine posed context views nor explicitly
predicts input camera parameters
([paper, Figure 1 and Sections 1, 3](https://splatt3r.active.vision/static/pdfs/splatt3r.pdf)).
The union of the two predicted sets is trained first through MASt3R geometry
and then through masked target-view MSE plus LPIPS.  The mask uses training-time
ground-truth depth and poses to avoid penalizing regions not visible from a
context image
([paper, Section 3.4](https://splatt3r.active.vision/static/pdfs/splatt3r.pdf)).

The authors explicitly state that this masking teaches visible reconstruction,
not guessing unseen regions, and evaluate PSNR/SSIM/LPIPS on ScanNet++ stereo
pairs at different overlap/baseline regimes
([paper, Sections 4.1–4.2](https://splatt3r.active.vision/static/pdfs/splatt3r.pdf)).
Thus “zero-shot” means no per-scene optimization after cross-scene training;
it does not mean training-data-free, prior-free, or hidden-scene completion.
Its official release requires a pretrained MASt3R checkpoint and a separately
downloaded Splatt3R checkpoint trained on ScanNet++, and exports a Gaussian
PLY rather than a triangle mesh
([official README](https://github.com/btsmart/splatt3r/blob/bda1dd07cf84b9189baabb1b8beac243959cfe5d/README.md)).

Pin the official source, if a later amortized comparison is approved, to
[`bda1dd07cf84b9189baabb1b8beac243959cfe5d`](https://github.com/btsmart/splatt3r/tree/bda1dd07cf84b9189baabb1b8beac243959cfe5d),
dated 2024-11-23.  Its environment is Python 3.11, Torch 2.3.1+cu121,
Torchvision 0.18.1 and a separately installed modified Gaussian rasterizer;
the repository is CC BY-NC 4.0
([environment](https://github.com/btsmart/splatt3r/blob/bda1dd07cf84b9189baabb1b8beac243959cfe5d/environment.yml),
[licence](https://github.com/btsmart/splatt3r/blob/bda1dd07cf84b9189baabb1b8beac243959cfe5d/License)).
There is no official B200 recipe.  Checkpoint licences, exact bytes, MASt3R
transitive terms, and training-distribution provenance must be reviewed and
locked before execution; Splatt3R is not a fallback for the no-checkpoint
per-scene Splatfacto reference.

## Candidate comparison

| Candidate | Source pin, licence, and runtime | Semantics and assessment | Outcome |
|---|---|---|---|
| **Nerfstudio Splatfacto + gsplat (selected)** | Nerfstudio [`50e0e3c`](https://github.com/nerfstudio-project/nerfstudio/tree/50e0e3c70c775e89333256213363badbf074f29d) and gsplat [`4d3a3b6`](https://github.com/nerfstudio-project/gsplat/tree/4d3a3b69db4de0326f983ccf7b7b255271a17b01), both [Apache-2.0](https://github.com/nerfstudio-project/gsplat/blob/4d3a3b69db4de0326f983ccf7b7b255271a17b01/LICENSE); exact gsplat version already exists in the repository runtime lock. | Per-scene posed-RGB optimization, explicit 3D Gaussian radiance primitives, no pretrained scene/category checkpoint. Lowest integration and licence risk; not a mesh method and not paper-exact because Splatfacto uses later strategy choices. | **Land first.** |
| Direct gsplat 3DGS trainer | Same gsplat pin and Apache-2.0 licence; source-build its CUDA extension for `sm_100`. | Smaller, closer-to-paper training loop and checkpoint. It loses Nerfstudio's already integrated parser/config/evaluation layer. | **Declared fallback** if Splatfacto wrapper fails; separate adapter/result ID. |
| Official 3DGS | [`54c035f`](https://github.com/graphdeco-inria/gaussian-splatting/tree/54c035f7834b564019656c3e3fcc3646292f727d), dated 2024-10-30; research-only licence; Python 3.7/Torch 1.12.1/CUDA 11.6. | Historical author implementation, including exact custom rasterizer lineage. Submodules and old binary stack require a B200 port, and the licence is less permissive. | Historical oracle, not first runtime. |
| Official SuGaR | [`7c10c4a`](https://github.com/Anttwo/SuGaR/tree/7c10c4ae4a267dece512f5c7f40ed212a0a2ab44); research-only 3DGS licence; Torch 2.0.1/cu118 plus PyTorch3D/Open3D. | Explicit surface-alignment regularization, Poisson extraction, optional mesh-bound splats. Correct answer when the experiment specifically asks for SuGaR mesh semantics. | Later surface adapter after licence and B200 port. |
| Official 2DGS | [`f3e3b9f`](https://github.com/hbb1/2d-gaussian-splatting/tree/f3e3b9fa67bbd1c75e05167ff37391d8dab2a678); active at cutoff but research-only licence and old Torch/custom rasterizer stack. | Surface-like disks, perspective-correct ray–disk intersections, normal/distortion regularizers, TSDF extraction. Strongest registry candidate for joint rendering/geometry, but more integration risk. | Preferred second, surface-aware adapter. |
| gsplat 2DGS example | Same Apache-2.0 gsplat pin and B200 build path as selected reference. | Maintained rasterization path and optional surface losses, but defaults disable them and no paper extraction is implemented. | Compatibility prototype only; never call it an official 2DGS reproduction. |
| Splatt3R | [`bda1dd0`](https://github.com/btsmart/splatt3r/tree/bda1dd07cf84b9189baabb1b8beac243959cfe5d), CC BY-NC 4.0, Torch 2.3.1/cu121 plus MASt3R and Splatt3R checkpoints. | Feed-forward two-image, uncalibrated, cross-scene learned prior; visible-region NVS, not per-scene optimization or mesh extraction. | Later amortized-prior comparison only. |

Repository activity is only a maintenance signal, not a B200 guarantee.  Of
these candidates, only the selected/fallback gsplat path shares the actual
CUDA 12.8/Torch 2.7 build already locked here; even that combination still
needs an execution gate.

## Exact selected dependency and offline boundary

| Item | Required pin / rule | Consequence |
|---|---|---|
| Nerfstudio | Commit [`50e0e3c`](https://github.com/nerfstudio-project/nerfstudio/commit/50e0e3c70c775e89333256213363badbf074f29d), Apache-2.0 | Install detached source with `--no-deps`; preserve the existing exact Python closure and resolved-manifest comparison. |
| gsplat | Tag `v1.4.0` resolves to commit [`4d3a3b6`](https://github.com/nerfstudio-project/gsplat/commit/4d3a3b69db4de0326f983ccf7b7b255271a17b01), Apache-2.0 | Replace the package-version-only provenance with a detached source checkout, source-tree hash, and native extension build.  The pinned setup builds a PyTorch `CUDAExtension` and honours the architecture selected by PyTorch's extension machinery ([setup](https://github.com/nerfstudio-project/gsplat/blob/4d3a3b69db4de0326f983ccf7b7b255271a17b01/setup.py)). |
| GPU runtime | Existing CUDA 12.8.1 / Torch 2.7.1+cu128 / Torchvision 0.22.1+cu128 / Python 3.12 image; `TORCH_CUDA_ARCH_LIST=10.0` | PyTorch 2.7 is the first official release with Blackwell and CUDA 12.8 wheels; B200 is compute capability 10.0 ([PyTorch release](https://pytorch.org/blog/pytorch-2-7/), [NVIDIA GPU table](https://developer.nvidia.com/cuda/gpus)).  This establishes a plausible toolchain, not numerical validation. |
| Incidental metric asset | Reuse the byte/hash-locked torchvision AlexNet weights from Modules 09–10 | Splatfacto eagerly constructs LPIPS even though LPIPS is not in its training loss ([model initialization](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/models/splatfacto.py#L252-L261)).  Record it as a metric dependency, not a scene prior. |
| Scene assets | Repository-generated context RGB and calibration only | No pretrained reconstruction checkpoint and no downloaded dataset.  Evaluation depth/masks/normals and target RGB stay outside the training mount. |

`fetch` may obtain the two source trees and exact Python/source archives;
`build` may compile gsplat with CUDA 12.8 for `sm_100`, create the immutable
OCI image, and record all input hashes and `pip freeze --all`.  `reference`
must run with `--network none`, verified read-only source/image/input mounts,
and a separate writable output mount.  Do not rely on first-import JIT that
mutates an untracked cache at reference time: build and execute a gsplat
forward/backward kernel during image construction, retain its build log, and
repeat a tiny runtime kernel smoke after network isolation.

The pinned gsplat release predates public Blackwell hardware and contains no
official B200 CI claim.  NVIDIA's guide requires native compute-10.0 cubin or
compatible PTX for Blackwell, so an architecture inspection plus execution is
mandatory
([Blackwell compatibility guide](https://docs.nvidia.com/cuda/archive/12.9.0/blackwell-compatibility-guide/index.html)).
Failure to compile or execute is `unsupported_environment`; it is not
permission to fetch a newer wheel, drop to CPU, or float to gsplat main.

## Controlled-scene adapter protocol

### Inputs, frame contract, and controlled overrides

Use the same bounded analytic sphere fixture as Modules 09–10.  Smoke uses the
five declared context azimuths `{-45,-25,-5,15,35}`; full uses the generated
nine-view arc `{-45,-35,-25,-15,-5,5,15,25,35}`.  Both render the same three
held-out targets `{120,150,180}` at 640x480 with the declared OpenCV
intrinsics
([shared scene](../shared-scene.json),
[fixture generator](../pipeline/reference_scene.py),
[Module 10 protocol](module10-reference-selection.md)).
Only context RGB and exact intrinsics/poses are training evidence.  Target RGB,
truth depth/normals/masks, and common-visible support arrays are evaluator-only
and must not appear in the Nerfstudio train/eval dataset.

Use the same explicit OpenCV-to-Nerfstudio camera transform as Module 10:
right-multiply each camera-to-world by `diag(1,-1,-1,1)`, disable pose
auto-orientation/centering/scaling, and persist both directions of the
transform
([Nerfstudio camera convention](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/docs/quickstart/data_conventions.md),
[pinned parser](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/data/dataparsers/nerfstudio_dataparser.py)).

Deep-copy `method_configs["splatfacto"]`, save the resolved config, and make
only these declared changes:

| Setting | Pinned Splatfacto value | Module 11 controlled value and reason |
|---|---:|---|
| Steps | 30,000 | Smoke 1,000; full 30,000.  Smoke crosses the 500-step refinement warm-up; full preserves the upstream budget. |
| Initialization | SfM points when present; otherwise configurable random initialization | `random_init=True`, seed `260925`, `num_random=50,000`, `random_scale=2.0`, which samples only the declared `[-1,1]^3` model AABB.  This avoids leaking evaluator depth or adding a context-only SfM implementation to the first adapter.  Label it a controlled departure from the paper. |
| Camera optimizer | `off` in the model default | Keep off; poses are exact. |
| Background | `random` | `black`, matching the opaque RGB fixture; random background with three-channel black training images would change the target rather than merely composite alpha. |
| Resolution schedule | two initial downscales, doubling every 3,000 steps | Keep unchanged and record per-step resolution. |
| SH | degree 3, one degree added every 1,000 steps | Keep unchanged. |
| Densification | warm-up 500; refine every 100; stop at 15,000; absolute gradients; opacity reset every 3,000; Splatfacto thresholds | Keep unchanged for the primary run; record realized Gaussian count after every refinement event. |
| Loss | `0.8 L1 + 0.2 (1-SSIM)`; scale regularization off | Keep unchanged.  No mask, depth, normal, or surface loss. |
| Rasterization | classic EWA mode | Keep `classic` for the baseline; antialiased mode is a separately named secondary sweep because exported PLY semantics differ ([config warning](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/models/splatfacto.py#L145-L155)). |
| Evaluation cadence | one image every 100, all images every 1,000, save every 2,000 | Disable periodic target evaluation and save one final checkpoint.  Target cameras are rendered once after training. |
| Appearance/camera extras | Bilateral grid off; scale regularization off | Keep off; the synthetic fixture has fixed appearance and the base question is unregularized 3DGS rendering. |

The upstream defaults come from the pinned
[`splatfacto` preset](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/configs/method_configs.py#L592-L647)
and
[`SplatfactoModelConfig`](https://github.com/nerfstudio-project/nerfstudio/blob/50e0e3c70c775e89333256213363badbf074f29d/nerfstudio/models/splatfacto.py#L88-L171).
The overrides are repository policy, not claimed upstream recommendations.
Run one GPU with TF32 off and deterministic PyTorch/cuDNN flags where
available, but record that atomic CUDA updates and sorting may still prevent
bitwise reproducibility.

### Preflight and required artifacts

Before training, require all of the following:

- device reports `(10,0)` and the built extension contains `sm_100` or
  accepted compute-10.0 PTX;
- a two-Gaussian forward render, scalar loss backward pass, and one optimizer
  update all produce finite values under `--network none`;
- the exact pinned Splatfacto config constructs without fetching assets, and a
  one-image training step completes;
- camera round-trip and a synthetic center-ray projection agree within
  `1e-6`, preventing a visually plausible axis flip.

Each successful run must retain:

- source commits/tree hashes, source/wheel/archive hashes, OCI image ID,
  driver/runtime/compiler versions, GPU UUID/model/capability, build flags,
  executed command, seed, TF32/determinism state, wall time, step rate, and
  peak allocated/reserved GPU bytes;
- complete input manifest and hashes, exact camera matrices and frame
  transform, resolved YAML, per-step resolution, loss trace, primitive-count
  trace, and checkpoint hash;
- `gaussians.npz` with typed means/log-scales/quaternions/opacity logits/SH,
  a standard splat `gaussians.ply` labelled `renderable_primitives_not_mesh`,
  and a finite/range/statistics manifest for every parameter array;
- lossless context/target RGB, accumulation and expected depth arrays, exact
  render cameras, per-view metric JSON, warm/cold render benchmark CSV,
  `artifacts/failure_sweep.csv`, and one metric-summary SVG;
- `unsupported.json` explicitly setting `triangle_mesh`, `mesh_f_score`,
  `canonical_surface`, and `hidden_surface_completion` to unsupported for the
  vanilla reference.

Do not emit a triangle-face array with zero faces and call that a mesh.  Do not
evaluate the target until after the final checkpoint.  Do not use target
metrics for early stopping or hyperparameter selection.

### Metrics and interpretation

Report three separate families:

1. **Novel-view rendering.** Per target and macro mean: full-frame PSNR, fixed
   Gaussian-window SSIM, and pinned AlexNet LPIPS; foreground PSNR and the
   tight truth-foreground crop's SSIM/LPIPS; plus context versions explicitly
   labelled `fit_diagnostic`.  Reuse Module 10's host evaluator so metric
   implementation, masks, crops, and aggregation are identical.
2. **Rendered geometry diagnostic.** On target truth-foreground pixels with
   common-visible support, report accumulation coverage at `>=0.5`, expected
   depth RMSE/AbsRel, and back-projected point accuracy/completeness/F-score at
   2, 5, and 10 cm.  Convert gsplat expected ray distance to the fixture's
   OpenCV camera-axis `z` before comparison.  Report unsupported target pixels
   separately.  These are **view-conditioned depth/point diagnostics**, not a
   mesh score or proof of one global surface.
3. **Representation and performance.** Final and peak primitive count, count
   trajectory, parameter bytes, PLY bytes, training time/steps per second,
   peak memory, and post-warm-up raster FPS at 640x480 for the three exact
   target cameras.  Synchronize CUDA around timing; report median and p95 over
   at least 100 frames after 20 warm-up frames.  FPS is hardware/configuration
   evidence, not a paper reproduction.

The held-out back arc is deliberately harsh: training cameras cover only
-45 to +35 degrees, while targets are 120–180 degrees.  Novel-view scores
therefore measure extrapolation with unsupported content as well as local
rendering fidelity.  They must be reported beside the common-visible split,
not summarized as generic “scene reconstruction.”

### Failure sweeps

The mandatory smoke-budget sweeps use the same seed, evaluator, and target
cameras and write both the intervention and realized primitive count:

- **view sparsity:** context counts 3/5/9, with three views
  `{-45,-5,35}`, the declared five, and the generated nine;
- **primitive budget:** random initial counts `{10k,50k,100k}` with adaptive
  refinement disabled, plus the 50k primary initialization with default
  refinement.  This distinguishes parameter count from the densification
  algorithm instead of pretending its emergent count is directly controlled;
- **density-control sensitivity:** projected-gradient threshold at
  `{0.5x,1x,2x}` the pinned value, keeping every other setting fixed;
- **geometric-bias guardrail:** Splatfacto scale regularization off/on as a
  secondary anisotropy test, labelled `scale_regularization`, **not**
  `surface_regularization`.  Vanilla Splatfacto has no SuGaR/2DGS surface
  objective, so the curriculum's true surface-regularization sweep remains
  unsupported until a separately pinned surface adapter lands;
- **initialization:** random versus context-only SfM is optional after a
  deterministic context-only SfM artifact exists.  Evaluator depth or truth
  points may never seed Gaussians.

Persist failed runs too: OOM step and last primitive count, NaN/Inf parameter,
extension error, compile log, zero-gradient fraction, or camera-projection
failure are evidence, not rows to discard.  At most one variable changes per
primary sweep row.

### Acceptance calibration plan

No unexecuted paper number or Module 10 Nerfacto threshold should be copied
into Module 11.  First land the adapter with schema/finite/provenance-only
gates, then on one locked B200 image run:

1. five independent smoke fits at seeds `{260925,260926,260927,260928,260929}`
   and two full fits at seeds `{260925,260926}`;
2. one exact rerender of a retained checkpoint to separate training variance
   from renderer/evaluator variance;
3. the mandatory 3/5/9 view and primitive-budget sweeps;
4. one intentional camera-axis flip and one disabled-densification negative
   control, which must degrade the appropriate projection/render or
   primitive-growth checks.

Freeze the baseline image ID and raw per-view results before choosing numeric
thresholds.  For metrics where larger is better, set a regression floor below
the worst valid calibration run by a preregistered margin; for errors, set a
ceiling above the worst valid run.  The margin must be at least the larger of
three observed-seed standard deviations or 10% of the observed range.  Use
schema/execution gates, not quality thresholds, for FPS and memory until a
second B200 host quantifies system variance.  Recalibration requires a new
source/image/evaluator version and retained old/new comparison; it may not be
done merely because a regression failed.

## Completion and unsupported guardrails

A Module 11 run is complete only when the exact source/image/input hashes are
verified, all preflight checks pass, the requested smoke or full optimization
finishes, all declared target/context arrays and metrics are present, the
failure sweep is present, and atomic result validation succeeds.  Anything
less is `incomplete` or `unsupported_environment`, never a passing synthetic
placeholder.

The first Splatfacto adapter supports only these claims:

- a pinned explicit Gaussian radiance representation was optimized from the
  declared posed context RGB;
- it rendered the declared held-out cameras with the recorded image/depth
  statistics, primitive count, speed, and memory on the recorded machine;
- common-visible rendered-depth diagnostics answer a narrower geometric
  question than mesh reconstruction.

It explicitly does **not** support claims of a watertight or canonical
surface, mesh F-score, physical density, unseen-object recovery, semantic
understanding, generative uncertainty, cross-scene generalization, exact
reproduction of Kerbl et al., or upstream-certified B200 support.  Empty or
hallucinated back-side splats are `unsupported_completion`, not successful
completion.  A later SuGaR/2DGS/Splatt3R run must have its own adapter ID,
licence/checkpoint/source locks, observation contract, metrics, and acceptance
calibration; its numbers must never overwrite the vanilla 3DGS result.
