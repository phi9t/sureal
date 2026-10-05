# From Classical Reconstruction to Generative Scenes

Historical cutoff: **September 25, 2026**. This is a reproduction-oriented
pathway for computer-vision and machine-learning researchers. It follows three
braided traditions: geometric measurement (evidence to cameras, depth, and
surfaces), renderable representations (image-based rendering to neural fields
and Gaussian primitives), and learned priors (depth/completion models to
generative scene hypotheses). It is canonical rather than exhaustive.

The scope is passive RGB, photometric and silhouette cues, active range,
RGB-D/LiDAR registration, visual and RGB-D SLAM, learned reconstruction,
neural rendering, and generative 3D. Medical tomography, microscopy,
geophysical imaging, and specialized industrial metrology are outside scope.
The cutoff matters: later systems should be added as a new, dated revision,
not silently projected backward into this history.

## How to use this pathway

Every module asks the same seven questions:

1. What evidence enters the problem?
2. What is observable, under which assumptions and gauge freedoms?
3. What representation is recovered?
4. Is inference analytic, optimized per scene, amortized across data, sampled,
   or a hybrid?
5. Which objective and metrics define success?
6. What happens outside observed support?
7. Which controlled intervention exposes the characteristic failure?

Keep task claims separate. Novel-view synthesis evaluates images from held-out
cameras; surface reconstruction evaluates 3D geometry. Completion predicts
unobserved content; posterior sampling requires a distribution whose samples
are coherent conditional alternatives. The term point stochasticity means randomness in
individual decoded points; scene stochasticity is randomness in a shared state
that persists across points, cameras, and time. No single scalar ranks all of
these tasks.

The machine-readable counterpart is
[`curriculum.json`](../parallax/curriculum.json). The shared scene
uses metres, a right-handed world frame, and OpenCV cameras
(x right, y down, z forward). All smoke labs are deterministic and offline;
`build` and `fetch` are the only network-capable dispatches. Each run records
input/config/artifact hashes, runtime, peak memory, a controlled sweep, and a
short interpretation. Full modules additionally bind the hash-verified
Blender/Cycles `phase-a-v1` episode: 16 shared context views, eight targets per
hidden-scene hypothesis, exact OpenCV cameras, metric depth and ray distance,
normals, IDs, albedo, sampled geometry, and visibility. Deterministic RGB-D,
time-of-flight, and sparse-LiDAR response summaries are derived from those
rendered buffers. Full `all` also executes every adapter marked `landed` in
`reference-adapters.json`; smoke remains the compact CI contract.

```bash
parallax/run.sh list
parallax/run.sh all --profile smoke --run-id pathway-smoke
parallax/run.sh report --run-id pathway-smoke
python3 parallax/pipeline/audit.py --offline
```

## 1. Image formation and observability

### Evidence and observability

The evidence is a set of image measurements, ideally calibrated pixel
correspondences. A pinhole camera maps a world point to a ray, not a unique 3D
point. One calibrated image therefore determines direction but not range. Two
non-coincident cameras add an epipolar constraint; their rays can be
triangulated when the baseline and correspondence are informative. With
unknown calibration, reconstruction is initially projective. With calibrated
monocular views, global scale remains unobservable. Even a metric multi-view
solution has a coordinate gauge unless a world frame is fixed.

### Representation and inference

The recovered representation is a set of intrinsics (K_i), world-to-camera
poses ((R_i,t_i)), and sparse points (X_j). Projection and ideal
triangulation are analytic; calibration and noisy triangulation are estimated.
The camera center is (C=-R^\top t). Changing every camera and point by the
same admissible gauge leaves image evidence unchanged.

### Defining mathematics

For homogeneous image coordinates,

\[
\tilde{x} \sim K [R\mid t]\tilde{X}, \qquad
\tilde{x}_2^\top F\tilde{x}_1=0, \qquad
F=K_2^{-\top}[t_{21}]_\times R_{21}K_1^{-1}.
\]

Depth sensitivity is inversely proportional to disparity. In rectified stereo,
(Z=fB/d), so (\partial Z/\partial d=-fB/d^2): small baseline (B), large
depth (Z), or uncertain disparity makes triangulation ill-conditioned.

### Assumptions and failure modes

The pinhole model assumes a calibrated or calibratable camera and distortion
handling. Epipolar geometry assumes a rigid scene and synchronized views.
Degenerate motion, nearly parallel rays, calibration error, and incorrect
matches can all yield precise-looking but wrong 3D. Reprojection alone cannot
choose a gauge or validate unobserved geometry.

### Primary-source reading sequence

Start with calibrated two-view recovery in
[longuet-higgins-1981](https://doi.org/10.1038/293133a0), then study optimal
image-space correction in
[hartley-sturm-1997](https://doi.org/10.1006/cviu.1997.0547), and finish with
practical planar calibration in
[zhang-2000](https://doi.org/10.1109/34.888718).

### Reproduction lab

```bash
parallax/run.sh run --module 01 --profile smoke --run-id pathway-01
```

Inspect `result.json`, `report.md`, `artifacts/triangulation.svg`, and
`artifacts/failure_sweep.csv`. The sweep holds pixel noise fixed while changing
baseline; the numerical tests also cover projection round trips, camera-center
recovery, epipolar residual, triangulation, and OpenCV/OpenGL conversion.

### Transition

Camera geometry tells us which 3D explanations are compatible with image
coordinates. It does not say where correspondences, normals, or silhouettes
come from. Shape-from-X methods add a cue model.

## 2. Shape-from-X

### Evidence and observability

Stereo and motion use repeated texture; shading uses intensity variation;
photometric stereo uses images under changing illumination; silhouettes use
foreground boundaries. Each cue changes the observable. Stereo estimates
visible depth where correspondence is identifiable. Photometric stereo
estimates local normals under lighting and reflectance assumptions. Silhouettes
constrain the intersection of generalized cones: the visual hull. A concavity
that never affects a silhouette is not observable from silhouettes alone.

### Representation and inference

Outputs include disparity/depth maps, surface normals, motion/structure, or a
volumetric visual hull. Classical inference is analytic or variational, usually
with regularization where a cue is weak. These are not interchangeable
representations: an integrable normal field is not automatically a metrically
located surface, and a visual hull is an outer bound rather than the object.

### Defining mathematics

Lambertian photometric stereo writes (I_k(x)=\rho(x)l_k^\top n(x)). Stacking
known lights gives (i=L(\rho n)), solved locally when (L) has sufficient
rank. A silhouette cone for view (i) is (C_i); the visual hull is

\[
V=\bigcap_i C_i.
\]

Stereo commonly minimizes a data term plus regularity,
(E(d)=\sum_x \rho(I_1(x)-I_2(x-d(x)))+\lambda R(d)).

### Assumptions and failure modes

Repeated or textureless areas break matching. Specularity, cast shadows,
interreflections, and unknown illumination break simple shading models.
Visual hulls miss concavities. Shape from motion inherits rigidity and camera
degeneracies. The same smoothness prior that fills weak evidence can erase thin
or discontinuous geometry.

### Primary-source reading sequence

Read the correspondence formulation in
[marr-poggio-1979](https://doi.org/10.1098/rspb.1979.0029), the foundational
single-view shading analysis in
[horn-1970](https://dspace.mit.edu/handle/1721.1/6883), calibrated lighting in
[woodham-1980](https://doi.org/10.1117/12.7972479), and the precise silhouette
limit in [laurentini-1994](https://doi.org/10.1109/34.273735).

### Reproduction lab

```bash
parallax/run.sh run --module 02 --profile smoke --run-id pathway-02
```

Inspect `result.json`, `report.md`, `artifacts/cue_failure.svg`, and
`artifacts/failure_sweep.csv`. Texture contrast is swept while the analytic
concavity remains invisible to the silhouette cue.

### Transition

Shape-from-X infers geometry through scene assumptions. Active sensors instead
inject energy or directly time returns, exchanging correspondence ambiguity for
calibrated sensor uncertainty and missing-data mechanisms.

## 3. Active range acquisition

### Evidence and observability

Structured light observes a projected code with a calibrated projector-camera
baseline. Time-of-flight estimates delay or phase. RGB-D cameras package depth
with imagery. LiDAR samples returns along emitted rays. These devices measure
range at sampled directions, but do not observe opaque surfaces behind the
first return. Reflectance, incidence angle, ambient illumination, range,
multipath, and interference affect whether a return exists and how biased it
is.

### Representation and inference

The immediate representations are depth images or range points with a sensor
origin and uncertainty. Conversion to a point cloud is analytic after
calibration. A persistent surface still requires registration and fusion.
Recorded sensor sequences are valid executable substitutes for hardware, but
their noise and missingness must be preserved rather than replaced by clean
ground truth.

### Defining mathematics

For phase-modulated time of flight, an idealized range is
(r=c\phi/(4\pi f_m)), modulo the unambiguous range. Depth-camera points use

\[
X_c=ZK^{-1}\tilde{x}.
\]

A useful heteroscedastic model is (Z_{meas}=Z+\epsilon(Z,\theta,\rho)), with
variance increasing with range and adverse incidence or reflectance.

### Assumptions and failure modes

Structured light needs decodable projected patterns. ToF can mix multiple path
lengths into one phase. RGB-D edges show flying pixels; reflective, transparent,
dark, and distant regions can be absent. LiDAR is sparse, asynchronous relative
to cameras, and subject to rolling acquisition. Missing depth is structured,
not independent random dropout.

### Primary-source reading sequence

Use [salvi-2010](https://doi.org/10.1016/j.patcog.2010.03.004) for structured
light, [hansard-2012](https://doi.org/10.1007/978-1-4471-4658-2) for ToF
principles, [khoshelham-2012](https://doi.org/10.3390/s120201437) for Kinect
uncertainty, and [geiger-2012](https://doi.org/10.1109/CVPR.2012.6248074) for a
calibrated camera/LiDAR benchmark setting.

### Reproduction lab

```bash
parallax/run.sh run --module 03 --profile smoke --run-id pathway-03
```

Inspect `result.json`, `report.md`, `artifacts/sensor_uncertainty.svg`, and
`artifacts/failure_sweep.csv`. Range is swept under a quadratic uncertainty
model; the result separately records bias, variance, and missing rate.

### Transition

A range frame is local and partial. Registration estimates how frames relate;
fusion decides how repeated noisy measurements become one surface.

## 4. Registration and range fusion

### Evidence and observability

The evidence is overlapping oriented or unoriented range samples, often with
initial pose estimates. Sufficient non-symmetric overlap constrains relative
rigid motion. It does not constrain alignment where geometry is repetitive,
planar in the wrong directions, or disjoint. Fusion improves supported regions
but does not turn missing support into a measurement.

### Representation and inference

ICP alternates correspondences and a rigid update. A TSDF stores truncated
signed distance and accumulated weight on a grid; marching cubes extracts its
zero level set. Poisson reconstruction instead integrates oriented samples into
a global indicator function. ICP and global surface reconstruction are
optimized per scene; TSDF updates are incremental weighted estimates.

### Defining mathematics

Point-to-plane ICP minimizes

\[
\min_{R,t}\sum_i \rho\!\left(n_i^\top(Rp_i+t-q_i)\right).
\]

For TSDF observations (d_k) with weights (w_k),
(D=\sum_k w_kd_k/\sum_k w_k). Marching cubes approximates
(\{x:D(x)=0\}). Poisson reconstruction solves a global problem of the form
(\min_\chi\|\nabla\chi-V\|^2) from an oriented vector field (V).

### Assumptions and failure modes

ICP is local: initialization, overlap, outliers, normals, and symmetry control
the basin. TSDF truncation and voxel size trade smoothing against detail;
pose errors blur rather than average away. Marching cubes discretizes topology.
Poisson methods can close holes globally and thereby create unsupported
surface. Report accuracy and completeness separately.

### Primary-source reading sequence

Read ICP in [besl-mckay-1992](https://doi.org/10.1109/34.121791), volumetric
fusion in [curless-levoy-1996](https://doi.org/10.1145/237170.237269), extraction
in [lorensen-cline-1987](https://doi.org/10.1145/37401.37422), and oriented-point
reconstruction in [kazhdan-2006](https://doi.org/10.2312/SGP/SGP06/061-070).

### Reproduction lab

```bash
parallax/run.sh run --module 04 --profile smoke --run-id pathway-04
```

Inspect `result.json`, `report.md`, `artifacts/icp_convergence.svg`, and
`artifacts/failure_sweep.csv`. The numerical contract checks rigid SVD recovery,
ICP convergence, TSDF averaging, and unit normals; the sweep increases range
noise.

### Transition

Range pipelines begin with 3D samples. Structure from motion has to recover
both the cameras and sparse structure from images before dense fusion is
possible.

## 5. Structure from motion and bundle adjustment

### Evidence and observability

SfM consumes overlapping images. Local features propose correspondences;
geometric verification rejects many outliers; relative poses and triangulated
tracks form an image graph. The reconstruction is observable only in connected,
nondegenerate components. A monocular reconstruction has a global similarity
gauge. Repeated texture can create a self-consistent but false component.

### Representation and inference

The representation is a sparse model: calibrated cameras, tracks, 3D points,
and a covisibility graph. Inference is hybrid. Feature detection and matching
are amortized or algorithmic; minimal pose solvers are analytic; RANSAC samples
hypotheses; incremental registration and triangulation initialize; bundle
adjustment jointly optimizes the scene.

### Defining mathematics

Bundle adjustment minimizes robust reprojection error,

\[
\min_{\{\theta_i\},\{X_j\}}\sum_{(i,j)\in\mathcal O}
\rho\!\left(\|x_{ij}-\pi(\theta_i,X_j)\|_2^2\right).
\]

Gauge must be fixed or handled in the linear system. RANSAC success after (N)
draws with inlier rate (w) and sample size (s) is
(1-(1-w^s)^N), showing why outlier rate matters sharply.

### Assumptions and failure modes

SfM assumes a mostly rigid scene, sufficient texture and overlap, a useful
camera motion, and matchable appearance. Low parallax weakens depth. Repetition
creates false tracks. Rolling shutter and moving objects violate the camera
model. Bundle adjustment refines the basin it receives; it is not a substitute
for correct data association.

### Primary-source reading sequence

Read robust sampling in
[fischler-bolles-1981](https://doi.org/10.1145/358669.358692), invariant local
features in [lowe-2004](https://doi.org/10.1023/B:VISI.0000029664.99615.94), the
modern synthesis in [triggs-2000](https://doi.org/10.1007/3-540-44480-7_21),
and the maintained pipeline design in
[schonberger-frahm-2016](https://openaccess.thecvf.com/content_cvpr_2016/html/Schonberger_Structure-From-Motion_Revisited_CVPR_2016_paper.html).
Historical-credit guardrail: bundle adjustment existed in photogrammetry before
the 2000 synthesis; that chapter organizes the method rather than inventing it.

### Reproduction lab

```bash
parallax/run.sh run --module 05 --profile smoke --run-id pathway-05
parallax/run.sh reference --adapter colmap-sfm --profile smoke --run-id pathway-05-colmap
```

Inspect `result.json`, `report.md`, `artifacts/bundle_adjustment.svg`, and
`artifacts/failure_sweep.csv`. The lab refines a noisy point observed by three
cameras and sweeps overlap. The separate maintained reference renders the
shared contract's explicit multi-depth plane-mosaic fixture: five calibrated
views for smoke and nine for full. It runs the exact Ubuntu package
`colmap=3.9.1-2build2` offline in the classical Insula, using the immutable
container image ID resolved before execution. Its smoke acceptance contract
requires at least four registered images, 1,000 sparse points, and mean
reprojection error no greater than 1.5 px; the locked September 26, 2026 smoke
observation registered all five views with 3,794 points and 1.088 px mean
error. Inspect its SQLite database, binary and text sparse models, `sparse.ply`,
execution log, package/Insula manifests, hashes, and recorded image ID.

### Transition

Sparse SfM supplies cameras and reliable tracks. Dense MVS asks which surface
explains photometric agreement at nearly every visible pixel.

## 6. Dense multi-view stereo and meshing

### Evidence and observability

Dense MVS takes calibrated overlapping images and seeks visible surfaces that
are consistent across selected source views. Visibility is part of the
problem: an occluded point should not be penalized against the occluding image.
Even ideal MVS observes only surfaces seen with usable texture and baseline.
Topology is inferred later by fusing depths or points and extracting a mesh.

### Representation and inference

Representations include per-view cost volumes, depth/normal maps, filtered
points, fused signed-distance fields, and meshes. Classical inference is
per-scene optimization or cost aggregation. Learned MVS (Module 8) amortizes
matching priors but retains the same evidence boundary.

### Defining mathematics

A generic depth objective is

\[
E(D)=\sum_{p}\sum_{j\in V(p,D)} C\big(I_r(p),I_j(w_j(p,D_p))\big)
+\lambda R(D),
\]

where (V) is a visibility/view-selection set and (w_j) warps a reference
pixel into view (j). Evaluation should report distance from reconstruction to
ground truth (accuracy) and from ground truth to reconstruction (completeness),
plus a thresholded F-score.

### Assumptions and failure modes

Brightness constancy fails with exposure changes, non-Lambertian material, and
lighting motion. Textureless areas flatten the cost curve. Thin structures and
occlusion boundaries are easily filtered. Increasing views helps coverage only
when those views reveal and match the surface; hidden geometry remains hidden.
Meshing can bridge unsupported gaps.

### Primary-source reading sequence

Use [seitz-2006](https://doi.org/10.1109/CVPR.2006.19) for definitions and
evaluation, [furukawa-ponce-2010](https://doi.org/10.1109/TPAMI.2009.161) for
patch-based dense reconstruction, and
[schonberger-2017](https://doi.org/10.1007/978-3-319-46487-9_31) for pixelwise
view selection in unstructured image collections.

### Reproduction lab

```bash
parallax/run.sh run --module 06 --profile smoke --run-id pathway-06
parallax/run.sh reference --adapter colmap-mvs --profile smoke --run-id colmap-mvs-06
```

Inspect `result.json`, `report.md`, `artifacts/mvs_views.svg`, and
`artifacts/failure_sweep.csv`. View count and exposure shift are separate
sweeps; accuracy, completeness, and hidden-surface recall remain distinct.

The maintained reference is a separate, offline COLMAP 4.2.0 execution pinned
to source commit `be5e29168d4aff238409d60424812df66aac919f`. Its CUDA 12.9.1
Insula is built explicitly for the available B200. This version boundary is
material: upstream fixed empty PatchMatch outputs on `sm_100+` in
[colmap-4.0.3-release](https://github.com/colmap/colmap/releases/tag/4.0.3),
and 4.2.0 retains that workaround. The pinned
[colmap-install-2026](https://github.com/colmap/colmap/blob/be5e29168d4aff238409d60424812df66aac919f/doc/install.rst) also notes that
distribution packages do not provide CUDA support, so the dense reference is
source-built rather than silently falling back to a CPU/package variant.

The controlled fixture uses unique appearance for every depth tile to avoid
turning repeated texture into an accidental pose ambiguity. Smoke uses five
views and full uses nine. The adapter runs SIFT SfM, image undistortion,
geometric-consistency PatchMatch, stereo fusion, and Poisson meshing. It emits
the SQLite feature database, binary and text sparse models, photometric and
geometric depth/normal maps, fused oriented points, a mesh, logs, manifests,
and a hash-bound report. Execution is `--network none`; the immutable image ID
and exact source commit are checked before atomic promotion.
Base-image digests, the Dockerfile hash, and the per-run image ID are recorded,
but Ubuntu dependencies are resolved during the explicit build. The result is
version-attested rather than a claim of bit-reproducible OCI output; the
reported B200 environment is descriptive baseline metadata, not a rebuild
identity gate.

The full profile also consumes all 16 supplied calibrated views from the
official Middlebury `TempleSparseRing` archive. Fetch locks the archive bytes
and the extracted 19-file tree; execution imports its provided pinhole cameras,
runs the same offline dense pipeline, and requires nontrivial fused-point and
mesh support. Middlebury does not distribute the corresponding laser ground
truth in that archive, so this canonical check reports input consumption and
structural support only. It is deliberately not presented as an accuracy or
completeness benchmark.

Let (S) be the similarity estimated from recovered camera centers and
orientations to the declared metric cameras, (P) the fused points, and (G) the
repo-owned union of per-view visible-surface samples. Both aligned clouds are
deduplicated on a 1 cm voxel grid, then sampled without replacement to at most
8,192 voxels using seed 260925. This makes the score invariant to PLY row order
and prevents repeated observations from weighting a surface multiple times.
On the resulting spatial samples (\bar P,\bar G), the reference reports

\[
\operatorname{accuracy}=\frac{1}{|\bar P|}\sum_{p\in \bar P}\min_{g\in \bar G}\|p-g\|_2,
\qquad
\operatorname{completeness}=\frac{1}{|\bar G|}\sum_{g\in \bar G}\min_{p\in \bar P}\|g-p\|_2.
\]

Precision and recall threshold those two directed distances at 10 cm, and their
harmonic mean is reported as F-score. These quantities are not collapsed with
novel-view rendering metrics. The visible-surface contract includes deeper and
background pixels that are visible in an input but may lack sufficient
multi-view support; their miss remains in completeness. The report separately
summarizes truth voxels receiving at least two sampled observations and those
below that threshold, and claims a support failure only when that split explains
the directed-error gap.
Counts revalidate exactly. Floating metrics revalidate at 1e-9 relative and
1e-12 absolute tolerance, and the hashed run configuration records the NumPy
version used for evaluation.

The verified B200 smoke baseline registers 5/5 views and produces 41,749 fused
points and 257,274 unique non-degenerate mesh faces, with 0.034 m accuracy, 0.827 m completeness,
and 0.387 F-score at 10 cm. Full registers 9/9 views and produces 105,548
points and 628,823 such faces, with 0.046 m accuracy, 0.625 m completeness, and
0.643 F-score. The tracked baselines live in `reference-adapters.json`; the
large directed-error gap is retained as failure evidence rather than averaged
away. COLMAP's GPU stages vary slightly, so acceptance is threshold-based
rather than exact-output based. Smoke uses a
deliberately loose 1 m completeness ceiling while
still requiring supported-surface accuracy and a minimum 10 cm F-score; a
five-view run is not rejected merely for exposing the intended support failure.

### Transition

Offline SfM/MVS can revisit all images. SLAM must decide online what to retain,
how to limit drift, and whether the world remains stable enough for one map.

## 7. Online SLAM and persistent mapping

### Evidence and observability

Visual SLAM receives an ordered image stream; RGB-D SLAM adds range; visual-
inertial systems add accelerations and angular rates. Short-term motion is
locally observable under texture, parallax, and sensor excitation. Long-term
consistency depends on loop closure and relocalization. Monocular scale is
unobservable without an additional metric cue. Dynamic objects confound camera
motion with scene motion.

### Representation and inference

The persistent representation combines a live state estimate with keyframes,
landmarks or dense geometry, covisibility, and a pose graph. Tracking is
incremental; local BA or dense alignment optimizes a window; loop closure adds
nonlocal constraints; pose-graph optimization redistributes drift. A map is a
maintained state, not merely a batch reconstruction.

### Defining mathematics

Absolute trajectory error aligns estimated poses (\hat T_i) to ground truth
and measures (\operatorname{trans}(T_i^{-1}S\hat T_i)). Relative pose error
measures local drift over a fixed interval. A pose graph minimizes

\[
\sum_{(i,j)}\|\log(Z_{ij}^{-1}T_i^{-1}T_j)\|_{\Omega_{ij}}^2.
\]

Dense RGB-D tracking often minimizes photometric and point-to-plane residuals.

### Assumptions and failure modes

Tracking fails under blur, low texture, pure rotation for depth initialization,
or missing range. Perceptual aliasing causes false loops; missed loops leave
drift. The static-world assumption breaks when moving objects dominate.
Relocalization tests map persistence after loss, not just frame-to-frame
accuracy.

### Primary-source reading sequence

Read dense RGB-D tracking/fusion in
[newcombe-2011](https://doi.org/10.1109/ISMAR.2011.6092378), keyframe feature
SLAM in [mur-artal-2015](https://doi.org/10.1109/TRO.2015.2463671), its
visual-inertial/multimap continuation in
[campos-2021](https://doi.org/10.1109/TRO.2021.3075644), and trajectory
evaluation in [sturm-2012](https://doi.org/10.1109/IROS.2012.6385773).

### Reproduction lab

The repo-owned concept lab remains the fast numerical exercise:

```bash
parallax/run.sh run --module 07 --profile smoke --run-id pathway-07
```

Inspect `result.json`, `report.md`, `artifacts/slam_drift.svg`, and
`artifacts/failure_sweep.csv`. The controlled loop redistributes synthetic
drift; the failure sweep increases dynamic-pixel fraction.

The maintained-system reproduction uses the official TUM
`freiburg1_xyz` RGB-D sequence and the canonical ORB-SLAM3 upstream at source
commit `4452a3c4ab75b1cde34e5505a36ec3f9edcdc4c4`:

```bash
parallax/run.sh fetch --asset tum-rgbd       # network allowed
parallax/run.sh build                         # network allowed
parallax/run.sh reference --adapter orb-slam --profile smoke --run-id orb-slam-smoke
parallax/run.sh reference --adapter orb-slam --profile full --run-id orb-slam-full
```

The reference executions are offline. Smoke processes the first 300 associated
RGB-D frames; full processes all 798. The headless runner exports the optimized
camera and keyframe trajectories, per-frame tracking states, a voxel-deduplicated
set of live landmarks at their final post-shutdown positions, a depth-derived
visible-surface reference, runtime, peak CPU memory, and two controlled variants.
The occlusion variant blanks the middle 15% of RGB and depth frames before
restoring observations; the dynamic variant inserts a moving foreground patch
with inconsistent depth. Both variants export an online trajectory. The first
also records Atlas map identity before loss and after tracking resumes, so a
new-map restart is not mislabeled as relocalization. They do not test unobserved
scene completion.

Metrics preserve their direction and task. ATE and RPE evaluate trajectory;
landmark-to-depth distance is map accuracy; depth-to-landmark distance is map
completeness. Precision, recall, and F-score use a 10 cm threshold after one
rigid SE(3) alignment estimated from the RGB-D trajectory. No scale alignment
is allowed because RGB-D supplies metric scale. One-frame translational RPE is
measured in the origin camera frame, rather than in the arbitrary world frame.
Endpoint translation and rotation drift use the first-pose-relative start-to-end
transform; they are not the final residual of a whole-trajectory alignment.
Each perturbed pose is positionally bound to its source-frame index and Atlas
map ID. One-frame RPE therefore skips missing source frames. If Atlas switches
maps, each contiguous single-map segment is aligned and scored independently;
global ATE and endpoint drift are omitted because the maps do not share a
validated gauge.
The reference surface is a deterministic maximum of 8,192 visible RGB-D
samples whose rays use the sequence's Brown-Conrady distortion coefficients,
on a 5 cm voxel grid; the estimated map contains final, live, observation-supported
sparse landmarks on a 2 cm grid. Accordingly, its F-score is a sparse
visible-map diagnostic, not a dense surface or complete-scene score.

On the locked image and host recorded in `reference-adapters.json`, smoke
tracked 300/300 frames with 0.0106 m ATE RMSE, 0.00595 m translational RPE,
0.0277 m endpoint drift, 1,779 final landmarks, and 0.603 map F-score. Full
tracked 798/798 frames with 0.0104 m ATE RMSE, 0.00585 m translational RPE,
0.0198 m endpoint drift, 2,023 final landmarks, and 0.636 map F-score.
Blank-frame tracking coverage was 0.833 in smoke and 0.850 in full. Smoke
resumed in the same Atlas map; its same-gauge aggregate ATE was 0.0119 m. Full
resumed in a new map, so no cross-map aggregate is reported: the pre-loss
segment had 0.0107 m ATE, while the post-restart segment had 0.0534 m ATE and
0.203 m endpoint drift. This is an explicit relocalization failure rather than
a favorable-result requirement. The moving patch caused no tracking loss, but
its trajectory is still evaluated (full ATE 0.0105 m and endpoint drift
0.0195 m), so coverage cannot hide pose damage. Thresholds—not exact
outputs—gate reproduction because thread scheduling changes feature-map details.

Expected artifacts are `trajectory.svg`, `output/CameraTrajectory.txt`,
`output/KeyFrameTrajectory.txt`, the two perturbed `CameraTrajectory-*.txt`
files, their two `TrajectoryContext-*.csv` frame/map bindings,
`output/tracking.csv`, `output/map.ply`, `output/ground-truth-map.ply`,
`output/failure-sweep.json`, `output/resources.json`, `report.md`, and the
hash-bound `result.json`. The adapter verifies the TUM archive and complete
extraction tree, immutable container image, source and Insula manifests,
semantic artifacts, recomputed baseline and failure-trajectory metrics,
resource-summary equality, acceptance thresholds, and atomic promotion.

### Transition

Classical methods expose weak or missing evidence directly. Learned depth and
completion add dataset priors, improving difficult observations while making
it essential to label which geometry is measured and which is predicted.

## 8. Learned depth, MVS, and deterministic completion

### Evidence and observability

Monocular depth networks see one RGB image; learned MVS sees multiple images
and camera geometry; completion networks see partial voxels or points. Training
data supplies a prior over likely geometry. That prior improves estimates when
correspondence is weak, but it does not make metric scale observable from an
arbitrary monocular image. A completion can fill an occluded region without
that region being determined by the test evidence.

### Representation and inference

Depth maps, cost volumes, occupancy grids, semantic voxels, and completed point
sets are produced by amortized inference. A deterministic network returns one
conditional estimate. Its output variability under augmentation or dropout is
not automatically a calibrated multimodal posterior. Learned fusion can combine
measurement and prior, but evaluation should retain confidence and support
labels.

### Defining mathematics

Monocular depth commonly minimizes scale-aware or scale/shift-invariant loss.
For the maintained metric-depth diagnostic, one affine pair is fitted across
the entire declared profile and constrained to preserve depth order,

\[
(s^*,t^*)=\arg\min_{s\geq 0,t}\sum_i(s\hat d_i+t-d_i)^2.
\]

Raw metre-space error remains primary. If the unconstrained solution would use
a negative scale, the diagnostic records the boundary solution \(s^*=0\)
rather than making an order-reversed prediction look geometrically accurate.

Learned MVS builds a cost volume by warping features through depth hypotheses,
(C(p,d)=\operatorname{Var}_j f_j(w_j(p,d))). Point completion may minimize a
symmetric Chamfer distance, which can reward averaged geometry when multiple
completions are valid.

### Assumptions and failure modes

The learned prior assumes test scenes resemble training. Relative-depth scores
can conceal scale error after alignment. Cost volumes still fail under
occlusion and appearance change. Deterministic completion can place a familiar
shape where the evidence admits several alternatives, and semantic completion
can be confidently wrong out of distribution.

### Primary-source reading sequence

Start with supervised monocular prediction in
[eigen-2014](https://proceedings.neurips.cc/paper/2014/hash/91c56ce4a249fae5419b90cba831e303-Abstract.html),
then cross-dataset relative depth in
[ranftl-2020](https://doi.org/10.1109/TPAMI.2020.3019967), synthetic-to-real
monocular training and metric fine-tuning in
[yang-dav2-2024](https://arxiv.org/abs/2406.09414), learned multi-view cost
volumes in [yao-2018](https://doi.org/10.1007/978-3-030-01237-3_47), point
completion in [yuan-2018](https://doi.org/10.1109/3DV.2018.00088), and
semantic scene completion in
[song-2017](https://doi.org/10.1109/CVPR.2017.28).

### Reproduction lab

```bash
parallax/run.sh run --module 08 --profile smoke --run-id pathway-08
```

Inspect `result.json`, `report.md`, `artifacts/learned_depth.svg`, and
`artifacts/failure_sweep.csv`. The lab compares metric and scale-aligned error,
then weakens correspondence while recording unsupported completion separately.

The maintained reference is the official Depth Anything V2 Metric Hypersim
Small checkpoint. Fetch and build are the only networked steps; execution is
offline and hash-verifies the 99,222,290-byte checkpoint before mounting it
read-only:

```bash
parallax/run.sh fetch --asset depth-anything-v2-metric-hypersim-small
parallax/run.sh build
parallax/run.sh reference --adapter depth-anything-v2 --profile smoke --run-id dav2-08
```

Source commit `a561b849ebae10a6f5ef49e26c83cbbcd36c71bf`, checkpoint
revision `3bc65d4e14a6786a61acec16453c50e12bf5f338`, checkpoint SHA-256
`b782898d8a3e8be1f639de33837ed85e9b4b73e40f8f5e5cd99067588d722545`,
and the Apache-2.0 checkpoint declaration are locked. Smoke predicts the center
shared-scene view plus a 1.25x effective-focal crop and a concave open-box OOD
case. Full predicts all nine shared-scene views plus the same two stressors.
Every target is camera-axis depth for an input-visible ray. There is no target
or output behind an occluder, so this adapter is neither learned MVS nor scene
completion; those branches remain represented by the concept lab and reading
sequence.

On the recorded B200 Insula, smoke/full processed 3/11 cases in 6.49/12.29 s
with 1.29 GB peak compute memory. Raw RMSE was 3.80/3.97 m and raw AbsRel was
0.836/0.851; \(\delta_1\) was zero in both profiles. One profile-global,
order-preserving affine fit reduced RMSE to 1.16/1.19 m, with scales 0.309 and
0.0198; this near-flat full-profile fit is precisely why it is reported as a
diagnostic rather than metric accuracy. The shared smoke case's separate
localization fit reached the \(s=0\) boundary, exposing an order failure that a
per-image aggregate would have obscured. The stress cases did not have worse
raw RMSE than the shared case, so the run makes no causal claim that crop or
concavity alone caused the already-large domain failure.

Reference artifacts include float32 depth maps, binary validity masks, fixed-
scale truth/prediction/error PPM comparisons, one profile-global affine score,
per-case localization scores, runtime and CPU/GPU peaks,
source/checkpoint/Insula manifests, a short interpretation, and the hash-bound
`result.json`. Hypersim training and this repository-owned synthetic fixture
make these a controlled OOD reproduction, not a third-party benchmark result.

### Transition

Discrete depth, voxel, and point outputs tie geometry to a chosen sampling.
Continuous implicit fields move the representation into function space and
make differentiable rendering a general inverse-graphics tool.

## 9. Continuous geometry and differentiable inverse graphics

### Evidence and observability

Occupancy and signed-distance fields can be fit from 3D samples, masks, or
images through a renderer. A latent shape model also contributes learned
evidence. The zero level set may be observed near samples while its topology
and hidden side remain prior- or regularizer-dependent. Differentiability makes
image evidence optimizable; it does not add information absent from the images.

### Representation and inference

An occupancy field maps (o_\theta(x,z)\) to ([0,1]). An SDF maps a query to
signed distance, with surface (\mathcal S=\{x:f_\theta(x,z)=0\}).
DeepSDF-style auto-decoders optimize a latent (z) for each shape. IDR jointly
optimizes surface, appearance, and
cameras; NeuS converts an SDF into a volume-rendering density. Inference is
amortized, per-instance optimized, or hybrid depending on how (z) and
(\theta) are obtained.

### Defining mathematics

An SDF obeys the Eikonal condition near a regular surface,

\[
\|\nabla_x f_\theta(x)\|_2=1,\qquad
\mathcal S=\{x:f_\theta(x)=0\}.
\]

Differentiable rasterization or ray integration yields an image
(\hat I=\mathcal R(\mathcal S,a,c)), optimized with
(\|I-\hat I\|+\lambda\mathcal L_{geom}). Mesh extraction still samples the
field on a finite grid before marching cubes.

### Assumptions and failure modes

Finite network capacity, positional encoding, and sample distribution determine
detail. Eikonal regularization does not guarantee correct topology. A latent
shape prior can complete an unseen side but may select the wrong category mode.
Image-based inverse graphics can trade camera, lighting, reflectance, and shape
against one another. Extraction cost and resolution remain real even when
storage is continuous.

### Primary-source reading sequence

Read continuous occupancy in
[mescheder-2019](https://openaccess.thecvf.com/content_CVPR_2019/html/Mescheder_Occupancy_Networks_Learning_3D_Reconstruction_in_Function_Space_CVPR_2019_paper.html),
latent SDFs in
[park-2019](https://openaccess.thecvf.com/content_CVPR_2019/html/Park_DeepSDF_Learning_Continuous_Signed_Distance_Functions_for_Shape_Representation_CVPR_2019_paper.html),
GPU differentiation primitives in
[laine-2020](https://doi.org/10.1145/3414685.3417861), surface inverse rendering
in [yariv-2020](https://proceedings.neurips.cc/paper/2020/hash/1a77befc3b608d6ed363567685f70e1e-Abstract.html),
and SDF-aware volume rendering in
[wang-neus-2021](https://proceedings.neurips.cc/paper/2021/hash/e41e164f7485ec4a28741a2d0ea41c74-Abstract.html).
The executable reference uses the official
[nerfstudio-neus-facto-2025](https://github.com/nerfstudio-project/nerfstudio/tree/50e0e3c70c775e89333256213363badbf074f29d),
not an official-paper NeuS checkpoint.

### Reproduction lab

```bash
parallax/run.sh run --module 09 --profile smoke --run-id pathway-09
```

Inspect `result.json`, `report.md`, `artifacts/representation_scaling.svg`, and
`artifacts/failure_sweep.csv`. Dense voxel memory is swept cubically while
field storage, extraction evaluations, topology, and hidden completion are
reported separately.

The concept lab is analytic: it samples the same sphere as a finite voxel
grid, occupancy level set, and signed-distance level set. It reports storage,
zero-crossing samples, extraction work, a coarse-grid topology merge, and an
unobserved counterfactual separately. An implicit field's compact parameters
do not make marching-cubes evaluation free, and a value behind all cameras is
not evidence-backed completion.

### Maintained reference

Fetch the one initialization-only perceptual backbone during the explicit
networked phase, then run the pinned reference offline:

```bash
parallax/run.sh fetch --asset nerfstudio-lpips-alexnet
parallax/run.sh reference --adapter neus-facto --profile smoke --run-id neus-smoke
parallax/run.sh reference --adapter neus-facto --profile full --run-id neus-full
```

NeuS-Facto observes calibrated context RGB only and optimizes one SDF/radiance
field per scene. The repository-generated masks, depths, normals, analytic
surface samples, and target images are evaluation truth, not training input.
Camera poses remain fixed; there is no monocular prior, category latent,
completion decoder, or posterior sampler. The adapter uses the SDFStudio
OpenCV-to-Nerfstudio Y/Z axis conversion, queries the learned field in the
declared object-centred metric frame, and flips gradients on export because
the pinned configuration uses a positive-inside SDF while the pathway's normal
convention is outward.

Geometry is scored only against analytic truth visible from at least two
context cameras. Target RGB and depth are a separate rendering family, field
gradient residuals are a separate regularity family, and zero-context-support
surface samples are reported without a completion score. Smoke trains for
1,000 steps and extracts at (128^3); full uses the upstream-shaped 20,001
steps and (256^3). Both verify the B200 `sm_100` tiny-cuda-nn kernel,
NeuS-Facto forward/backward path, coarse SDF extraction, source commits,
runtime versions, read-only checkpoint hash, offline container flags, and
atomic artifact promotion.

The latest B200 smoke reproduction completed in 42.3 seconds with 5.32 GB peak
compute memory. It reached common-visible F@10 cm 0.421, accuracy RMSE 0.225 m,
outward-normal error 64.5 degrees, mean Eikonal residual 0.102, and back-arc
target PSNR 8.08 dB. The full reproduction took 575.9 seconds and 6.40
GB peak compute memory; it reached F@5 cm 0.220, RMSE 0.212 m, completeness
0.538, outward-normal error 61.6 degrees, Eikonal residual 0.0318, and target
PSNR 8.39 dB. These values establish reproducible execution gates, not quality
claims: the field contains many zero crossings outside image-supported surface,
and held-out views lie well beyond the context arc. The failure is the lesson.
Photometric fit and Eikonal regularity do not prove accurate topology, hidden
completion, or coherent scene-hypothesis sampling.

Expected maintained-reference artifacts include the checkpoint and locked
config, float32 SDF grid, NPZ/PLY mesh, target RGB/depth/normal arrays,
resolution failure sweep, source/runtime/Insula manifests, resource trace,
metric visualizations, hash-bound `result.json`, and the generated report.

### Transition

Implicit geometry represents a surface first. Neural radiance fields instead
optimize a renderable volume first, which shifts the dominant success metric
toward held-out images.

## 10. Neural rendering and radiance fields

### Evidence and observability

The standard evidence is posed RGB images. Along observed rays, colors constrain
a combination of density, radiance, visibility, and camera parameters. Novel
view coverage can be strong even when density is spread, duplicated, or
view-dependent in ways that do not form a precise surface. Sparse-view systems
add learned cross-scene priors.

### Representation and inference

Neural Volumes use learned volumetric grids. NeRF maps position and direction
to density and view-dependent radiance. pixelNeRF conditions a shared network
on image features, amortizing across scenes. Mip-NeRF integrates positional
features over conical frusta. Surface-aware fields such as NeuS bias rendering
toward an SDF level set. The distinction between per-scene optimization and
amortized inference is as important as the field parameterization.

### Defining mathematics

For ray (r(t)=o+td), volume rendering gives

\[
\hat C(r)=\int_{t_n}^{t_f}T(t)\sigma(r(t))c(r(t),d)\,dt,
\quad T(t)=\exp\!\left(-\int_{t_n}^{t}\sigma(r(s))ds\right).
\]

Photometric training minimizes sampled ray error. PSNR is derived from image
MSE; it is not a surface-distance metric. Geometric evaluation must extract or
probe a surface and compare it independently.

### Assumptions and failure modes

Static scenes, accurate cameras, exposure consistency, and train/test view
coverage are common assumptions. View-dependent color can absorb geometry
error. Density floaters and transparent-looking shells can render well.
Sparse views permit many fields. Camera error can be traded against scene
structure. High image fidelity and low surface error may therefore disagree.

### Primary-source reading sequence

Begin with learned renderable volumes in
[lombardi-2019](https://doi.org/10.1145/3306346.3323020), then NeRF in
[mildenhall-2020](https://doi.org/10.1007/978-3-030-58452-8_24), amortized
conditioning in
[yu-pixelnerf-2021](https://openaccess.thecvf.com/content/CVPR2021/html/Yu_pixelNeRF_Neural_Radiance_Fields_From_One_or_Few_Images_CVPR_2021_paper.html),
multiscale integration in
[barron-2021](https://openaccess.thecvf.com/content/ICCV2021/html/Barron_Mip-NeRF_A_Multiscale_Representation_for_Anti-Aliasing_Neural_Radiance_Fields_ICCV_2021_paper.html),
and the surface-oriented alternative in
[wang-neus-2021](https://proceedings.neurips.cc/paper/2021/hash/e41e164f7485ec4a28741a2d0ea41c74-Abstract.html). The maintained
reference is the composite implementation registered in
[nerfstudio-nerfacto-2025](https://github.com/nerfstudio-project/nerfstudio/tree/50e0e3c70c775e89333256213363badbf074f29d);
it is not presented as a paper-exact reproduction of the original NeRF.

### Reproduction lab

```bash
parallax/run.sh run --module 10 --profile smoke --run-id pathway-10
```

Inspect `result.json`, `report.md`, `artifacts/comparison.json`,
`artifacts/field_comparison.npz`, `artifacts/radiance_vs_geometry.svg`, and
`artifacts/failure_sweep.csv`. The repo-owned analytic lab alpha-composites
sampled density and radiance, persists the exact RGB/depth arrays used for
scoring, and gives the radiance field higher PSNR while a separately evaluated
signed-distance field uses zero-level ray intersections and has lower depth
RMSE. This controlled construction is a numerical
concept demonstration, not a trained NeRF result; the maintained Nerfacto
adapter below supplies the reproduction result.

The maintained reproduction uses the pinned Nerfstudio `nerfacto` preset,
which is a composite implementation rather than a paper-exact original NeRF:

```bash
parallax/run.sh reference --adapter nerfacto \
  --profile smoke --run-id nerfacto-smoke
```

Only the five smoke or nine full primary context RGB images appear in the
training transform file. The input tree also contains the declared nine-view
superset for the trained failure sweep. Target RGB is loaded after optimization
solely for evaluation, and the entire input tree is mounted read-only while
output has a separate writable mount.
The adapter disables camera optimization, appearance embeddings, and scene
contraction; retains the upstream proposal sampler, field sizes, losses, mixed
precision, and optimizers; uses metric near/far bounds of 0.1/6.0 m; and runs
1,000 x 1,024-ray smoke or 20,001 x 2,048-ray full updates. A single loader
worker and an all-context train/eval split avoid the pinned parallel loader's
empty worker partition on this five-image fixture. They do not admit a target
image into training.

On the NVIDIA B200, the final provenance-bound smoke measurement reached
21.78 dB PSNR, 0.367 host-recomputed SSIM, 0.422 full-frame LPIPS,
0.218 m accumulation-qualified expected-depth RMSE, and 0.710 point F-score at
10 cm in 18.8 primary-training seconds. The full run reached 22.17 dB, 0.798,
0.198, 0.055 m, and 0.996 respectively in 345.4 primary-training seconds. The
truth-mask crop LPIPS values, 0.630 and 0.806, remain distinct from full-frame
LPIPS. Full-profile unsupported-region depth RMSE remained 0.369 m despite the
stronger visible-surface fit, retaining the back-arc extrapolation limitation. Each run
additionally trains 3-, 5-, and
9-context-view controls for 1,000 updates at 1,024 rays per batch. Hash-grid
CUDA updates are not bitwise deterministic here, so acceptance tolerances
bound measured variation rather than promising identical values. LPIPS remains
reported but is not a hard gate; PSNR, host-recomputed SSIM, opacity coverage,
depth RMSE, and point F-score retain independent regression bounds.

Expected maintained-reference artifacts include the final checkpoint and
resolved configuration, target and context RGB arrays, target
accumulation/median-depth/expected-depth arrays, recomputable 3/5/9-view sweep
renders, the 128³ or 256³ float32 density grid, threshold fractions plus
32³ component diagnostics, per-view full/crop metrics, complete dependency
locks, runtime/Insula/source manifests, resource trace, visualization,
hash-bound `result.json`, and generated report. Density thresholds remain field
diagnostics: a density field has no canonical SDF-like surface level. The full
profile additionally verifies the complete extraction tree of the locked NeRF
example archive, optimizes a second Nerfacto field from 16 fixed Lego training
views, and recomputes PSNR and SSIM on four fixed held-out views. Those
canonical-sample rendering measurements remain separate from the analytic
shared-scene geometry score because Lego supplies no matching analytic
surface/support contract in this bundle. Smoke does not require the 370 MB
canonical archive.

### Transition

NeRF stores a scene in a network or feature grid. Gaussian splatting makes
renderable primitives explicit and fast, while preserving the question of
whether rendering support coincides with a physical surface.

## 11. Gaussian splatting and explicit renderable primitives

### Evidence and observability

3D Gaussian Splatting usually starts from posed images and sparse SfM points.
It optimizes anisotropic primitives to explain image evidence. Feed-forward
variants predict primitives from image features or pointmaps. The evidence
supports renderable opacity and color along covered rays; it need not uniquely
support primitive centers as surface samples.

### Representation and inference

Each primitive carries mean (\mu), covariance (\Sigma), opacity, and color
coefficients. Projection yields an elliptical footprint that is composited in
visibility order. Classic 3DGS is per-scene optimized with adaptive
densification. Surface-aligned, 2D Gaussian, and mesh-extraction methods add
geometric structure. Feed-forward splat prediction amortizes initialization or
the complete representation.

### Defining mathematics

A 3D Gaussian has

\[
G(x)=\exp\!\left[-\tfrac12(x-\mu)^\top\Sigma^{-1}(x-\mu)\right],
\qquad \Sigma=RSS^\top R^\top.
\]

Projected alpha values are front-to-back composited,
\(C=\sum_i T_i\alpha_i c_i\), where
\(T_i=\prod_{j<i}(1-\alpha_j)\). Surface methods
regularize primitive normals, flatten one covariance axis, or reconstruct an
additional scalar field before meshing.

### Assumptions and failure modes

Pose errors and sparse coverage produce floaters. Large or elongated Gaussians
can cover rays without locating a surface. Densification raises detail and
memory but does not guarantee topology. Surface regularization can improve
geometry while lowering view-dependent rendering flexibility. Mesh extraction
is a separate operation with its own thresholds.

### Primary-source reading sequence

Historical credit starts with
[zwicker-2001](https://doi.org/10.1145/383259.383300): splatting predates 3DGS.
Then read modern differentiable 3DGS in
[kerbl-2023](https://doi.org/10.1145/3592433), surface-aligned extraction in
[guedon-lepetit-2024](https://openaccess.thecvf.com/content/CVPR2024/html/Guedon_SuGaR_Surface-Aligned_Gaussian_Splatting_for_Efficient_3D_Mesh_Reconstruction_and_CVPR_2024_paper.html),
2D surfel-like primitives in
[huang-2dgs-2024](https://doi.org/10.1145/3641519.3657428), and feed-forward
prediction in [smart-splatt3r-2024](https://arxiv.org/abs/2408.13912).
The maintained implementation is Nerfstudio Splatfacto at
[nerfstudio-splatfacto-2025](https://github.com/nerfstudio-project/nerfstudio/tree/50e0e3c70c775e89333256213363badbf074f29d)
with the pinned rasterization dependency
[gsplat-1.4.0](https://github.com/nerfstudio-project/gsplat/tree/4d3a3b69db4de0326f983ccf7b7b255271a17b01).
It is a maintained 3DGS-family reference, not a paper-exact reproduction of
Kerbl et al.

### Reproduction lab

```bash
parallax/run.sh run --module 11 --profile smoke --run-id pathway-11
```

Inspect `result.json`, `report.md`, `artifacts/gaussian_comparison.npz`,
`artifacts/gaussian_comparison.json`, `artifacts/splat_tradeoff.svg`, and
`artifacts/failure_sweep.csv`. The repo-owned lab renders deterministic,
isotropic screen-space Gaussian samples with a normalized-weight teaching
renderer; it is not an anisotropic, visibility-aware 3DGS implementation. Its
primitive-count sweep recomputes image PSNR, while a
viewing-axis center perturbation leaves the orthographic image unchanged and
increases center-to-sphere error. Projecting those centers back to the known
sphere is an analytic teaching regularizer, not a SuGaR/2DGS reproduction.
Mesh extraction is explicitly unsupported.

Run the maintained Splatfacto reproduction separately:

```bash
parallax/run.sh reference --adapter splatfacto \
  --profile smoke --run-id splatfacto-smoke
```

The adapter pins Nerfstudio commit
`50e0e3c70c775e89333256213363badbf074f29d`, gsplat 1.4.0 commit
`4d3a3b69db4de0326f983ccf7b7b255271a17b01`, Torch 2.7.1/CUDA 12.8,
and a Blackwell `sm_100` build. It optimizes one representation from five
smoke or nine full calibrated context RGB images with seed 260925, 50,000
random initial primitives at scale 2, camera optimization disabled, a black
background, the classic rasterizer, and scale regularization disabled. Smoke
runs 1,000 updates; full runs 30,000. Target truth is opened only after the
final checkpoint. Independent 3/5/9-view fits at 1,000 updates form the
reference failure sweep.

On the retained NVIDIA B200 calibration, smoke reached 22.54 dB held-out PSNR,
0.804 SSIM, 0.153 LPIPS, 0.201 m common-visible expected-depth RMSE, and 0.724
point F-score at 10 cm. Its primary fit took 11.1 seconds and ended with 1,749
primitives. Full reached 21.33 dB, 0.923, 0.119, 0.069 m, and 0.963 F-score at
5 cm in 251.8 training seconds, ending with 2,605 primitives. Both measured
1.50 GiB peak GPU compute memory; median target rendering was 555 and 517 FPS,
respectively, at the fixture resolution. These are retained configuration and
hardware measurements, not copied paper results or cross-method rankings.
Across repeated same-seed CUDA calibration and the retained reviewed runs,
smoke target SSIM ranged from 0.171 to 0.804 and full 5 cm point F-score from
0.612 to 0.963. Full adaptive-density fits also produced target SSIM as low as
0.632, 0.894 m expected-depth RMSE, and 0.017 F-score at 10 cm. Thus the former
0.80 SSIM, 0.80 m RMSE, and 0.05 F-score bounds rejected observed optimization
basins without identifying an execution collapse. The acceptance contract now
uses conservative stochastic B200 support/non-collapse gates: PSNR and visible
accumulation must remain usable, while finite nonzero geometry is retained as
characteristic evidence even when it is weak. They are not cross-method quality claims.
The raw quality metrics remain visible instead of promising
bitwise or basin-level reproducibility or selecting only favorable fits.

Expected depth is the ordered alpha-compositing expectation converted to
camera-axis depth, not a first physical surface intersection. Geometry scores
therefore remain view-conditioned diagnostics on accumulation-qualified,
common-visible rays. The full fit's visible expected-depth RMSE improved to
0.069 m while its separately reported unsupported-region RMSE was 0.869 m.
The output `gaussians.ply` is labelled renderable primitives, has no faces,
and is never called a mesh. Canonical surface extraction, mesh F-score,
hidden-surface completion, and posterior scene sampling remain unsupported;
surface-aware SuGaR or 2DGS requires a distinct future adapter.

### Transition

Per-scene optimization can be slow. Foundation geometry models amortize camera,
depth, pointmap, and correspondence prediction across large training sets.

## 12. Feed-forward visual geometry foundations

### Evidence and observability

DUSt3R, MASt3R, VGGT, and Depth Anything 3 accept one or more RGB images, often
without supplied poses. They regress pointmaps, depth, rays, cameras, tracks,
or matches using learned priors. They can bridge weak classical correspondence,
but their direct geometric support is still concentrated on visible image
content. Occluded surfaces are prior predictions if emitted at all.

### Representation and inference

DUSt3R predicts pairwise pointmaps in a common camera frame, followed by global
alignment for larger collections. MASt3R adds dense matching features and fast
reciprocal matching. VGGT jointly predicts cameras, depth, pointmaps, and
tracks with a feed-forward transformer. DA3 uses a unified depth-ray target and
supports inputs with or without known cameras. “Feed-forward” describes the
learned pass; retained alignment, calibration, filtering, or fusion stages
must still be reported.

### Defining mathematics

A pointmap assigns a 3D point to each pixel, (P_i(u)\in\mathbb R^3). Pairwise
predictions can be aligned by similarities (S_i):

\[
\min_{\{S_i\}}\sum_{(i,j),u}w_{iju}\|S_iP_{ij}(u)-S_jP_{ji}(v(u))\|_2^2.
\]

Depth-ray representations factor a point as (X=o+d\,r), coupling range and
camera rays. Pose AUC, depth error, point-cloud accuracy/completeness, runtime,
and memory should be reported independently.

### Assumptions and failure modes

Training distribution supplies priors over cameras and scenes. Low overlap,
repetition, reflections, tiny baselines, and long sequences remain difficult.
Confidence may correlate imperfectly with error. Predicted pointmaps can be
locally plausible but globally inconsistent. Visible-surface benchmarks do not
establish coherent hidden completion.

### Primary-source reading sequence

Read pointmap unification in
[wang-dust3r-2024](https://openaccess.thecvf.com/content/CVPR2024/html/Wang_DUSt3R_Geometric_3D_Vision_Made_Easy_CVPR_2024_paper.html),
3D-grounded matching in
[leroy-mast3r-2024](https://arxiv.org/abs/2406.09756), joint geometry prediction
in [wang-vggt-2025](https://arxiv.org/abs/2503.11651), and the depth-ray design
in [lin-da3-2025](https://arxiv.org/abs/2511.10647).

### Reproduction lab

```bash
parallax/run.sh run --module 12 --profile smoke --run-id pathway-12
```

Inspect `result.json`, `report.md`, `artifacts/foundation_geometry.svg`,
`artifacts/model_comparison.json`, `artifacts/gauge_alignment.npz`, and
`artifacts/failure_sweep.csv`. This repo-owned fixture applies a known global
similarity to exact visible points, then shows that raw error can be large while
Sim(3)-aligned error is numerical zero. Its overlap sweep is analytic, its
unobserved hemisphere has zero recall, and it contains no named-model quality
scores. It is an observability lesson, not a reproduced leaderboard.

The maintained comparison is separate and checkpoint-backed:

```bash
# Networked build. This also prepares the reused Surflo B200 Insula and venv.
parallax/run.sh build

# Networked, explicit, and hash verified. Restricted weights are not committed.
parallax/run.sh fetch --asset foundation-geometry-models

# Offline B200 execution after fetch.
parallax/run.sh reference --adapter foundation-geometry \
  --profile smoke --run-id module12-smoke
parallax/run.sh reference --adapter foundation-geometry \
  --profile full --run-id module12-full
```

It runs two precisely named direct modes from unposed RGB only:

- `vggt/direct` uses the original VGGT-1B checkpoint and the exact upstream
  `a288dd0…` source archive, both independently byte-locked. It uses official
  518-pixel preprocessing, predicted cameras and
  camera-z depth, depth unprojection as the canonical pointmap, the untouched
  direct point head as a second result, and 16 queried tracks. The checkpoint
  is CC BY-NC 4.0; this scientific reference is not permission for commercial
  use or redistribution.
- `da3-base/camera-head` uses Apache-2.0 DA3-BASE at 504-pixel upper-bound
  resize with fixed first-image reference selection. It predicts cameras,
  camera-z depth, and confidence; points are obtained by deterministic
  unprojection. It has no direct point head or track output.

Raw, SE(3), and Sim(3) rows remain separate. Alignment is performed by the
evaluator after the feed-forward pass and is never relabelled as model
optimization. Camera orientation fixes the global rotation before fitting
rigid or similarity translation/scale, so two-view alignment has no arbitrary
rotation about its baseline. Monocular scale uses declared visible-point
correspondences and is labelled evaluator-only.

The smoke sweep covers native one-view inference, high/low-overlap pairs,
three/five views, and a five-view permutation. The full sweep uses fixed nested
1/2/4/8/16-view subsets, high/medium/low/disconnected pairs, and an eight-view
permutation. Every case evaluates ground-truth observed and unseen surface
slices defined from the selected cameras, not model confidence.
Ground-truth cameras, masks, depths, and surfaces live outside the container's
RGB-only input mount. Bundle adjustment, global alignment, metric scale,
watertight surfaces, hidden completion, and posterior scene sampling remain
explicitly unsupported.

Corresponding-pixel threshold accuracy is not called F-score. Point-cloud
precision and completeness use bidirectional nearest-neighbor distances, and
their harmonic mean is reported as F1 at the declared metric and
scene-normalized thresholds. Confidence/coverage curves, direct-point
reprojection diagnostics, per-stage cold-load/preprocess/network/decode/export
timings, validity counts, source/checkpoint metadata, and the complete resolved
environment/native-binary manifest are retained in the run artifacts.
VGGT track records also declare the integer-centered processed-pixel lattice,
query frame, array shapes and dtypes, and visibility/confidence semantics; DA3
records tracks as unsupported. The foundation environment is rebuilt from an
exact CUDA base digest, dated Ubuntu snapshot, locked Python/uv archives, PEP
pylock, source pins, and hashed build scripts, then normalized and checked
against a complete byte-tree lock before inference.

On the locked NVIDIA B200 environment, smoke (five-view primary case) measured
VGGT pose AUC@30 0.910, Sim(3) camera RMSE 0.0365 m, scaled depth AbsRel 0.0090,
corresponding-point RMSE 0.161 m, and true observed-surface F1 0.413 at 10 cm;
DA3-BASE measured 0.817, 0.0649 m, 0.0276, 0.297 m, and 0.297. Full
(16-view primary case) measured 0.868/0.0848 m/0.0134/0.205 m/0.149 at 5 cm
for VGGT and 0.712/0.160 m/0.0194/0.394 m/0.0905 for DA3-BASE. Both unseen
surface recalls were zero at the declared thresholds. Primary-case totals were
2.69/1.64 s smoke and 6.83/4.17 s full for VGGT/DA3; all inference cases took
11.92/5.65 s and 27.49/13.17 s, respectively. End-to-end runtime, including
source/environment hashing, scene generation, evaluation, sealing, and report
creation, was 48.2 s smoke and 88.4 s full. Measured peak compute memory was
12.25 GB and 14.04 GB. These are one controlled-scene reproduction's integrity
baselines, not paper-table results or a general ranking. Exact source,
checkpoint, licence, preprocessing, environment, and protocol evidence is recorded in
`parallax/research/module12-reference-selection.md`.

### Transition

Foundation geometry returns an estimate. Generative 3D asks for conditional
alternatives and therefore has to specify where randomness lives and what makes
one sample internally coherent.

## 13. Generative 3D and scene priors

### Evidence and observability

Evidence may be partial geometry, one or more images, a scene layout, or text.
Training data supplies the prior; the observation (O) constrains a complete
state (S). The target is (p(S\mid O)), not simply a noisy prediction. A
completion is supported only where it preserves observed constraints, varies
where (O) is genuinely ambiguous, and keeps all outputs belonging to one
sample mutually consistent. Diversity without evidence consistency is noise;
evidence consistency without mode coverage is collapse; pooled point coverage
without within-sample coherence is hybridization. The posterior is rarely
known for real scenes, which is why the lab below uses two exactly balanced,
identifiable hidden hypotheses.

### Representation and inference

“Generative 3D” names different probabilistic objects. PointFlow samples a
global shape latent and then points conditionally. Shap-E diffuses parameters
of an implicit function. EG3D samples a hybrid triplane representation that is
rendered from cameras. DreamFusion optimizes one representation through a
frozen 2D score, while Zero-1-to-3 directly samples camera-conditioned images.
LRM amortizes deterministic image-to-triplane prediction. DiffComplete samples
object completion; DiffuScene and Coherent 3D Scene Diffusion model joint
object configurations. These outputs, inference procedures, and evidence
contracts are different and must not be collapsed into one accuracy ranking.

Sampling one persistent implicit field or scene-level object set is
structurally closer to a scene hypothesis than drawing unrelated points, but
it is still not posterior inference unless the conditioning preserves evidence
and the samples cover valid alternatives. A deterministic global encoding
(h(O)) is likewise not a stochastic scene state: independent decoders can
share (h(O)) while their private noise selects incompatible hidden modes.

### Defining mathematics

Flow matching learns a vector field for a probability path:

\[
\mathcal L_{FM}=\mathbb E_{t,x_t}\|v_\theta(x_t,t,O)-u_t(x_t\mid O)\|_2^2.
\]

The crucial factorization is structural. If two hidden scenes (A) and (B)
are equally compatible with the same observation, independent point decoding
implements

\[
p_{\mathrm{ind}}(X\mid O)=\prod_i\left[\tfrac12p_A(x_i)+
\tfrac12p_B(x_i)\right].
\]

It has the correct one-point marginal, yet almost every sufficiently dense
sample mixes mutually exclusive worlds. A scene mixture instead implements

\[
p_{\mathrm{scene}}(X\mid O)=\tfrac12\prod_i p_A(x_i)+
\tfrac12\prod_i p_B(x_i).
\]

More generally, a coherent scene sampler uses

\[
p(S\mid O)=\int p(S\mid z^*,O)p(z^*\mid O)\,dz^*,
\]

then reuses one sampled (z^*) for every point count, query batch, camera, and
time step. Flow matching specifies a transport objective; it does not specify
whether the transported state is one point, an object set, or a persistent
scene latent. PointFlow predates the Flow Matching objective and already has a
shared shape latent, so it belongs on the coherent side of this analytic
contrast even though it does not solve conditional scene inference by itself.

### Assumptions and failure modes

Text or image priors can overpower observed geometry. Score distillation can
exploit a 2D model without producing multi-view consistency. A stochastic view
generator can redraw hidden content for every camera. Individually plausible
object completions can intersect, float, or lose identity when composed.
Independent random points can cover both hidden modes in aggregate while
mixing them within every sample; redrawing a global latent between query
batches defeats persistence too. A single ground-truth completion cannot
identify a one-to-many posterior, and best-of-(K) alone rewards sample count.
Report observed-evidence error, within-sample coherence, hybrid fraction,
coherent mode coverage, between-sample diversity, calibration where known, and
cross-query persistence separately.

### Primary-source reading sequence

Read hierarchical point generation in
[yang-pointflow-2019](https://openaccess.thecvf.com/content_ICCV_2019/html/Yang_PointFlow_3D_Point_Cloud_Generation_With_Continuous_Normalizing_Flows_ICCV_2019_paper.html),
the general flow objective in
[lipman-2023](https://openreview.net/forum?id=PqvMRDCJT9t), and persistent
implicit-parameter diffusion in
[jun-shap-e-2023](https://arxiv.org/abs/2305.02463). Contrast one latent
rendered from many cameras in
[chan-eg3d-2022](https://openaccess.thecvf.com/content/CVPR2022/html/Chan_Efficient_Geometry-Aware_3D_Generative_Adversarial_Networks_CVPR_2022_paper.html)
with view-conditioned image sampling in
[liu-zero123-2023](https://openaccess.thecvf.com/content/ICCV2023/html/Liu_Zero-1-to-3_Zero-shot_One_Image_to_3D_Object_ICCV_2023_paper.html).
Then separate 2D-prior optimization in
[poole-2022](https://arxiv.org/abs/2209.14988) from amortized deterministic
reconstruction in [hong-lrm-2023](https://arxiv.org/abs/2311.04400). For the
move from objects to scenes, read probabilistic object completion in
[chu-diffcomplete-2023](https://proceedings.neurips.cc/paper_files/paper/2023/hash/ef7bd1f9cbf8a5ab7ddcaccd50699c90-Abstract.html),
set-level scene synthesis in
[tang-diffuscene-2024](https://openaccess.thecvf.com/content/CVPR2024/html/Tang_DiffuScene_Denoising_Diffusion_Models_for_Generative_Indoor_Scene_Synthesis_CVPR_2024_paper.html),
joint image-conditioned pose/shape denoising in
[dahnert-scene-diffusion-2024](https://proceedings.neurips.cc/paper_files/paper/2024/hash/29c8c615b3187ee995029284702d3f43-Abstract-Conference.html),
and open-set relational composition in
[shi-scenemaker-2026](https://openaccess.thecvf.com/content/CVPR2026/html/Shi_SceneMaker_Open-set_3D_Scene_Generation_with_Decoupled_De-occlusion_and_Pose_CVPR_2026_paper.html).

### Reproduction lab

```bash
parallax/run.sh run --module 13 --profile smoke --run-id pathway-13
```

Inspect `result.json`, `report.md`, `artifacts/scene_coherence.svg`,
`artifacts/ambiguity_samples.svg`, `artifacts/ambiguity_samples.npz`,
`artifacts/ambiguity_comparison.json`, and `artifacts/failure_sweep.csv`. The
fixture places the same hidden object either left or right behind an identical
48-point observed occluder. The NPZ contains both hypotheses, every stochastic
assignment, repeated-query draws, and predicted visible points; validation
recomputes the reported metrics from those arrays.

In the locked smoke run (64 samples, 257 hidden points), independent decoding
had coherence 0.527, hybrid fraction 1.0, coherent-hypothesis coverage 0,
repeat-query consistency 0.498, and best-hypothesis RMSE 0.853 m. Its marginal
mode entropy was effectively one bit while its coherent-scene entropy was
zero: pooled diversity hid the failure. The shared
latent scored 1.0 coherence, 1.0 coherent coverage, 1.0 repeat consistency,
and zero best-hypothesis RMSE. Both covered both modes in aggregate and had
perfect observed-evidence consistency, so marginal coverage and evidence fit
cannot explain the difference. Full (4,096 samples, 4,097 hidden points)
measured 0.506 versus 1.0 coherence and 0.500 versus 1.0 repeated-query
consistency. As point count rises, the independent sample converges more
reliably to a stable hybrid, not to a scene. This is an analytic factorization
test, not a reproduction or quality claim for any cited model. The detailed
source and terminology ledger is in
`parallax/research/module13-generative-scene-priors.md`.

### Transition

A static scene state is not enough for video. Dynamic representations must
preserve identity and geometry through time while separating camera and object
motion.

## 14. Dynamic 3D and 4D representations

### Evidence and observability

Dynamic reconstruction uses time-indexed RGB or RGB-D observations, sometimes
from synchronized cameras and sometimes from one moving camera. Image motion
mixes camera motion, object root motion, local deformation, illumination,
visibility, and correspondence. For a world point (X_i(t)),

\[
u_i(t)=\pi\!\left(K(t)T_{cw}(t)X_i(t)\right).
\]

An arbitrary time-dependent world transform (H(t)) can be exchanged between
scene and camera,

\[
X'_i(t)=H(t)X_i(t),\qquad
T'_{cw}(t)=T_{cw}(t)H(t)^{-1},
\]

without changing the projected point. Static background, known calibration,
metric depth, synchronized views, inertial evidence, rigidity, or a learned
motion prior is therefore needed to choose a camera/object gauge. Optical flow
is image displacement; scene flow is a world-space 3D displacement; neither
alone guarantees a reconstructed surface or long-range identity.

Occlusion is missing evidence. A smooth interpolation behind an occluder can
choose the wrong identity even when the unordered geometry at reappearance is
nearly correct. Topology change, object birth/death, and temporary visibility
loss are separate events and require separate contracts.

### Representation and inference

Classical non-rigid factorization restricts shape to a low-dimensional basis;
scene-flow methods estimate explicit 3D displacement; DynamicFusion combines
metric RGB-D fusion with a canonical-to-live warp. D-NeRF and Nerfies optimize
time-conditioned or observation-conditioned deformations into canonical
radiance fields. NSFF adds forward/backward scene flow, while HyperNeRF lifts a
canonical template into a higher-dimensional ambient space for topology
change. BANMo makes root pose, articulation, camera, canonical shape, and
appearance separate variables; RoDynRF jointly optimizes cameras and a
static/dynamic radiance decomposition.

Persistent Dynamic 3D Gaussians intentionally propagate indexed primitives;
4D-GS instead emphasizes compact deformation-driven rendering, which is not by
itself a material-correspondence guarantee. OmniMotion optimizes long-range
quasi-3D tracks; St4RTrack predicts world-frame pointmaps and trajectories;
StreamSplat propagates online dynamic Gaussians. MoRel uses global and local
anchors for long sequences, while GaME updates the latest map after structural
change rather than retaining every object's complete history. These outputs
are per-sequence optimized, online deterministic, or feed-forward estimates;
none is generative future or scene-hypothesis sampling merely because it is
time dependent.

### Defining mathematics

A material trajectory defines scene flow

\[
v_i(t)=X_i(t+\Delta t)-X_i(t),
\]

while a canonical model maps (X_c=W_t(X_t)) and renders a field
(F(X_c,d,a_t)). A general (W_t) need not be invertible; a single ordinary 3D
canonical template cannot continuously represent every topology change.
Temporal consistency may penalize

\[
\sum_{t,i}\|X_i(t+1)-\Phi_t(X_i(t))\|^2,
\]

but this requires identities (i) or a defined correspondence field (\Phi_t).
For an object hidden through (t_b), the identity-aware reappearance error is

\[
E_{\mathrm{reid}}=\sqrt{\frac1{|Q|}\sum_{i\in Q}
\|\widehat X_i(t_b+1)-X_i(t_b+1)\|_2^2}.
\]

It must be reported beside the set-aligned error that is free to permute
object IDs. A low set error and a high identity-aware error expose a tracker
that reconstructs the right places with the wrong histories.

### Objectives and metrics

Rendering, depth, optical-flow, scene-flow, cycle, deformation-smoothness,
rigidity, and correspondence losses supervise different claims. Keep held-out
PSNR/SSIM/LPIPS separate from surface/depth error, world-frame trajectory EPE,
camera ATE, temporal displacement error, visibility accuracy, identity
switches, and first-frame reappearance error. Short-range flow-warp or flicker
metrics test appearance continuity, not material persistence. No rendering
metric is emitted by the repo-owned lab because it does not render images.

### Assumptions and failure modes

Low-rank, articulated, locally rigid, smooth-flow, and canonical-deformation
priors each exclude valid motions. Canonical deformation struggles with
topology change and newly appearing content; fixed persistent primitives
cannot reconstruct objects absent at initialization. Time-conditioned fields
can memorize frames without a stable material correspondence. Pairwise or
short-window trackers lose history under long occlusion. Joint camera/scene
optimization fails when background support is weak, camera motion is fast, or
intrinsics change. A high-quality dynamic render can therefore coexist with
wrong depth, camera trajectory, primitive identity, or re-identification.

### Primary-source reading sequence

Start with low-rank non-rigid factorization in
[bregler-nrsfm-2000](https://doi.org/10.1109/CVPR.2000.854941), the original 3D
motion quantity in
[vedula-scene-flow-1999](https://doi.org/10.1109/ICCV.1999.790293), and metric
canonical fusion in
[newcombe-dynamicfusion-2015](https://openaccess.thecvf.com/content_cvpr_2015/html/Newcombe_DynamicFusion_Reconstruction_and_2015_CVPR_paper.html).
Then compare time-conditioned canonical rendering in
[pumarola-dnerf-2021](https://openaccess.thecvf.com/content/CVPR2021/html/Pumarola_D-NeRF_Neural_Radiance_Fields_for_Dynamic_Scenes_CVPR_2021_paper.html),
elastic observation-to-canonical warps in
[park-nerfies-2021](https://openaccess.thecvf.com/content/ICCV2021/html/Park_Nerfies_Deformable_Neural_Radiance_Fields_ICCV_2021_paper.html),
explicit neural scene flow in
[li-nsff-2021](https://openaccess.thecvf.com/content/CVPR2021/html/Li_Neural_Scene_Flow_Fields_for_Space-Time_View_Synthesis_of_Dynamic_CVPR_2021_paper.html),
and topology-changing hyperspace in
[park-hypernerf-2021](https://hypernerf.github.io/).

For factorization and correspondence, read articulated root/camera/local
motion in
[yang-banmo-2022](https://openaccess.thecvf.com/content/CVPR2022/html/Yang_BANMo_Building_Animatable_3D_Neural_Models_From_Many_Casual_Videos_CVPR_2022_paper.html),
joint camera/static/dynamic optimization in
[liu-rodynrf-2023](https://openaccess.thecvf.com/content/CVPR2023/html/Liu_Robust_Dynamic_Radiance_Fields_CVPR_2023_paper.html),
and occlusion-aware long-range tracks in
[wang-omnimotion-2023](https://openaccess.thecvf.com/content/ICCV2023/html/Wang_Tracking_Everything_Everywhere_All_at_Once_ICCV_2023_paper.html).
Contrast explicitly persistent primitives in
[luiten-dynamic3dgs-2024](https://doi.org/10.1109/3DV62453.2024.00044) with
deformation-driven Gaussian rendering in
[wu-4dgs-2024](https://openaccess.thecvf.com/content/CVPR2024/html/Wu_4D_Gaussian_Splatting_for_Real-Time_Dynamic_Scene_Rendering_CVPR_2024_paper.html).

Finally, read feed-forward world-frame tracks in
[feng-st4rtrack-2025](https://st4rtrack.github.io/), online uncalibrated
Gaussian reconstruction in
[wu-streamsplat-2026](https://proceedings.iclr.cc/paper_files/paper/2026/hash/c822d05dcc00695ed6b63c9e97bb3449-Abstract-Conference.html),
long-sequence local anchors in
[kwak-morel-2026](https://cmlab-korea.github.io/MoRel/), and latest-state
evolving maps in [yugay-game-2026](https://vladimiryugay.github.io/game/).
The last method deliberately answers a different question from preserving a
complete 4D identity history.

St4RTrack is the preferred maintained learned-reference candidate because its
world-frame pointmaps and APD/EPE tracking outputs align with this module's
camera/object and persistence metrics. It is documented here, not claimed as
an executed reference: code, weights, licence, preprocessing, coordinate
adapter, and a B200 smoke result must be hash-locked before that status changes.

### Reproduction lab

```bash
parallax/run.sh run --module 14 --profile smoke --run-id pathway-14
```

Inspect `result.json`, `report.md`, `artifacts/dynamic_sequence.npz`,
`artifacts/dynamic_comparison.json`, `artifacts/dynamic_trajectories.svg`,
`artifacts/temporal_drift.svg`, and `artifacts/failure_sweep.csv`. Two
indistinguishable objects approach and reverse while fully occluded. A
constant-velocity tracker instead predicts pass-through. The same event is
evaluated with a static camera, a moving camera whose motion is known, and
joint motion where 35% of one dynamic object's displacement leaks into the
world-frame camera-center estimate. The sweep increases hidden duration.

Every result metric is recomputed from the NPZ, and validation independently
regenerates the sweep. Smoke uses 33 frames and eight hidden frames. Static
and known-moving-camera conditions both measured 0.36 m identity-aware error,
0.04 m set-aligned error, and zero identity accuracy: the unordered geometry
was nearly correct while both histories were switched. Known camera motion
added effectively zero visible or temporal error. With camera/object leakage,
camera ATE rose to 0.143 m, visible-object RMSE to 0.107 m, temporal
displacement RMSE to 0.0158 m, and identity-aware reappearance error to 0.478
m, even though camera-relative observation residual remained numerical zero.
Full uses 129 frames and 32 hidden frames and preserves the same controlled
0.36/0.04 m identity-aware/set-aligned contrast; the contaminated condition
measured 0.478/0.318 m with 0.145 m camera ATE.
This is an analytic observability and metric-contract experiment, not a quality
claim for any cited system. Detailed source, maintained-reference, and
terminology evidence is in
`parallax/research/module14-dynamic-4d.md`.

### Transition

The final case study returns to static reconstruction and asks exactly what
Surflo's global state and arbitrary-resolution surface flow establish—and what
architectural step remains before persistent generative scenes.

## 15. Surflo as the current case study

### Evidence and observability

Surflo takes a variable number of unposed RGB views. A frozen VGGT encoder
provides visual geometry evidence; a Perceiver compresses it into a fixed set
of global tokens. Observed surfaces are supported by the input views. Hidden
surfaces remain ambiguous, and the paired-scene benchmark makes that ambiguity
literal: two complete rooms have byte-identical context views but different
hidden furniture revealed only by targets.

### Representation and inference

Surflo decodes arbitrary numbers of oriented points. Each query begins as noise
in a 6D position/normal space and is transported by a conditional flow using
the same deterministic global token set. Optional rendering guidance correlates
nearby points during ODE integration, and meshing converts the oriented cloud
into a surface. This improves output resolution and visible-surface consistency
without a fixed output grid. The pathway's locked single-scene scout makes the
improvement concrete without promoting it to a benchmark claim: on Tanks &
Temples Ignatius, plain Surflo measured 0.9057 surface F1 and 0.004679
normalized Chamfer, versus 0.8565 and 0.006064 for the inherited VGGT
pointmap. Guided Surflo measured 0.8893 F1 and 0.004610 Chamfer, so guidance
did not improve every geometric metric even on that one scene.

### Defining mathematics

The existing decoder learns a conditional velocity

\[
\dot x_i(t)=v_\theta(x_i(t),t,h(O)),\qquad x_i(0)\sim p_0,
\]

for independent query noises (x_i(0)) and shared evidence encoding (h(O)).
Sharing the conditioning does not make the random choices a persistent scene
variable. The proposed transition is instead to learn

\[
p(z^* \mid O),\qquad z^*\sim p(\cdot\mid O),\qquad
x_i,\ I_c,\ S_t \sim p(\cdot\mid z^*,O),
\]

and reuse one persistent complete-scene state across points, cameras, and time.

### Assumptions and failure modes

The frozen encoder limits evidence adaptation. A fixed token state can compress
many views, but token sharing alone says nothing about a distribution over
complete scenes. Independent point transports may be locally regularized by
rendering guidance yet still omit both hidden alternatives or combine
incompatible marginals. Meshing cannot recover support absent from the points.
The paired benchmark therefore does not require a favorable completion.

### Primary-source reading sequence

Read the evidence backbone in
[wang-vggt-2025](https://arxiv.org/abs/2503.11651), the flow objective in
[lipman-2023](https://openreview.net/forum?id=PqvMRDCJT9t), and Surflo's design
and claims in [guedon-surflo-2026](https://arxiv.org/abs/2606.13644).

### Reproduction lab

```bash
parallax/run.sh run --module 15 --profile smoke --run-id pathway-15
```

Inspect `result.json`, `report.md`, `artifacts/surflo_hidden_support.svg`,
`artifacts/surflo_visible_surface.svg`, `artifacts/surflo_endpoint.json`,
`artifacts/surflo_endpoint_evidence.npz`, and `artifacts/failure_sweep.csv`.
The lab hashes and reuses both tracked result sets: the B200 single-scene scout
for visible-surface quality and the photoreal paired-scene result for hidden
support. It recomputes every reported scalar from the archived measured rows,
and validation independently compares those rows with both repository asset
locks. In the paired probe all four seeds are
`unsupported`, mean observed-common recall is about 0.766, mean
unobserved-common recall about 0.056, and support for either hidden hypothesis
is zero. The paired run used plain inference, 100,000 query points, and 100 ODE
steps; query count and rendering guidance were held fixed rather than claimed
as executed sweep axes. A favorable hidden completion is not an acceptance
condition. This is evidence for the open problem, not a failure hidden by an
acceptance threshold. The compact result retains hidden-hypothesis support
labels, not the point-level evidence needed to report within-sample coherence.
It also omits the candidate numerator and denominator, so the pathway preserves
the per-seed completion-precision values in the archive but does not aggregate
or interpret their zeros.
The code-level architecture, measurement boundary, and persistent-state
interface are detailed in
`parallax/research/module15-surflo-synthesis.md`.

### Transition

Surflo inherits feed-forward geometry evidence, global cross-view conditioning,
continuous arbitrary-resolution generation, oriented surface output, rendering
guidance, and a meshing path. It improves the fixed-output-budget problem. It
does **not** yet define coherent scene-hypothesis sampling: query noise belongs
to points, while a hypothesis must persist across the whole decoded scene.
The next architectural objective is one sampled (z^*) per scene, trained so
that its decodes preserve observations, cover conditional alternatives, remain
coherent within a sample, and can extend consistently through time.

## Reproduction infrastructure and acceptance

The dispatcher surface is deliberately small:

```text
run.sh build
run.sh fetch
run.sh list
run.sh run --module MODULE --profile smoke|full
run.sh validate --module MODULE --run-id ID
run.sh report --run-id ID
run.sh all --profile full
run.sh reference --adapter colmap-sfm --profile smoke|full --run-id ID
run.sh reference --adapter colmap-mvs --profile smoke|full --run-id ID
```

`build` and `fetch` are networked by declaration. Lab execution, validation,
and reporting are offline. Runs are written to cache-backed staging directories,
validated for schema, finite values, hashes, artifacts, and metric-family
separation, then atomically promoted. Existing run IDs are not overwritten.
The classical SfM, CUDA/Blackwell classical-MVS, and neural-rendering Insulas
are distinct; the pathway references the existing Blender and Surflo Insulas
for those specialized workloads. `build` prepares the Blender rootfs as well
as the pathway containers; `fetch --asset controlled-suite` fetches its locked
CC0 inputs. If the validated episode is absent, a full module dispatch renders
it offline before the lab begins. Every use verifies the locked recipe,
episode/validation manifests, and all 444 cached artifact hashes.
Maintained reference runs use their own `reference-runs/` namespace so their
measured outputs cannot be confused with controlled concept fixtures.
The full `all` command executes every adapter marked `landed`, moves each
validated output beneath the atomically promoted aggregate run, and binds the
module/reference result hashes into `report.json`. It is the B200 cross-era
acceptance gate. `all --profile full --fixture-only` is an explicit diagnostic
escape hatch and cannot set `full_acceptance=true`; smoke remains the compact
fixture contract unless `--with-references` is requested.

The Blender-controlled scene, cameras, masks, geometry, lighting, visibility,
and sensor-response summaries are bound across all compatible full modules.
Their task-specific teaching metrics remain separate from the photoreal
episode and from third-party benchmarks. Canonical Middlebury MVS, TUM RGB-D,
and NeRF Synthetic samples plus the repository's Surflo paired-scene result are
asset-locked. Large downloads, checkpoints, and run outputs remain in caches.
An offline audit checks metadata, citations, local hashes, historical-credit
caveats, and terminology. The optional online audit checks primary URLs:

```bash
python3 parallax/pipeline/audit.py --online
```

Acceptance is evidence, not optimism: geometry tests cover projection,
camera-center recovery, epipolar residual, triangulation, point refinement,
ICP, TSDF fusion, normals, and coordinate conversion. Every landed lab emits
task-appropriate metrics, resource use, provenance, a visualization, and a
controlled failure sweep. Cross-era reports never collapse geometry,
rendering, and generative metrics into one leaderboard.
