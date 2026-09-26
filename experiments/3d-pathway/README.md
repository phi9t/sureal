# Executable 3D reconstruction pathway

This directory backs the survey in
[`docs/3d-reconstruction-pathway.md`](../../docs/3d-reconstruction-pathway.md).
It provides deterministic concept labs for all fifteen modules, machine-readable
source and asset registries, a common controlled scene, four distinct Insula
definitions, provenance-aware run storage, and citation/terminology auditing.

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
python3 experiments/3d-pathway/pipeline/audit.py --offline

# Required real-container gates (the full gate is intentionally opt-in):
(cd experiments/3d-pathway && SURFLO_REQUIRE_COLMAP_MVS_REFERENCE=1 python3 -m unittest -q tests.test_colmap_mvs_reference.ColmapMvsReferenceAdapterTest.test_real_colmap_mvs_reconstructs_and_meshes_the_smoke_scene)
(cd experiments/3d-pathway && SURFLO_REQUIRE_COLMAP_MVS_FULL=1 python3 -m unittest -q tests.test_colmap_mvs_reference.ColmapMvsReferenceAdapterTest.test_real_colmap_mvs_full_profile_on_b200)
(cd experiments/3d-pathway && SURFLO_REQUIRE_ORB_SLAM_REFERENCE=1 python3 -m unittest -q tests.test_orb_slam_reference.OrbSlamReferenceContractTest.test_real_orb_slam_smoke_tracks_tum_rgbd_and_exports_a_map)
(cd experiments/3d-pathway && SURFLO_REQUIRE_ORB_SLAM_FULL=1 python3 -m unittest -q tests.test_orb_slam_reference.OrbSlamReferenceContractTest.test_real_orb_slam_full_profile)

# Explicit network boundaries:
experiments/3d-pathway/run.sh build
experiments/3d-pathway/run.sh fetch
experiments/3d-pathway/run.sh fetch --asset tum-rgbd
python3 experiments/3d-pathway/pipeline/audit.py --online
```

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
trajectory and the persistent union of tracked sparse landmarks, and compares
them with timestamped motion-capture poses and a deterministic visible RGB-D
surface sample formed with the sequence's Brown-Conrady camera model. ATE/RPE
and directed map distances remain separate; one-frame translational RPE is
measured in the origin camera frame. The
failure sweep blanks a contiguous frame interval to test relocalization and
adds a moving RGB-D patch to expose static-world sensitivity. Asset extraction
rejects links and traversal, records every file hash, and execution rechecks
the archive and extraction tree before launching with `--network none`.

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
`all` stages the complete run and promotes it atomically; its `report.json`
manifest records completeness, sources, assumptions, interpretations, and the
Markdown report hash. A report made from a partial run says so explicitly.

`assets.lock.json` records the generated controlled suite, selected canonical
dataset inputs, and the existing paired-scene result. Downloaded datasets and
checkpoints stay outside Git. `sources.json` is the source of truth for title,
authors, year, venue, primary URL, themes, supported claims, and historical
credit caveats.
