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
[`curriculum.json`](../experiments/3d-pathway/curriculum.json). The shared scene
uses metres, a right-handed world frame, and OpenCV cameras
(x right, y down, z forward). All smoke labs are deterministic and offline;
`build` and `fetch` are the only network-capable dispatches. Each run records
input/config/artifact hashes, runtime, peak memory, a controlled sweep, and a
short interpretation. The `full` profile only increases the repo-owned
concept-fixture workload. It is not a B200 benchmark or a claim that the
heavyweight reference systems listed in `reference-adapters.json` have landed
unless their registry status explicitly says so. The first landed maintained
reference is the module-5 COLMAP SfM adapter.

```bash
experiments/3d-pathway/run.sh list
experiments/3d-pathway/run.sh all --profile smoke --run-id pathway-smoke
experiments/3d-pathway/run.sh report --run-id pathway-smoke
python3 experiments/3d-pathway/pipeline/audit.py --offline
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
experiments/3d-pathway/run.sh run --module 01 --profile smoke --run-id pathway-01
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
experiments/3d-pathway/run.sh run --module 02 --profile smoke --run-id pathway-02
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
experiments/3d-pathway/run.sh run --module 03 --profile smoke --run-id pathway-03
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
experiments/3d-pathway/run.sh run --module 04 --profile smoke --run-id pathway-04
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
experiments/3d-pathway/run.sh run --module 05 --profile smoke --run-id pathway-05
experiments/3d-pathway/run.sh reference --adapter colmap-sfm --profile smoke --run-id pathway-05-colmap
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
experiments/3d-pathway/run.sh run --module 06 --profile smoke --run-id pathway-06
experiments/3d-pathway/run.sh reference --adapter colmap-mvs --profile smoke --run-id colmap-mvs-06
```

Inspect `result.json`, `report.md`, `artifacts/mvs_views.svg`, and
`artifacts/failure_sweep.csv`. View count and exposure shift are separate
sweeps; accuracy, completeness, and hidden-surface recall remain distinct.

The maintained reference is a separate, offline COLMAP 4.2.0 execution pinned
to source commit `be5e29168d4aff238409d60424812df66aac919f`. Its CUDA 12.9.1
Insula is built explicitly for the available B200. This version boundary is
material: upstream fixed empty PatchMatch outputs on `sm_100+` in the
[COLMAP 4.0.3 release](https://github.com/colmap/colmap/releases/tag/4.0.3),
and 4.2.0 retains that workaround. COLMAP's
[installation guide](https://colmap.github.io/install.html) also notes that
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
experiments/3d-pathway/run.sh run --module 07 --profile smoke --run-id pathway-07
```

Inspect `result.json`, `report.md`, `artifacts/slam_drift.svg`, and
`artifacts/failure_sweep.csv`. The controlled loop redistributes synthetic
drift; the failure sweep increases dynamic-pixel fraction.

The maintained-system reproduction uses the official TUM
`freiburg1_xyz` RGB-D sequence and the canonical ORB-SLAM3 upstream at source
commit `4452a3c4ab75b1cde34e5505a36ec3f9edcdc4c4`:

```bash
experiments/3d-pathway/run.sh fetch --asset tum-rgbd       # network allowed
experiments/3d-pathway/run.sh build                         # network allowed
experiments/3d-pathway/run.sh reference --adapter orb-slam --profile smoke --run-id orb-slam-smoke
experiments/3d-pathway/run.sh reference --adapter orb-slam --profile full --run-id orb-slam-full
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
experiments/3d-pathway/run.sh run --module 08 --profile smoke --run-id pathway-08
```

Inspect `result.json`, `report.md`, `artifacts/learned_depth.svg`, and
`artifacts/failure_sweep.csv`. The lab compares metric and scale-aligned error,
then weakens correspondence while recording unsupported completion separately.

The maintained reference is the official Depth Anything V2 Metric Hypersim
Small checkpoint. Fetch and build are the only networked steps; execution is
offline and hash-verifies the 99,222,290-byte checkpoint before mounting it
read-only:

```bash
experiments/3d-pathway/run.sh fetch --asset depth-anything-v2-metric-hypersim-small
experiments/3d-pathway/run.sh build
experiments/3d-pathway/run.sh reference --adapter depth-anything-v2 --profile smoke --run-id dav2-08
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
experiments/3d-pathway/run.sh run --module 09 --profile smoke --run-id pathway-09
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
experiments/3d-pathway/run.sh fetch --asset nerfstudio-lpips-alexnet
experiments/3d-pathway/run.sh reference --adapter neus-facto --profile smoke --run-id neus-smoke
experiments/3d-pathway/run.sh reference --adapter neus-facto --profile full --run-id neus-full
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
experiments/3d-pathway/run.sh run --module 10 --profile smoke --run-id pathway-10
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
experiments/3d-pathway/run.sh reference --adapter nerfacto \
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
22.72 dB PSNR, 0.884 host-recomputed SSIM, 0.247 pinned-container LPIPS,
0.260 m accumulation-qualified expected-depth RMSE, and 0.664 point F-score at
10 cm in 16.7 primary-training seconds. The full run reached 23.88 dB, 0.866,
0.202, 0.072 m, and 0.989 respectively in 345.0 primary-training seconds. Its
unsupported-region depth RMSE remained 0.418 m despite the stronger visible
surface fit, retaining the back-arc extrapolation limitation. Each run
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
diagnostics: a density field has no canonical SDF-like surface level. The
locked NeRF example archive is a separately fetchable canonical supplement; the
current adapter does not consume it because it lacks the analytic
surface/support truth used by this geometry score.

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
(C=\sum_i T_i\alpha_i c_i), (T_i=\prod_{j<i}(1-\alpha_j)). Surface methods
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

### Reproduction lab

```bash
experiments/3d-pathway/run.sh run --module 11 --profile smoke --run-id pathway-11
```

Inspect `result.json`, `report.md`, `artifacts/splat_tradeoff.svg`, and
`artifacts/failure_sweep.csv`. Primitive count is swept while PSNR and surface
RMSE remain separate; surface regularization and extracted-mesh rendering are
reported as different outputs.

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
experiments/3d-pathway/run.sh run --module 12 --profile smoke --run-id pathway-12
```

Inspect `result.json`, `report.md`, `artifacts/foundation_geometry.svg`,
`artifacts/model_comparison.json`, and `artifacts/failure_sweep.csv`. The table
is a controlled contract fixture, not a reproduced leaderboard; maintained
model adapters in the Surflo environment are the full-profile target.

### Transition

Foundation geometry returns an estimate. Generative 3D asks for conditional
alternatives and therefore has to specify where randomness lives and what makes
one sample internally coherent.

## 13. Generative 3D and scene priors

### Evidence and observability

Evidence may be partial points, one or more images, or text. Training defines a
prior over shapes or scenes. The desired object is a conditional distribution
(p(S\mid O)), where all hypotheses explain observation (O) while differing
only where evidence permits. Diversity without evidence consistency is noise;
evidence consistency without mode coverage is collapse; marginal point
coverage without within-sample coherence is hybridization.

### Representation and inference

PointFlow samples a shape latent and then points conditionally. Flow matching
trains continuous transports. Diffusion can generate implicit parameters,
images used as multi-view priors, or 3D assets. DreamFusion optimizes a scene
through a 2D diffusion prior; Zero-1-to-3 produces view-conditioned images;
LRMs amortize image-to-triplane prediction. These solve different conditional
tasks and should not be grouped under one accuracy number.

### Defining mathematics

Flow matching learns a vector field for a probability path:

\[
\mathcal L_{FM}=\mathbb E_{t,x_t}\|v_\theta(x_t,t,O)-u_t(x_t\mid O)\|_2^2.
\]

The crucial factorization is structural. Independent point decoding resembles
(\prod_i p(x_i\mid O)). A coherent scene sampler uses

\[
p(S\mid O)=\int p(S\mid z^*,O)p(z^*\mid O)\,dz^*,
\]

then reuses one sampled (z^*) for every point, camera, and time step.

### Assumptions and failure modes

Text or image priors can overpower geometry. Score distillation can exploit a
2D model without producing multi-view consistency. Object generators do not
automatically compose scenes with physical relations. Independent random
points can represent both hidden modes in aggregate while mixing them in every
single sample. Diversity must be measured between samples and coherence within
samples.

### Primary-source reading sequence

Read hierarchical point generation in
[yang-pointflow-2019](https://openaccess.thecvf.com/content_ICCV_2019/html/Yang_PointFlow_3D_Point_Cloud_Generation_With_Continuous_Normalizing_Flows_ICCV_2019_paper.html),
the general flow objective in
[lipman-2023](https://openreview.net/forum?id=PqvMRDCJT9t), 2D-prior optimization
in [poole-2022](https://arxiv.org/abs/2209.14988), amortized large reconstruction
in [hong-lrm-2023](https://arxiv.org/abs/2311.04400), and view-conditioned image
priors in
[liu-zero123-2023](https://openaccess.thecvf.com/content/ICCV2023/html/Liu_Zero-1-to-3_Zero-shot_One_Image_to_3D_Object_ICCV_2023_paper.html).

### Reproduction lab

```bash
experiments/3d-pathway/run.sh run --module 13 --profile smoke --run-id pathway-13
```

Inspect `result.json`, `report.md`, `artifacts/scene_coherence.svg`,
`artifacts/ambiguity_comparison.json`, and `artifacts/failure_sweep.csv`. Both
samplers cover two hypotheses and satisfy the shared visible evidence. Only the
shared-latent sampler chooses one hypothesis per sample.

### Transition

A static scene state is not enough for video. Dynamic representations must
preserve identity and geometry through time while separating camera and object
motion.

## 14. Dynamic 3D and 4D representations

### Evidence and observability

Dynamic reconstruction uses time-indexed images, sometimes from multiple
cameras. Visible motion mixes camera motion, object motion, nonrigid
deformation, illumination, and occlusion. Correspondence through time is
observable only where appearance and motion make identity trackable. Long
occlusion requires memory or a prior, not interpolation of visible pixels.

### Representation and inference

Nerfies and D-NeRF map observations through a deformation field into a
canonical radiance field. Dynamic 3D Gaussians preserve primitive identities;
4D Gaussian methods learn deformation over time. Alternatives include explicit
scene flow, trajectories, time-conditioned fields, and persistent object
states. Inference can be per-sequence optimized or amortized, but the
camera/object factorization must be explicit.

### Defining mathematics

A deformation model uses (x_c=W(x,t)) and renders
(F(x_c,d)). Temporal consistency may penalize

\[
\sum_{t,i}\|X_i(t+1)-\Phi_t(X_i(t))\|^2,
\]

but this requires identities (i) or a correspondence field (\Phi_t).
Evaluation needs trajectory error, temporal geometry consistency, and
post-occlusion re-identification in addition to frame PSNR.

### Assumptions and failure modes

Canonical deformation struggles with topology change and newly appearing
content. Time-conditioned models can memorize frames without persistent
correspondence. Moving-camera and moving-object ambiguity causes drift.
Occlusion deletes direct evidence, so an apparently smooth interpolation may
switch identity. Dynamic rendering metrics can mask these failures.

### Primary-source reading sequence

Read canonical deformation in
[park-nerfies-2021](https://openaccess.thecvf.com/content/ICCV2021/html/Park_Nerfies_Deformable_Neural_Radiance_Fields_ICCV_2021_paper.html),
time-conditioned NeRF in
[pumarola-dnerf-2021](https://openaccess.thecvf.com/content/CVPR2021/html/Pumarola_D-NeRF_Neural_Radiance_Fields_for_Dynamic_Scenes_CVPR_2021_paper.html),
persistent primitives in
[luiten-dynamic3dgs-2024](https://doi.org/10.1109/3DV62453.2024.00044), and
compact 4D deformation in
[wu-4dgs-2024](https://openaccess.thecvf.com/content/CVPR2024/html/Wu_4D_Gaussian_Splatting_for_Real-Time_Dynamic_Scene_Rendering_CVPR_2024_paper.html).

### Reproduction lab

```bash
experiments/3d-pathway/run.sh run --module 14 --profile smoke --run-id pathway-14
```

Inspect `result.json`, `report.md`, `artifacts/temporal_drift.svg`, and
`artifacts/failure_sweep.csv`. The same event is evaluated with static camera,
moving camera, and joint camera/object motion while occlusion duration grows.

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
without a fixed output grid.

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
experiments/3d-pathway/run.sh run --module 15 --profile smoke --run-id pathway-15
```

Inspect `result.json`, `report.md`, `artifacts/surflo_hidden_support.svg`,
`artifacts/surflo_endpoint.json`, and `artifacts/failure_sweep.csv`. The lab
hashes and reuses the tracked photoreal result: all four seeds are
`unsupported`, mean observed-common recall is about 0.766, mean
unobserved-common recall about 0.056, and support for either hidden hypothesis
is zero. This is evidence for the open problem, not a failure hidden by an
acceptance threshold.

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
for those specialized workloads.
Maintained reference runs use their own `reference-runs/` namespace so their
measured outputs cannot be confused with controlled concept fixtures.

The controlled scene, cameras, masks, and split are shared across compatible
modules. Canonical Middlebury MVS, TUM RGB-D, and NeRF Synthetic samples plus
the repository's Surflo paired-scene result are asset-locked. Large downloads,
checkpoints, and run outputs remain in caches. An offline audit checks metadata,
citations, local hashes, historical-credit caveats, and terminology. The
optional online audit checks primary URLs:

```bash
python3 experiments/3d-pathway/pipeline/audit.py --online
```

Acceptance is evidence, not optimism: geometry tests cover projection,
camera-center recovery, epipolar residual, triangulation, point refinement,
ICP, TSDF fusion, normals, and coordinate conversion. Every landed lab emits
task-appropriate metrics, resource use, provenance, a visualization, and a
controlled failure sweep. Cross-era reports never collapse geometry,
rendering, and generative metrics into one leaderboard.
