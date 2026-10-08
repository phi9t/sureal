# Module 14: dynamic 3D and 4D representations

**Primary-source synthesis; historical cutoff 2026-09-25.**

## Research conclusion

Dynamic reconstruction does not become well defined merely by appending time
to a static representation. A video measurement couples camera motion, object
motion, non-rigid deformation, appearance change, visibility, and illumination.
Without a static reference, calibrated cameras, or another motion prior, a
time-dependent world transform can be exchanged between the camera and the
scene without changing the rendered images. The first lesson of this module is
therefore observability: image motion is evidence, not a unique 3D motion
explanation.

The literature has developed several different ways to close that gap:

1. low-rank or articulated shape models constrain the family of admissible
   deformations;
2. RGB-D fusion adds metric range and estimates a canonical-to-live warp;
3. scene-flow models predict explicit 3D displacement and often use optical
   flow, depth, smoothness, and cycle priors;
4. dynamic radiance fields optimize a time-conditioned renderer, sometimes
   through a canonical deformation field;
5. persistent Gaussian models attach trajectories to explicit renderable
   primitives; and
6. recent feed-forward models jointly predict world-frame geometry and tracks.

These are not interchangeable. A model may render held-out views well while
having no stable material correspondence. Conversely, a tracker can retain
pixel identity through occlusion while providing only pseudo-depth rather than
metric geometry. The lab must report image, geometry, motion, visibility, and
post-occlusion identity metrics separately.

The strongest endpoint for Surflo is equally specific. A deterministic dynamic
reconstruction estimates one time-varying explanation of an observed video. It
does not sample alternative futures or complete-scene hypotheses. Adding time
to independently sampled points also does not create a persistent dynamic
scene: one sampled scene state must retain object identity and hidden choices
across points, cameras, time, occlusion, and later queries.

## Terminology guardrails

| Term | Meaning in this pathway | It does **not** establish |
|---|---|---|
| **Optical flow** | Apparent 2D image displacement between frames. | 3D motion, camera/object separation, or material identity through occlusion. |
| **Scene flow** | A 3D motion field for scene points, introduced as the 3D analogue of optical flow by Vedula et al. | A reconstructed surface, a renderer, or long-range persistent tracks by itself. |
| **Non-rigid reconstruction** | Geometry plus a constrained deformation or shape trajectory. | Topology change, arbitrary new content, or calibrated uncertainty. |
| **Dynamic novel-view synthesis** | Render an observed dynamic sequence at a requested view and time. | Accurate geometry, physical motion, persistent identity, or future prediction. |
| **Canonical space** | A reference domain to which time-varying observations are mapped. | That the map is bijective, physically meaningful, topology preserving, or unique. |
| **Time-conditioned field** | A function whose output varies with time. | Correspondence: two time queries may be modeled without a shared material point. |
| **Persistent primitive** | One indexed primitive is intentionally propagated through time. | Semantic identity unless birth, death, occlusion, splitting, and merging are modeled and tested. |
| **4D reconstruction** | Recovery of 3D structure and its evolution over time from observations. | Generative future sampling or a posterior over unseen dynamic worlds. |
| **4D generation** | Synthesis of a dynamic asset or video, often from text, one image, or another sparse condition. | Reconstruction of the observed event or evidence-calibrated posterior sampling. |
| **Temporal consistency** | A stated cross-time property with a metric, such as track error or flow-warp error. | Persistent identity merely because adjacent rendered frames do not flicker. |
| **Re-identification after occlusion** | The same tracked entity returns at the correct location and identity after an unobserved interval. | Smooth interpolation behind the occluder. |

Historical credit also needs care. Non-rigid factorization and 3D scene flow
predate neural fields by two decades; canonical deformation and splatting
predate NeRF and 3D Gaussian Splatting. “Dynamic NeRF” and “4DGS” name later
representations, not the invention of dynamic reconstruction or splatting.

## Observability and defining mathematics

Let a world point have trajectory \(X_i(t)\), camera extrinsics
\(T_{cw}(t)\), intrinsics \(K(t)\), and image measurement

\[
u_i(t)=\pi\!\left(K(t)T_{cw}(t)X_i(t)\right).
\]

For an arbitrary time-dependent world transform \(H(t)\), the substitutions

\[
X'_i(t)=H(t)X_i(t),\qquad
T'_{cw}(t)=T_{cw}(t)H(t)^{-1}
\]

produce the same projected points. Static background, known calibration,
metric depth, inertial information, multi-camera simultaneity, rigidity, or a
deformation prior is needed to choose a gauge. A moving-camera/moving-object
experiment should expose this ambiguity rather than quietly supplying perfect
poses to every method.

The scene flow of a material point may be written

\[
v_i(t)=X_i(t+\Delta t)-X_i(t),
\]

while a canonical deformation model uses a warp

\[
X_c=W_t(X_t), \qquad (c,\sigma)=F(X_c,d,a_t).
\]

The first equation explicitly denotes a displacement; the second supplies a
shared coordinate system, but a general \(W_t\) need not be invertible and may
fail when topology changes. HyperNeRF's extra ambient dimensions were
introduced precisely because a single ordinary canonical 3D template cannot
represent every topological event continuously.

For a dynamic Gaussian indexed by \(i\), a useful bookkeeping form is

\[
G_i(t)=\{\mu_i(t),R_i(t),s_i(t),\alpha_i(t),c_i(t)\}.
\]

Dynamic 3D Gaussians deliberately fixes or regularizes attributes so index
\(i\) follows the same physical region. A deformation network that simply
outputs \(G_i(t)\) can render smoothly without that stronger identity contract.
The distinction must be tested, not inferred from the representation name.

For an object hidden over frames \([t_a,t_b]\), report reappearance error on
the first visible frame

\[
E_{\mathrm{reid}}=
\sqrt{\frac{1}{|Q|}\sum_{i\in Q}
\left\|\widehat X_i(t_b+1)-X_i(t_b+1)\right\|_2^2},
\]

together with identity switches and visibility classification. Adjacent-frame
PSNR or optical-flow warp error cannot substitute for this measurement.

## Primary-source records

The records below state what each paper can support in the pathway. “Failure
mode” includes limitations stated by the authors and direct consequences of the
published evidence contract; it is not a claim that later work never addressed
the limitation.

### 1. Bregler, Hertzmann, and Biermann — non-rigid factorization

- **Proposed ID:** `bregler-nrsfm-2000`
- **Title / authors / venue:** *Recovering Non-Rigid 3D Shape from Image
  Streams*, Christoph Bregler, Aaron Hertzmann, Henning Biermann, CVPR 2000.
- **Primary source:** [author publication page](https://chris.bregler.com/pubs.html),
  [paper](https://cs.nyu.edu/media/publications/TR1999-787.pdf),
  [DOI 10.1109/CVPR.2000.854941](https://doi.org/10.1109/CVPR.2000.854941).
- **Supported claim:** under orthographic projection, a non-rigid shape in each
  frame can be modeled as a linear combination of basis shapes, yielding a
  higher-rank measurement matrix that can be factorized into pose,
  configuration, and basis shape.
- **Assumptions and objective:** tracked 2D points, orthographic camera, a
  low-dimensional linear shape basis, and sufficiently informative motion;
  optimize measurement-matrix factorization and metric constraints.
- **Reported evidence:** reconstructed face and animal examples and 2D/3D
  accuracy experiments; this predates modern standardized dynamic-view metrics.
- **Failure boundary:** missing or wrong tracks, perspective effects, and
  deformations outside a global linear basis violate the model. Factorization
  also retains gauge and basis ambiguities.
- **Executable reference:** no maintained official implementation is known;
  use the repo-owned low-rank concept lab rather than reviving historical code.
- **Lab relevance:** establishes the controlled “motion prior makes monocular
  dynamics solvable” baseline and a counterpoint to unconstrained per-frame
  geometry.
- **Credit caveat:** foundational for non-rigid structure from motion, but not
  the origin of all deformable modeling or motion capture.

### 2. Vedula et al. — three-dimensional scene flow

- **Proposed ID:** `vedula-scene-flow-1999`
- **Title / authors / venue:** *Three-Dimensional Scene Flow*, Sundar Vedula,
  Simon Baker, Peter Rander, Robert Collins, Takeo Kanade, ICCV 1999.
- **Primary source:** [DOI
  10.1109/ICCV.1999.790293](https://doi.org/10.1109/ICCV.1999.790293).
- **Supported claim:** scene flow is the 3D motion field of scene points, the
  world-space analogue of optical flow; multi-view image motion and known scene
  structure constrain that field.
- **Assumptions and objective:** calibrated multi-camera observations and
  correspondences or known geometry; solve for 3D velocity consistent with the
  projected image velocities.
- **Reported evidence:** motion-field accuracy on controlled synthetic and
  captured sequences, rather than novel-view image quality.
- **Failure boundary:** scene flow is underconstrained with insufficient views,
  poor calibration, occlusion, or bad optical flow; it does not itself decide
  surface topology or long-term point identity.
- **Executable reference:** no maintained official package is known; the lab
  should implement the projection/Jacobian relation directly.
- **Lab relevance:** gives the correct target for separating image motion from
  world motion in the three camera/object-motion variants.
- **Credit caveat:** modern neural “scene flow fields” inherit this quantity;
  they did not introduce 3D scene flow.

### 3. Newcombe, Fox, and Seitz — DynamicFusion

- **Proposed ID:** `newcombe-dynamicfusion-2015`
- **Title / authors / venue:** *DynamicFusion: Reconstruction and Tracking of
  Non-Rigid Scenes in Real-Time*, Richard A. Newcombe, Dieter Fox, Steven M.
  Seitz, CVPR 2015.
- **Primary source:** [CVF paper page](https://openaccess.thecvf.com/content_cvpr_2015/html/Newcombe_DynamicFusion_Reconstruction_and_2015_CVPR_paper.html).
- **Supported claim:** one RGB-D camera can jointly fuse a canonical TSDF and
  estimate a dense volumetric 6-DoF warp to the live frame in real time without
  a pre-built object template.
- **Assumptions and objective:** calibrated depth, projective data association,
  a sufficiently good previous-frame initialization, spatially smooth
  as-rigid-as-possible deformation, and a mostly observable surface; minimize
  dense point-to-plane data error plus deformation-graph regularization and
  fuse warped depth in canonical space.
- **Reported evidence:** live reconstructions and tracking demonstrations;
  accuracy is primarily qualitative/system oriented rather than a modern NVS
  benchmark.
- **Failure boundary:** the paper explicitly reports difficulty with rapid
  closed-to-open topology change, large inter-frame motion, motion while
  occluded, insufficient geometric texture, tracking corruption, TSDF extent,
  and the growing cost/uncertainty of the warp field.
- **Executable reference:** no maintained official implementation is provided.
  A compact repo-owned RGB-D warp/fusion lab is the reproducible choice.
- **Lab relevance:** motivates a metric-depth baseline and the occlusion sweep:
  unobserved deformation must be predicted, not measured.
- **Credit caveat:** it generalized KinectFusion-style fusion to non-rigid
  scenes; canonical warps, embedded deformation, and TSDF fusion each predate
  the system.

### 4. Pumarola et al. — D-NeRF

- **Registry ID already present:** `pumarola-dnerf-2021`
- **Title / authors / venue:** *D-NeRF: Neural Radiance Fields for Dynamic
  Scenes*, Albert Pumarola, Enric Corona, Gerard Pons-Moll, Francesc
  Moreno-Noguer, CVPR 2021.
- **Primary source:** [CVF paper page](https://openaccess.thecvf.com/content/CVPR2021/html/Pumarola_D-NeRF_Neural_Radiance_Fields_for_Dynamic_Scenes_CVPR_2021_paper.html),
  [official repository](https://github.com/albertpumarola/D-NeRF).
- **Supported claim:** a time-conditioned deformation network can map a sample
  from observation time into a canonical NeRF and support novel view at an
  arbitrary observed/interpolated time from monocular moving-camera input.
- **Assumptions and objective:** known cameras, one canonical state, smooth
  deformation, static appearance model apart from the deformation; optimize
  volume-rendering photometric error and constrain the canonical time to have
  zero deformation.
- **Reported metrics:** PSNR/SSIM on the paper's synthetic dynamic benchmark,
  plus qualitative real-video results.
- **Failure boundary:** image metrics do not validate geometry or material
  tracks; the one-canonical-space model is weak for topology changes and
  content birth/death, and optimization is per scene.
- **Executable reference:** official PyTorch repository, historically useful
  but based on an older environment; pin it only after a smoke reproduction.
- **Lab relevance:** the minimal time-conditioned renderable baseline. Its
  output should be scored for NVS separately from 3D trajectory accuracy.
- **Credit caveat:** D-NeRF is one of several concurrent 2020/2021 dynamic-NeRF
  formulations and should not be described as the invention of dynamic neural
  rendering.

### 5. Park et al. — Nerfies

- **Registry ID already present:** `park-nerfies-2021`
- **Title / authors / venue:** *Nerfies: Deformable Neural Radiance Fields*,
  Keunhong Park, Utkarsh Sinha, Jonathan T. Barron, Sofien Bouaziz, Dan B.
  Goldman, Steven M. Seitz, Ricardo Martin-Brualla, ICCV 2021.
- **Primary source:** [CVF paper page](https://openaccess.thecvf.com/content/ICCV2021/html/Park_Nerfies_Deformable_Neural_Radiance_Fields_ICCV_2021_paper.html),
  [official repository](https://github.com/google/nerfies).
- **Supported claim:** a per-observation deformation code and continuous warp
  can map casual captures into a canonical 5D radiance field; coarse-to-fine
  optimization and elastic regularization improve robustness.
- **Assumptions and objective:** known or pre-estimated camera poses, a
  canonical template, smooth locally elastic deformation, and photometric
  supervision; optimize rendering loss with elastic, background, and
  coarse-to-fine regularization.
- **Reported metrics:** held-out synchronized-camera PSNR/SSIM and perceptual
  image metrics, with qualitative deformation/rendering evidence.
- **Failure boundary:** the observation-to-template optimization is
  underconstrained and prone to local minima; ordinary 3D canonical warps do
  not naturally represent topology change. Photorealism is not a material-track
  metric.
- **Executable reference:** official JAX code and Colab exist, but the GitHub
  repository was archived in April 2026 and is read-only; treat it as pinned
  historical code, not a maintained dependency.
- **Lab relevance:** supplies elastic-warp regularization and the canonical
  versus topology-change comparison.
- **Credit caveat:** “deformable NeRF” builds on much earlier canonical-space
  non-rigid reconstruction and geometry-processing regularizers.

### 6. Li et al. — Neural Scene Flow Fields

- **Proposed ID:** `li-nsff-2021`
- **Title / authors / venue:** *Neural Scene Flow Fields for Space-Time View
  Synthesis of Dynamic Scenes*, Zhengqi Li, Simon Niklaus, Noah Snavely,
  Oliver Wang, CVPR 2021.
- **Primary source:** [CVF paper](https://openaccess.thecvf.com/content/CVPR2021/papers/Li_Neural_Scene_Flow_Fields_for_Space-Time_View_Synthesis_of_Dynamic_CVPR_2021_paper.pdf),
  [official project](https://www.cs.cornell.edu/~zl548/NSFF/),
  [official repository](https://github.com/zhengqili/Neural-Scene-Flow-Fields).
- **Supported claim:** a per-scene time-varying field can jointly represent
  color, density, and forward/backward 3D scene flow for monocular space-time
  view synthesis; flow cycle, smoothness, optical-flow, depth, and
  disocclusion-aware terms constrain the ill-posed problem.
- **Assumptions and objective:** known or derivable cameras, adjacent temporal
  observations, pretrained depth/flow priors, predominantly smooth short-range
  motion; optimize rendering, temporal photometric consistency, flow cycle,
  geometric correspondence, and regularization losses.
- **Reported metrics:** PSNR, SSIM, and LPIPS on held-out space-time views; the
  representation exposes scene flow, but the headline benchmark remains image
  synthesis.
- **Failure boundary:** the paper reports inability to extrapolate unseen
  disocclusions, degraded detail under extreme/long motion, long per-scene
  optimization, and local minima when camera and object motion approach a
  degenerate configuration.
- **Executable reference:** official repository is available but historically
  pinned and expensive; use it as an optional full reference, not the smoke
  contract.
- **Lab relevance:** directly motivates the camera/object-motion degeneracy and
  disocclusion sweeps.
- **Credit caveat:** the neural field predicts a quantity introduced by the
  scene-flow literature; it adds differentiable volume rendering and learned
  priors.

### 7. Park et al. — HyperNeRF

- **Proposed ID:** `park-hypernerf-2021`
- **Title / authors / venue:** *HyperNeRF: A Higher-Dimensional Representation
  for Topologically Varying Neural Radiance Fields*, Keunhong Park, Utkarsh
  Sinha, Peter Hedman, Jonathan T. Barron, Sofien Bouaziz, Dan B. Goldman,
  Ricardo Martin-Brualla, Steven M. Seitz, ACM Transactions on Graphics 40(6),
  SIGGRAPH Asia 2021.
- **Primary source:** [official project and bibliographic record](https://hypernerf.github.io/),
  [official repository](https://github.com/google/hypernerf).
- **Supported claim:** lifting a canonical template into higher-dimensional
  ambient space permits slices whose 3D topology varies over time, addressing
  events that an ordinary continuous bijection in 3D cannot express.
- **Assumptions and objective:** known cameras, per-scene optimization,
  a learned deformation into hyperspace, and photometric supervision with
  geometric/elastic regularization.
- **Reported metrics:** held-out novel-view PSNR/SSIM/MS-SSIM/LPIPS and
  qualitative topology-changing sequences.
- **Failure boundary:** hyperspace removes one representational obstruction but
  does not uniquely identify material points or provide metric scene flow;
  geometry and motion remain weakly supervised by rendering.
- **Executable reference:** official JAX code exists; like Nerfies, use as a
  historical pinned reference after environment verification.
- **Lab relevance:** add one open/close or split/merge event to show where a
  single invertible canonical warp is mathematically insufficient.
- **Credit caveat:** the contribution is the higher-dimensional neural template,
  not the invention of level sets or topology-varying geometry.

### 8. Yang et al. — BANMo

- **Proposed ID:** `yang-banmo-2022`
- **Title / authors / venue:** *BANMo: Building Animatable 3D Neural Models
  From Many Casual Videos*, Gengshan Yang, Minh Vo, Natalia Neverova, Deva
  Ramanan, Andrea Vedaldi, Hanbyul Joo, CVPR 2022.
- **Primary source:** [CVF paper page](https://openaccess.thecvf.com/content/CVPR2022/html/Yang_BANMo_Building_Animatable_3D_Neural_Models_From_Many_Casual_Videos_CVPR_2022_paper.html),
  [official repository](https://github.com/facebookresearch/banmo).
- **Supported claim:** articulated canonical shape, neural blend skinning,
  canonical embeddings, root-body pose, and a radiance field can be optimized
  from multiple casual monocular videos without a registered template or
  supplied cameras; canonical embeddings support dense correspondences.
- **Assumptions and objective:** repeated videos of the same articulated
  subject, an object/background decomposition, a low-dimensional bone model,
  invertible skinning, and several learned 2D priors; optimize rendering,
  silhouette, optical-flow/feature correspondence, cycle, pose, and geometry
  terms.
- **Reported metrics:** novel-view image metrics, 3D shape error on synthetic
  data, camera/root-pose measures, and correspondence/flow evaluations.
- **Failure boundary:** articulated/bone and single-subject priors do not cover
  arbitrary fluids, topology changes, interactions, or unmodeled new objects;
  per-instance optimization is costly and initialization dependent.
- **Executable reference:** official code provides reproduction scripts and
  synthetic evaluation, but its documented examples require hours on multiple
  V100s. The repository points to Lab4D for newer software.
- **Lab relevance:** makes camera/root-body/local-articulation factorization
  explicit and informs separate object-pose versus deformation errors.
- **Credit caveat:** its articulated model intentionally combines classical
  blend skinning, canonical embeddings, and NeRF rather than replacing their
  histories.

### 9. Liu et al. — RoDynRF

- **Proposed ID:** `liu-rodynrf-2023`
- **Title / authors / venue:** *Robust Dynamic Radiance Fields*, Yu-Lun Liu,
  Chen Gao, Andreas Meuleman, Hung-Yu Tseng, Ayush Saraf, Changil Kim,
  Yung-Yu Chuang, Johannes Kopf, Jia-Bin Huang, CVPR 2023.
- **Primary source:** [CVF paper](https://openaccess.thecvf.com/content/CVPR2023/papers/Liu_Robust_Dynamic_Radiance_Fields_CVPR_2023_paper.pdf),
  [official project](https://robust-dynrf.github.io/),
  [official repository](https://github.com/facebookresearch/robust-dynrf).
- **Supported claim:** camera poses and focal length can be jointly optimized
  with separate static and dynamic radiance fields when conventional SfM fails
  on casual dynamic video.
- **Assumptions and objective:** one shared focal length, enough static or
  geometrically constrained content, flow and monocular-depth priors, and
  coarse-to-fine initialization; optimize static reconstruction/reprojection/
  disparity/depth losses, camera parameters, dynamic rendering, scene flow,
  and regularization.
- **Reported metrics:** camera translation/rotation errors on MPI Sintel and
  PSNR/SSIM/LPIPS or masked variants on dynamic NVS datasets.
- **Failure boundary:** the authors show fast camera motion breaking flow and
  therefore pose/geometry, and changing focal length violating the shared-
  intrinsic assumption. Joint optimization reduces but cannot remove the
  camera/object gauge ambiguity.
- **Executable reference:** official MIT-licensed implementation is available;
  it depends on RAFT and DPT preprocessing and remains a practical pinned full
  reference after asset/hash verification.
- **Lab relevance:** the closest optimized reference for the moving-camera plus
  moving-object cell and the pose-noise sweep.
- **Credit caveat:** joint scene/camera optimization existed for static neural
  fields; the contribution addresses robust dynamic decomposition.

### 10. Wang et al. — OmniMotion

- **Proposed ID:** `wang-omnimotion-2023`
- **Title / authors / venue:** *Tracking Everything Everywhere All at Once*,
  Qianqian Wang, Yen-Yu Chang, Ruojin Cai, Zhengqi Li, Bharath Hariharan,
  Aleksander Hołyński, Noah Snavely, ICCV 2023.
- **Primary source:** [CVF paper page](https://openaccess.thecvf.com/content/ICCV2023/html/Wang_Tracking_Everything_Everywhere_All_at_Once_ICCV_2023_paper.html),
  [official project](https://omnimotion.github.io/),
  [official repository](https://github.com/qianqianwang68/omnimotion).
- **Supported claim:** per-video optimization of bijections between local
  quasi-3D volumes and one canonical volume yields globally consistent dense
  pixel trajectories that can bridge occlusion and combine camera and object
  motion.
- **Assumptions and objective:** reliable pairwise correspondences, brightness
  evidence, an invertible mapping in the quasi-3D representation, and a video
  short enough for expensive test-time optimization; optimize flow-derived
  correspondence and photometric losses with hard-example sampling.
- **Reported metrics:** TAP-Vid position accuracy, Average Jaccard, Occlusion
  Accuracy, and a temporal-coherence measure. Its pseudo-depth is explicitly
  not physical metric depth.
- **Failure boundary:** rapid/highly non-rigid motion and thin structures can
  starve the optimizer of correct pairwise matches; initialization can yield
  wrong surface ordering or duplicated canonical objects; exhaustive flow
  preprocessing scales quadratically and optimization is slow.
- **Executable reference:** official PyTorch code and sample weights are
  available, but the documented environment is Python 3.8 / PyTorch 1.10,
  about 22 GB GPU memory, and 8–9 hours per video on an A100.
- **Lab relevance:** defines the post-occlusion tracking/visibility metrics and
  demonstrates why a canonical index can support identity even when a point is
  temporarily invisible.
- **Credit caveat:** this is a dense long-range 2D tracking representation with
  quasi-3D ordering, not a metric 4D surface reconstruction.

### 11. Luiten et al. — Dynamic 3D Gaussians

- **Registry ID already present:** `luiten-dynamic3dgs-2024`
- **Title / authors / venue:** *Dynamic 3D Gaussians: Tracking by Persistent
  Dynamic View Synthesis*, Jonathon Luiten, Georgios Kopanas, Bastian Leibe,
  Deva Ramanan, 3DV 2024.
- **Primary source:** [DOI
  10.1109/3DV62453.2024.00044](https://doi.org/10.1109/3DV62453.2024.00044),
  [official project](https://dynamic3dgaussians.github.io/),
  [official repository](https://github.com/JonathonLuiten/Dynamic3DGaussians).
- **Supported claim:** explicit Gaussians that move and rotate while retaining
  color, opacity, and size, together with local-rigidity/isometry/rotation
  priors, can support dynamic NVS and dense 6-DoF tracking with persistent
  primitive identities.
- **Assumptions and objective:** synchronized calibrated multi-camera video,
  foreground/background masks, full initial visibility for anything that will
  be tracked, and locally coherent motion; optimize photometric reconstruction
  plus rigidity, rotation, isometry, and segmentation losses, initialized
  sequentially from the preceding frame.
- **Reported metrics:** PSNR/SSIM/LPIPS for NVS and median 2D/3D trajectory
  error/track accuracy on PanopticSports and Particle-NeRF data.
- **Failure boundary:** the paper explicitly cannot reconstruct an object that
  first enters after the initial frame and does not work off-the-shelf on
  monocular video. Good NVS survives some ablations that visibly damage motion,
  demonstrating why rendering metrics alone are insufficient.
- **Executable reference:** official code includes NVS and tracking evaluation
  plus prepared data; this is the most direct historical persistent-primitive
  reference if its CUDA stack is pinned successfully.
- **Lab relevance:** compare a truly persistent primitive index against a
  time-conditioned renderer and sweep delayed object entry/occlusion.
- **Credit caveat:** persistent particles and splatting predate 3DGS; the work's
  contribution is the 3DGS analysis-by-synthesis formulation and regularized
  tracking contract.

### 12. Wu et al. — 4D Gaussian Splatting

- **Registry ID already present:** `wu-4dgs-2024`
- **Title / authors / venue:** *4D Gaussian Splatting for Real-Time Dynamic
  Scene Rendering*, Guanjun Wu, Taoran Yi, Jiemin Fang, Lingxi Xie, Xiaopeng
  Zhang, Wei Wei, Wenyu Liu, Qi Tian, Xinggang Wang, CVPR 2024.
- **Primary source:** [CVF paper page](https://openaccess.thecvf.com/content/CVPR2024/html/Wu_4D_Gaussian_Splatting_for_Real-Time_Dynamic_Scene_Rendering_CVPR_2024_paper.html),
  [official project](https://guanjunwu.github.io/4dgs/),
  [official repository](https://github.com/hustvl/4DGaussians).
- **Supported claim:** decomposed 4D neural voxels can encode time/space
  features from which a compact MLP predicts deformation of canonical 3D
  Gaussians, enabling high-resolution real-time dynamic rendering.
- **Assumptions and objective:** known cameras, a canonical Gaussian scaffold,
  a smooth learnable deformation over the sampled time domain, and per-scene
  optimization; optimize differentiable rendering with deformation and
  regularization terms.
- **Reported metrics:** PSNR/SSIM/LPIPS, training time, storage, and FPS on
  D-NeRF and real multi-view dynamic datasets.
- **Failure boundary:** the headline objective is NVS, not correspondence;
  predicted deformation of an indexed primitive is not by itself proof of
  material identity, topology handling, or re-identification. Monocular inputs
  retain depth and camera/object ambiguity.
- **Executable reference:** active official repository with dataset recipes;
  suitable as the renderable 4DGS full reference after dependency and dataset
  hashes are pinned.
- **Lab relevance:** contrasts compact deformation-driven rendering with the
  stronger persistent-track contract of Dynamic 3D Gaussians.
- **Credit caveat:** “4D Gaussian Splatting” is used by several independent
  2023/2024 papers for different spacetime parameterizations; always cite the
  exact formulation rather than treating the phrase as one method.

### 13. Feng et al. — St4RTrack

- **Proposed ID:** `feng-st4rtrack-2025`
- **Title / authors / venue:** *St4RTrack: Simultaneous 4D Reconstruction and
  Tracking in the World*, Haiwen Feng, Junyi Zhang, Qianqian Wang, Yufei Ye,
  Pengcheng Yu, Michael J. Black, Trevor Darrell, Angjoo Kanazawa, ICCV 2025.
- **Primary source:** [CVF paper](https://www.openaccess.thecvf.com/content/ICCV2025/papers/Feng_St4RTrack_Simultaneous_4D_Reconstruction_and_Tracking_in_the_World_ICCV_2025_paper.pdf),
  [official project](https://st4rtrack.github.io/),
  [official repository](https://github.com/HavenFeng/St4RTrack),
  [official model card](https://huggingface.co/yupengchengg147/St4RTrack).
- **Supported claim:** a feed-forward pair model can predict time-dependent
  pointmaps in one world frame, jointly reconstructing geometry and long-range
  3D tracks; world-frame tracking explicitly separates camera and scene motion.
- **Assumptions and objective:** learned priors from static and synthetic 4D
  data, pairwise processing against a reference frame, metric-depth/camera
  supervision where available, and optional per-video reprojection adaptation;
  optimize pointmap, confidence, 2D trajectory, monocular-depth, and
  reprojection/geometric-consistency terms.
- **Reported metrics:** TAPVid-3D-style Average Position in Distance, tracking
  EPE, and world-frame reconstruction APD/EPE, split for all versus dynamic
  points.
- **Failure boundary:** its project and paper state that pairwise/per-frame
  processing leaves scale misalignment, large camera moves, and occlusion
  unresolved; limited synthetic training diversity hurts complex out-of-domain
  motion and can require test-time adaptation.
- **Executable reference:** current official code, weights, and model card make
  this the preferred maintained learned reference, subject to a pinned offline
  checkpoint and license/hash audit.
- **Lab relevance:** directly matches the lab's world-frame camera/object
  separation and permits the same geometry/trajectory metrics on static-camera,
  moving-camera, and combined-motion inputs.
- **Credit caveat:** it adapts the pointmap/foundation-geometry lineage to time;
  it does not supersede explicit long-term tracking or optimized high-resolution
  renderers on every metric.

### 14. Wu et al. — StreamSplat

- **Proposed ID:** `wu-streamsplat-2026`
- **Title / authors / venue:** *StreamSplat: Towards Online Dynamic 3D
  Reconstruction from Uncalibrated Video Streams*, Zike Wu, Qi Yan, Xuanyu Yi,
  Lele Wang, Renjie Liao, ICLR 2026.
- **Primary source:** [ICLR proceedings](https://proceedings.iclr.cc/paper_files/paper/2026/hash/c822d05dcc00695ed6b63c9e97bb3449-Abstract-Conference.html),
  [official project](https://streamsplat3d.github.io/),
  [official repository](https://github.com/DSL-Lab/StreamSplat).
- **Supported claim:** a feed-forward online model can turn uncalibrated
  monocular video into dynamic 3D Gaussians using probabilistic position
  prediction, bidirectional two-frame deformation, and adaptive fusion that
  propagates persistent Gaussians while handling emerging/vanishing content.
- **Assumptions and objective:** learned monocular depth, an orthographic
  camera approximation, smooth motion between adjacent frames, and a two-frame
  temporal window; train RGB/LPIPS/depth/mask reconstruction objectives.
- **Reported metrics:** PSNR/SSIM/LPIPS for reconstruction, interpolation, and
  NVS, plus speed/memory and qualitative persistence. The paper explicitly
  describes the system as deterministic reconstruction rather than generation.
- **Failure boundary:** external pseudo-depth errors, lost history under fast
  motion or extended occlusion, and residual perspective distortion in
  close-range scenes. Qualitative stable Gaussians are not a full identity-
  switch or post-occlusion benchmark.
- **Executable reference:** current official code and checkpoint instructions
  exist, but training requires multi-GPU infrastructure; inference is a viable
  optional full-profile comparison after checkpoint locking.
- **Lab relevance:** the closest maintained online/camera-free reference and a
  useful stress test for long occlusion and perspective camera motion.
- **Credit caveat:** stochastic position prediction inside a deterministic
  reconstruction pipeline is not generative scene-hypothesis sampling.

### 15. Kwak et al. — MoRel

- **Proposed ID:** `kwak-morel-2026`
- **Title / authors / venue:** *MoRel: Long-Range Flicker-Free 4D Motion
  Modeling via Anchor Relay-based Bidirectional Blending with Hierarchical
  Densification*, Sangwoon Kwak, Weeyoung Kwon, Jun Young Jeong, Geonho Kim,
  Won-Sik Cheong, Jihyong Oh, CVPR 2026.
- **Primary source:** [CVF paper page](https://openaccess.thecvf.com/content/CVPR2026/html/Kwak_MoRel_Long-Range_Flicker-Free_4D_Motion_Modeling_via_Anchor_Relay-based_Bidirectioanl_CVPR_2026_paper.html),
  [official project](https://cmlab-korea.github.io/MoRel/),
  [official repository](https://github.com/CMLab-Korea/CVPR26-MoRel).
- **Supported claim:** a global canonical anchor, locally canonical key-frame
  anchors, bidirectional deformation windows, and learned opacity blending can
  extend 4DGS to long sequences with bounded memory and reduce chunk-boundary
  flicker, including appearing/disappearing occlusions.
- **Assumptions and objective:** posed multi-view video and initial geometry,
  temporally local smooth deformation around anchors, plus a global scaffold;
  optimize reconstruction/deformation/blending and feature-variance-guided
  densification.
- **Reported metrics:** PSNR/SSIM/LPIPS, temporal optical-flow discrepancy
  (`tOF`), training/rendering memory, storage, and runtime on a new long-range
  dataset and established dynamic datasets.
- **Failure boundary:** the paper reports that the global canonical anchor
  becomes less effective when spatial extent or spatial characteristics change
  substantially; reinitializing it can introduce a temporal discontinuity.
  `tOF` and flicker remain appearance/motion metrics, not persistent identity.
- **Executable reference:** official PyTorch code was released in April 2026;
  a practical recent full-profile candidate after license and asset locking.
- **Lab relevance:** motivates sweeping sequence and occlusion length rather
  than evaluating only short adjacent-frame motion.
- **Credit caveat:** local key-frame anchors trade one global canonical model
  for a sequence of overlapping local models; they do not remove the underlying
  observability problem.

### 16. Yugay et al. — GaME

- **Proposed ID:** `yugay-game-2026`
- **Title / authors / venue:** *Gaussian Mapping for Evolving Scenes*, Vladimir
  Yugay, Thies Kersten, Luca Carlone, Theo Gevers, Martin R. Oswald, Lukas
  Schmid, CVPR 2026.
- **Primary source:** [CVF paper page](https://openaccess.thecvf.com/content/CVPR2026/html/Yugay_Gaussian_Mapping_for_Evolving_Scenes_CVPR_2026_paper.html),
  [official project](https://vladimiryugay.github.io/game/),
  [official repository](https://github.com/VladimirYugay/GaME).
- **Supported claim:** an online 3D Gaussian map can be updated after structural
  changes that occur outside the current field of view by adding new geometry,
  removing stale geometry, and discarding outdated keyframe evidence while
  preserving useful observations.
- **Assumptions and objective:** posed RGB-D input, change detection from new
  observations, and an up-to-date-map objective rather than simultaneous
  trajectories for every past state; optimize Gaussian NVS/depth consistency
  with dynamic map and keyframe management.
- **Reported metrics:** PSNR, SSIM/LPIPS where applicable, L1 depth error,
  precision/recall-style change/map quality, runtime, and real/synthetic
  evolving-scene evidence; the abstract reports a 29.7% PSNR and 3× L1-depth
  improvement over its strongest baseline.
- **Failure boundary:** replacing stale state is not the same as preserving the
  identity and full trajectory of a moved object. Out-of-view change is known
  only after re-observation, and RGB-D/pose errors can corrupt add/remove
  decisions.
- **Executable reference:** current official code includes deterministic
  reproduction scripts, with a documented nondeterministic Gaussian rasterizer.
- **Lab relevance:** supplies a crucial endpoint: persistent mapping of the
  latest world differs from 4D history, post-occlusion identity, and generative
  hypotheses about changes while unobserved.
- **Credit caveat:** GaME studies long-term evolving maps, a different problem
  from short-term non-rigid motion capture and dynamic NVS.

## Cross-source findings for the lab

### Representation does not imply correspondence

D-NeRF, Nerfies, HyperNeRF, and 4D-GS can all render a function at time \(t\).
Only a stated correspondence construction and metric justify saying that an
indexed point at \(t_0\) is the same material point at \(t_1\). Dynamic 3D
Gaussians fixes primitive attributes and evaluates tracks; OmniMotion uses
local/canonical bijections and evaluates occlusion-aware tracks; St4RTrack
predicts world-frame time-dependent pointmaps. Those are three different
identity contracts.

### Camera/object disentanglement is a gauge choice plus evidence

Known cameras hide the hardest part of casual dynamic video. RoDynRF jointly
optimizes cameras and a static/dynamic split but still fails with fast motion
and changing intrinsics. BANMo separates root motion, articulation, and camera
using strong object and motion priors. St4RTrack predicts in a world frame from
learned priors. The proposed lab should therefore provide both an oracle-camera
condition and an unknown/noisy-camera condition; reporting only the oracle
condition would miss the module's central ambiguity.

### Occlusion is missing evidence, not ordinary interpolation

DynamicFusion predicts hidden deformation through its regularized warp and can
lose tracking irrecoverably. NSFF introduces disocclusion weights but cannot
invent unseen content reliably. OmniMotion can bridge occlusion when its global
canonical representation and pairwise matches establish the correct ordering,
yet can duplicate objects in a poor local minimum. Dynamic 3D Gaussians cannot
handle objects absent from the first frame. StreamSplat acknowledges lost
history under extended occlusion. A useful test must hide an identified surface,
then score its first reappearance, not just the frames before and after it.

### Topology change and object birth/death are different

HyperNeRF lifts a deforming template into higher dimensions to represent
topology change. Dynamic 3D Gaussians keeps a persistent initial set and cannot
model a newly entering object. StreamSplat and GaME add or retire Gaussians for
emergence/evolving maps. These operations solve different tasks: a topology
event changes connectivity, birth/death changes support, and occlusion changes
visibility without changing the underlying scene.

### Rendering metrics and motion metrics must remain separate

The lab report should contain at least four panels, never one aggregate rank:

| Contract | Minimum metrics | What it catches |
|---|---|---|
| Held-out dynamic rendering | PSNR, SSIM, LPIPS on a fixed view/time mask | Appearance and view synthesis. |
| Geometry | visible/dynamic-point EPE, APD at fixed metric thresholds, depth error | Metric or aligned surface quality. |
| Motion and camera | 3D trajectory EPE, camera ATE/rotation error, scene-flow EPE | Camera/object separation and world motion. |
| Visibility and identity | Occlusion Accuracy, Average Jaccard, reappearance error, identity switches | Persistence through missing observations. |
| Temporal appearance | flow-warp error or tOF, flicker statistic | Short-range rendering continuity, but not identity. |

## Repo-owned controlled concept lab

### Scene and ground truth

The landed analytic fixture uses two indistinguishable object centers with
stable hidden IDs. They approach, reverse while fully occluded, and reappear.
A constant-velocity tracker has an equally plausible pass-through explanation:
its unordered point set lies near the reappearing detections while its two
persistent identities are switched. This isolates identity observability
without claiming photorealism, topology change, or a learned-model benchmark.

The same event is evaluated in three matched conditions:

1. **static camera, moving objects**;
2. **moving camera, moving objects, oracle world-frame camera center**; and
3. **moving camera, moving objects, contaminated factorization**, where 35% of
   one object's displacement leaks into the estimated world-frame camera center.

Camera-relative measurements remain consistent in all three conditions. The
second condition demonstrates that camera motion is not intrinsically an error
source when it is observed; the third exposes the camera/object gauge when
dynamic support contaminates egomotion. The controlled sweep increases the
fully hidden duration. Camera-pose noise, texture, deformation speed, topology,
and birth/death are useful future extensions, not measurements claimed by this
fixture.

### Repo-owned concept baselines

The lab does not train or render. Exact world cameras and object trajectories
generate camera-relative centers. Oracle compensation reconstructs visible
world motion in the first two conditions. The contaminated condition adds the
declared camera-motion leakage. A constant-velocity prior forecasts the first
post-occlusion frame, and an unordered two-object assignment is evaluated both
with and without persistent identity labels. This yields a transparent
counterexample where set geometry is nearly correct while correspondence is
wrong.

### Expected artifacts

- `dynamic_trajectories.svg`: true identity trajectories, hidden interval, and
  post-occlusion predictions for all three conditions;
- `temporal_drift.svg`: identity-aware joint-motion error versus hidden
  duration;
- `dynamic_sequence.npz`: exact/estimated cameras, camera-relative evidence,
  truth identities, visibility, predictions, detections, and assignments;
- `dynamic_comparison.json`: array shapes, dtypes, semantics, condition
  contract, and recomputed summaries;
- `failure_sweep.csv`: occlusion duration under each motion/factorization
  condition;
- `result.json` and `report.md`: geometry, motion, visibility, identity,
  runtime, memory, input/config/artifact hashes, empty unsupported rendering
  and generative families, and an explicit inference type.

The landed CSV contains occlusion duration, identity-aware reappearance RMSE,
set-aligned RMSE, and identity accuracy for every condition; it does not claim
the other candidate sweeps. Every reported scalar is recomputable from
`dynamic_sequence.npz`. Validation binds the archive to the profile, checks
array semantics and internal observation/assignment consistency, recomputes
metrics, and independently regenerates both result and CSV sweep rows.

### Maintained full reference

Prefer a pinned **St4RTrack** inference path for the learned world-frame
reconstruction/tracking comparison because its current official repository,
weights, pointmap output, and APD/EPE metrics line up with this lab. Keep
**StreamSplat** as an optional online Gaussian comparison and **4D-GS** as the
optimized renderable reference. Historical D-NeRF/Nerfies/OmniMotion code is
valuable for reading and occasional reproduction but should not be called
maintained in 2026 without a successful pinned build.

Reference execution must remain offline after an explicit hash-verified fetch.
Missing weights, camera conventions, or licenses should fail before inference.

## Reconstruction versus dynamic generation

All recommended core references estimate one scene or one motion explanation
from observed video, even when a model internally samples a Gaussian position
or uses random initialization. They target reconstruction, NVS, or tracking:

\[
\widehat S_{0:T}=f(O_{0:T})
\quad\text{or}\quad
\widehat S_{0:T}=\arg\min_S \mathcal L(S;O_{0:T}).
\]

Generative future or scene-hypothesis sampling instead needs a conditional
distribution such as

\[
S_{0:T_{obs}}\sim p(S\mid O),\qquad
S_{T_{obs}+1:T}\sim p(S_{future}\mid S_{0:T_{obs}},O),
\]

with one persistent sampled scene identity reused by all time/view/point
queries. Neither smooth time interpolation nor stochastic internal features
establish this. Evidence consistency, alternative-hypothesis diversity,
within-sample temporal coherence, and cross-query persistence would all need
separate tests. Module 14 should teach the representation and observability
requirements needed before Module 15 returns to Surflo's persistent scene-state
frontier; it should not relabel dynamic reconstruction as generation.

## Recommended registry IDs and reading sequence

### Core sequence

1. `vedula-scene-flow-1999` — define the 3D motion quantity.
2. `newcombe-dynamicfusion-2015` — metric range fusion and hidden-motion limits.
3. `pumarola-dnerf-2021` — time-conditioned canonical neural rendering.
4. `park-nerfies-2021` — regularized deformation into canonical space.
5. `li-nsff-2021` — explicit neural scene flow and disocclusion ambiguity.
6. `wang-omnimotion-2023` — long-range correspondence and occlusion metrics.
7. `luiten-dynamic3dgs-2024` — persistent renderable primitive identities.
8. `wu-4dgs-2024` — compact deformation-driven Gaussian rendering.
9. `liu-rodynrf-2023` — camera/scene joint optimization.
10. `feng-st4rtrack-2025` — feed-forward world-frame geometry plus tracking.
11. `wu-streamsplat-2026` — online uncalibrated dynamic Gaussian reconstruction.
12. `kwak-morel-2026` — long-range sequence and occlusion scaling.

### Context sequence

- `bregler-nrsfm-2000` — low-rank non-rigid observability history.
- `park-hypernerf-2021` — topology-changing representation.
- `yang-banmo-2022` — root/camera/articulation factorization.
- `yugay-game-2026` — evolving latest-state maps versus full 4D history.

## Concise implementation and terminology checklist

- [ ] State whether cameras are known, optimized, or predicted.
- [ ] Fix and document world/camera transforms, handedness, units, time stamps,
      gauge alignment, and visibility semantics.
- [ ] Preserve exact ground-truth material/object IDs across every variant.
- [ ] Evaluate static-camera, moving-camera, and joint camera/object motion.
- [ ] Include a near-degenerate motion pair with similar 2D evidence.
- [ ] Sweep occlusion duration and score first-frame reappearance/ID switches.
- [ ] Keep topology change, object birth/death, and visibility change distinct.
- [ ] Separate NVS, geometry, motion/camera, visibility/identity, and temporal
      appearance metrics.
- [ ] Never infer correspondence from time conditioning or high PSNR.
- [ ] Never call pseudo-depth metric geometry without an explicit alignment and
      scale contract.
- [ ] Never call deterministic dynamic reconstruction generative future or
      scene-hypothesis sampling.
- [ ] Pin maintained reference code, weights, assets, coordinate adapters, and
      hashes; run offline after fetch.
- [ ] Persist arrays needed to recompute all metrics and validate tampering.
- [ ] Report runtime and peak CPU/GPU memory separately from accuracy.
- [ ] State whether identities persist across later calls, resolutions, cameras,
      occlusions, and time—not merely within one render invocation.
