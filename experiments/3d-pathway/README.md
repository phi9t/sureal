# Executable 3D reconstruction pathway

This directory backs the survey in
[`docs/3d-reconstruction-pathway.md`](../../docs/3d-reconstruction-pathway.md).
It provides deterministic concept labs for all fifteen modules, machine-readable
source and asset registries, a common controlled scene, seven local Insula
definitions plus the reused Blender and Surflo environments, provenance-aware
run storage, and citation/terminology auditing.

The smoke profile is the numerical and CI contract. The full profile only
increases the deterministic repo-owned fixture workloads. Maintained systems
run through explicit reference adapters, separately from both concept profiles.
`reference-adapters.json` distinguishes landed adapters from future work.
Controlled fixtures are teaching experiments, not reproduced third-party
leaderboard values.

```bash
# No network:
experiments/3d-pathway/run.sh list
experiments/3d-pathway/run.sh run --module 01 --profile smoke --run-id demo-01
experiments/3d-pathway/run.sh validate --module 01 --run-id demo-01
experiments/3d-pathway/run.sh all --profile smoke --run-id demo-all
experiments/3d-pathway/run.sh report --run-id demo-all
experiments/3d-pathway/run.sh reference --adapter colmap-sfm --profile smoke --run-id colmap-demo
experiments/3d-pathway/run.sh reference --adapter colmap-mvs --profile smoke --run-id colmap-mvs-demo
experiments/3d-pathway/run.sh reference --adapter orb-slam --profile smoke --run-id orb-slam-demo
experiments/3d-pathway/run.sh reference --adapter depth-anything-v2 --profile smoke --run-id dav2-demo
experiments/3d-pathway/run.sh reference --adapter neus-facto --profile smoke --run-id neus-demo
experiments/3d-pathway/run.sh reference --adapter nerfacto --profile smoke --run-id nerfacto-demo
experiments/3d-pathway/run.sh reference --adapter splatfacto --profile smoke --run-id splatfacto-demo
experiments/3d-pathway/run.sh reference --adapter foundation-geometry --profile smoke --run-id foundation-geometry-demo
python3 experiments/3d-pathway/pipeline/audit.py --offline

# Required real-container gates (the full gate is intentionally opt-in):
(cd experiments/3d-pathway && SURFLO_REQUIRE_COLMAP_MVS_REFERENCE=1 python3 -m unittest -q tests.test_colmap_mvs_reference.ColmapMvsReferenceAdapterTest.test_real_colmap_mvs_reconstructs_and_meshes_the_smoke_scene)
(cd experiments/3d-pathway && SURFLO_REQUIRE_COLMAP_MVS_FULL=1 python3 -m unittest -q tests.test_colmap_mvs_reference.ColmapMvsReferenceAdapterTest.test_real_colmap_mvs_full_profile_on_b200)
(cd experiments/3d-pathway && SURFLO_REQUIRE_ORB_SLAM_REFERENCE=1 python3 -m unittest -q tests.test_orb_slam_reference.OrbSlamReferenceContractTest.test_real_orb_slam_smoke_tracks_tum_rgbd_and_exports_a_map)
(cd experiments/3d-pathway && SURFLO_REQUIRE_ORB_SLAM_FULL=1 python3 -m unittest -q tests.test_orb_slam_reference.OrbSlamReferenceContractTest.test_real_orb_slam_full_profile)
(cd experiments/3d-pathway && SURFLO_REQUIRE_DEPTH_ANYTHING_REFERENCE=1 python3 -m unittest -q tests.test_depth_anything_reference.DepthAnythingReferenceAdapterTest.test_real_smoke_reference_runs_when_required)
(cd experiments/3d-pathway && SURFLO_REQUIRE_DEPTH_ANYTHING_FULL=1 python3 -m unittest -q tests.test_depth_anything_reference.DepthAnythingReferenceAdapterTest.test_real_full_reference_runs_when_required)
(cd experiments/3d-pathway && SURFLO_REQUIRE_NEUS_FACTO_REFERENCE=1 python3 -m unittest -q tests.test_neus_facto_reference.NeuSFactoReferenceAdapterTest.test_real_profiles_are_explicit_b200_gates)
(cd experiments/3d-pathway && SURFLO_REQUIRE_NEUS_FACTO_FULL=1 python3 -m unittest -q tests.test_neus_facto_reference.NeuSFactoReferenceAdapterTest.test_real_profiles_are_explicit_b200_gates)
(cd experiments/3d-pathway && SURFLO_REQUIRE_NERFACTO_REFERENCE=1 python3 -m unittest -q tests.test_nerfacto_reference.NerfactoReferenceExecutionContractTest.test_real_profiles_are_explicit_b200_gates)
(cd experiments/3d-pathway && SURFLO_REQUIRE_NERFACTO_FULL=1 python3 -m unittest -q tests.test_nerfacto_reference.NerfactoReferenceExecutionContractTest.test_real_profiles_are_explicit_b200_gates)
(cd experiments/3d-pathway && SURFLO_REQUIRE_SPLATFACTO_REFERENCE=1 python3 -m unittest -q tests.test_splatfacto_reference.SplatfactoOutputContractTest.test_real_profiles_are_explicit_b200_gates)
(cd experiments/3d-pathway && SURFLO_REQUIRE_SPLATFACTO_FULL=1 python3 -m unittest -q tests.test_splatfacto_reference.SplatfactoOutputContractTest.test_real_profiles_are_explicit_b200_gates)
(cd experiments/3d-pathway && SURFLO_REQUIRE_FOUNDATION_GEOMETRY_REFERENCE=1 python3 -m unittest -q tests.test_foundation_geometry_reference.FoundationGeometryReferenceContractTest.test_real_smoke_reference_runs_when_required)
(cd experiments/3d-pathway && SURFLO_REQUIRE_FOUNDATION_GEOMETRY_FULL=1 python3 -m unittest -q tests.test_foundation_geometry_reference.FoundationGeometryReferenceContractTest.test_real_full_reference_runs_when_required)

# Explicit network boundaries:
experiments/3d-pathway/run.sh build
experiments/3d-pathway/run.sh fetch
experiments/3d-pathway/run.sh fetch --asset tum-rgbd
experiments/3d-pathway/run.sh fetch --asset depth-anything-v2-metric-hypersim-small
experiments/3d-pathway/run.sh fetch --asset nerfstudio-lpips-alexnet
experiments/3d-pathway/run.sh fetch --asset foundation-geometry-models
python3 experiments/3d-pathway/pipeline/audit.py --online
```

The Module 12 reference reuses the Surflo B200 Insula and its persistent model
cache. `run.sh build` now prepares that Insula/rootfs/venv as well as the seven
pathway images. `run.sh fetch --asset foundation-geometry-models` resolves the
immutable VGGT-1B and DA3-BASE revisions plus the exact upstream VGGT source
archive in `foundation-models.lock.json`, then checks every source, config, and
weight byte. Preflight also rejects a dirty DA3 gitlink and verifies the full
6.81 GB resolved venv tree against its lock. The environment is reconstructive:
its recipe pins the CUDA base digest, dated Ubuntu snapshot, apt packages,
Python and uv archives, a hash-complete PEP pylock, source builds, and the build
scripts themselves. Clean-cache builds are normalized before complete-tree
verification so independently built roots must agree byte for byte. Execution
mounts only ordered RGB,
the non-secret execution contract, and read-only source/model caches into the
network-disabled container; evaluator cameras, depths, masks, and analytic
surface truth remain host-side. Raw, pose-constrained SE(3), and
pose-constrained Sim(3) scores are retained separately. The full sweep covers
nested 1/2/4/8/16 views, four overlap levels, order permutation, and observed
versus unseen truth surfaces. VGGT direct points/tracks are not conflated with
depth-unprojected points, and DA3's missing direct-point/track heads are
reported as unsupported. The original VGGT-1B weights are CC BY-NC 4.0;
DA3-BASE source and weights are Apache-2.0.

The landed COLMAP SfM adapter requires the classical image produced by
`run.sh build`. It renders the shared scene's explicit calibrated, multi-depth
plane-mosaic reference fixture (five smoke or nine full views), runs the exact
Ubuntu package `colmap=3.9.1-2build2` with container networking disabled, and
executes the immutable image ID inspected before launch. It atomically promotes
validated output under `reference-runs/RUN_ID/colmap-sfm/`. Validation checks
the SQLite catalog and required tables, binary and text sparse models, PLY
vertex count, package and Insula manifests, finite metrics, profile thresholds,
input calibration, execution log, report, hashes, and container provenance.

The COLMAP dense-MVS adapter requires
`surflo-pathway-classical-mvs:1`, built from COLMAP 4.2.0 source commit
`be5e29168d4aff238409d60424812df66aac919f` for CUDA architecture 100. This
release contains upstream's PatchMatch workaround for Blackwell GPUs; Ubuntu's
COLMAP package is intentionally not reused because its dense MVS path is not
CUDA-enabled. The adapter runs SfM, image undistortion, geometric-consistency
PatchMatch, stereo fusion, and Poisson meshing at trim 5 with networking
disabled. A cache-root CUDA JIT mount persists the upstream `90-virtual` PTX
compilation across runs.

The source commit, base-image digests, Dockerfile hash, and every executed
image ID are recorded. The build still resolves Ubuntu dependencies at build
time and is therefore version-attested per run, not claimed to be a
bit-reproducible OCI build; `baseline_environment` records the environment of
the reported measurements rather than acting as an image-identity gate.

The MVS fixture has five smoke or nine full views and unique appearance per
depth tile. It emits metric per-view depths plus a deterministic union of
visible-surface samples. After similarity-aligning the recovered camera gauge,
validation reports reconstruction-to-truth accuracy, truth-to-reconstruction
completeness, F-score at 10 cm, camera alignment, sparse/dense/mesh support,
runtime, and peak CPU/GPU memory. Geometry is deduplicated on a 1 cm voxel grid
and seed-sampled to at most 8,192 voxels per direction, making the metric
independent of PLY ordering and repeated-view weighting. Mesh support counts
only unique, non-degenerate faces. Completeness retains under-supported
deeper and background samples: a passing run is not relabeled as complete-scene
reconstruction. GPU memory is scoped to compute processes in the launched
container's cgroup, so unrelated jobs on a shared accelerator are excluded;
the hashed resource summary also records GPU UUIDs, models, compute capability,
and driver version.
Integer metrics revalidate exactly; floating metrics use recorded 1e-9 relative
and 1e-12 absolute tolerances, with the evaluating NumPy version retained in
the hashed run configuration.

The ORB-SLAM3 adapter uses its own Ubuntu 22.04 Insula with canonical upstream
ORB-SLAM3 commit `4452a3c4ab75b1cde34e5505a36ec3f9edcdc4c4` and peeled Pangolin
v0.6 commit `dd801d244db3a8e27b7fe8020cd751404aa818fd`. It runs TUM
`freiburg1_xyz` in RGB-D mode without a viewer, exports the optimized
trajectory and final live sparse landmarks after shutdown, and compares them
with timestamped motion-capture poses and a deterministic visible RGB-D
surface sample formed with the sequence's Brown-Conrady camera model. ATE/RPE
and directed map distances remain separate; one-frame translational RPE is
measured in the origin camera frame, while endpoint drift uses the
first-pose-relative start-to-end transform. The failure sweep exports and
evaluates both perturbed trajectories; it also compares Atlas map identity
before loss and after tracking resumes so a new-map restart is not called
relocalization. Asset extraction
rejects links and traversal, records every file hash, and execution rechecks
the archive and extraction tree before launching with `--network none`.

The Depth Anything V2 adapter uses the neural-rendering Insula with source
commit `a561b849ebae10a6f5ef49e26c83cbbcd36c71bf`, PyTorch 2.13.0/CUDA 13.2,
and the Apache-licensed Metric Hypersim Small checkpoint at immutable Hub
revision `3bc65d4e14a6786a61acec16453c50e12bf5f338`. The explicit fetch path locks
the checkpoint byte count and SHA-256; reference execution verifies it again,
mounts it read-only, and disables networking. Smoke evaluates one shared-scene
view plus focal-crop and concave-OOD stressors; full evaluates nine shared
views plus the stressors. Raw metre-space metrics remain primary, while one
profile-global non-negative-scale affine alignment is only a shape diagnostic;
per-case fits are retained solely to localize failures.
Outputs are deterministic per-view visible-ray depths with no hidden-scene or
posterior-sampling claim.

The NeuS-Facto adapter uses a dedicated CUDA 12.8 Insula with Nerfstudio commit
`50e0e3c70c775e89333256213363badbf074f29d`, tiny-cuda-nn commit
`0109538c37ac0bf613f2bac8de6cda48352feca7` built for `sm_100`, Torch
2.7.1, and Pillow 11.1.0. The Pillow pin is required by the selected
Nerfstudio source's image-loading API. Its LPIPS AlexNet initialization asset
is explicitly fetched, byte/hash checked, and mounted read-only; optimization
still runs with networking disabled. The adapter fits one bounded SDF/radiance
field from calibrated RGB, extracts a 128-cube smoke or 256-cube full mesh,
and reports common-visible geometry, held-out rendering, Eikonal residuals,
and unsupported geometry separately. Back-side output is never called
completion or a sampled scene hypothesis.

The Nerfacto adapter uses a separate CUDA 12.8 Insula with the same immutable
Nerfstudio and tiny-cuda-nn source commits, an exact Python requirements lock,
and a byte-compared full resolved-package manifest. Inputs are mounted
read-only, output is mounted separately, and execution has no network. The
primary five-view smoke or nine-view full fit renders held-out targets and
separately labelled context diagnostics; a fixed 3/5/9-view, 1,000-step sweep
records sparse-view failure evidence. Host evaluation recomputes PSNR, a fixed
Gaussian-window SSIM, visible-support depth/point metrics, unsupported-region
errors, density occupancy, and component counts from persisted arrays. LPIPS
comes from the pinned container but is not an acceptance gate. Density remains
a rendering field diagnostic, not an SDF surface or hidden-scene completion.

The Splatfacto adapter uses a seventh, CUDA 12.8 Insula with the same pinned
Nerfstudio source, gsplat 1.4.0 at commit
`4d3a3b69db4de0326f983ccf7b7b255271a17b01`, and Blackwell-native Torch
extensions. It fits explicit anisotropic Gaussian radiance primitives from
calibrated context RGB with networking disabled and writes the normalized
parameter arrays plus a face-free PLY labelled as renderable primitives. Host
evaluation recomputes held-out image metrics, accumulation-qualified expected
depth and point diagnostics, and a trained 3/5/9-view failure sweep. Expected
depth is an alpha-compositing statistic. Vanilla Splatfacto exposes no
canonical surface, triangle mesh, hidden-scene completion, or posterior scene
sample; every such field is retained as unsupported rather than inferred from
the PLY.

Runs default to `~/.cache/surflo/3d-pathway`. Set
`SURFLO_PATHWAY_CACHE_ROOT` to choose another cache. A module first writes to
`staging/`, validates schema and hashes, then atomically moves into
`runs/RUN_ID/MODULE/`. Existing module runs are never overwritten.

Every completed module contains:

- `result.json`: metrics separated into geometry, rendering, and generative
  families, resource use, environment, and input/config/artifact hashes;
- `report.md`: a short interpretation with assumptions and observed trend;
- `artifacts/failure_sweep.csv`: controlled intervention and response;
- at least one SVG visualization plus any module-specific compact evidence.

Every metric and artifact is labeled `controlled_fixture`, except module 15,
which is labeled `reused_measured_result` and checked against its asset lock.
Module 13's controlled fixture persists two mutually exclusive hidden-scene
hypotheses, all independent-point and shared-latent draws, repeat queries, and
visible evidence in `ambiguity_samples.npz`. Validation recomputes its
evidence, coherence, coverage, persistence, and best-hypothesis metrics from
that archive; the toy result is a factorization test, not a published-model
reproduction.
Module 14 persists exact cameras, camera-relative observations, visibility,
world-frame object identities, reconstructed visible centers, reappearance
predictions, unordered detections, and identity assignments in
`dynamic_sequence.npz`. Its analytic bounce-versus-pass-through event separates
set-aligned geometry from persistent identity and known camera motion from
dynamic-support leakage into the camera estimate. Validation recomputes every
metric and independently regenerates the occlusion-duration sweep; no image
metric is reported because the fixture does not render images.
`all` stages the complete run and promotes it atomically; its `report.json`
manifest records completeness, sources, assumptions, interpretations, and the
Markdown report hash. A report made from a partial run says so explicitly.

`assets.lock.json` records the generated controlled suite, selected canonical
dataset inputs, and the existing paired-scene result. Downloaded datasets and
checkpoints stay outside Git. `sources.json` is the source of truth for title,
authors, year, venue, primary URL, themes, supported claims, and historical
credit caveats.
