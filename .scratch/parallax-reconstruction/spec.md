# Parallax reconstruction: real geometry, algorithms and models behind the curriculum

Status: ready-for-agent

Governing decisions:
- `docs/adr/0001-directories-express-concepts.md`: directories name concepts.
- `docs/adr/0002-bazel-runs-inside-insula.md`: Bazel runs inside Insula and takes dependencies from the rootfs.

The layout was approved by the user on 2026-10-10. Conventions follow `.scratch/repo-quality/research/milano-conventions.md` (tests next to code, concept packages, no `sys.path` edits).

## Problem Statement

Parallax is meant to be a parallax-based 3D reconstruction codebase, but it contains almost no reconstruction code:

- **Reference adapters, about 9k lines.** These drive third-party systems in containers: COLMAP, ORB-SLAM, Depth Anything, nerfstudio and the Surflo foundation models.
- **Concept labs, about 1.3k lines.** Most of these generate illustrative curves. Some metrics are hardcoded. For example, the MVS lab reports `accuracy_mm: 1.8` and `f_score_2mm: 0.86`, and the SLAM lab "closes a loop" by subtracting drift it added itself.
- **Real math, 205 lines.** `math3d.py` holds projection, triangulation, single-point Gauss–Newton, Umeyama/ICP and a one-cell TSDF update.

Reports present the illustrative numbers next to measured ones with nothing to tell them apart. The layout groups files by kind (`pipeline/`, `tests/`), and the tests reach the code through `sys.path` edits.

## Solution

Grow Parallax into a real reconstruction codebase, one curriculum module at a time, without breaking the harness:

1. **Restructure into concept packages.** The packages are `camera/`, `scene/`, `features/`, `geometry/`, `sfm/`, `stereo/`, `fusion/`, `evaluation/`, `baselines/`, `curriculum/`, `pipeline/`, `assets/` and `schemas/`. Tests sit beside the code. Old import paths stay working through re-export shims until every caller has moved.
2. **Make the curriculum honest.** Each module declares a status: `synthetic`, `real` or `real+baseline`. Hardcoded lab metrics are labelled `illustrative`. Reports show the status of every number.
3. **Build the classical geometric chain for real, in our own code**, run on scenes with exact ground truth:
   - features and matching;
   - two-view geometry;
   - incremental SfM with Levenberg–Marquardt bundle adjustment;
   - plane-sweep MVS;
   - TSDF fusion with marching cubes.

   Metrics are always computed against ground truth. The COLMAP adapters become baselines compared in the same report.
4. **Add a real-data tier.** Middlebury MVS, compared with the COLMAP baseline as recorded evidence.

The target layout:

```
parallax/
  camera/      pinhole, pose (SE3/SO3), distortion
  scene/       textured_planes, orbit (rotating cameras), ground_truth
  features/    detect, describe, match
  geometry/    epipolar, pnp, triangulate, ransac, align (Umeyama, ICP)
  sfm/         tracks, initialize, incremental, bundle_adjust, reconstruction
  stereo/      plane_sweep, cost, depth_filter
  fusion/      tsdf, marching_cubes
  evaluation/  pose_metrics, surface_metrics
  baselines/   colmap_sfm, colmap_mvs, orb_slam, depth_anything, nerfacto, neus_facto, splatfacto, foundation_geometry
  curriculum/  labs (run_lab dispatch), synthetic/, curriculum.json
  pipeline/    cli, runner, reporting, contracts, validator, fetch, audit (orchestration only)
  assets/      assets.lock.json, sources.json, foundation-models.lock.json
  schemas/     *.schema.json
  insulas/     environment definitions
  research/    survey notes
```

Later modules get their own concept directories when they go real: `rendering/` for 10 and 11, `slam/` for 07, `learned/` for 08 and 12. They are not created up front.

## User Stories

1. As a researcher, I want SfM, MVS and fusion implemented in Parallax's own code, so that I can read, change and test every step of the reconstruction.
2. As a researcher, I want each algorithm to run on a scene with exact ground-truth poses and geometry, so that errors are measured rather than guessed.
3. As a researcher, I want orbiting cameras with real rotation, so that SfM is tested on the motion it must handle, not a pure x-translation.
4. As a researcher, I want our reconstructions compared with COLMAP in the same report, so that I know how far the implementation is from a maintained system.
5. As a reader of a report, I want each module and metric labelled `synthetic`, `real` or `real+baseline`, so that illustrative numbers are never mistaken for measurements.
6. As a reader of a report, I want hardcoded lab numbers marked `illustrative` now, before any module goes real.
7. As a maintainer, I want each concept in its own directory with its tests beside it, so that I can find the code for a concept in one place.
8. As a maintainer, I want the move to concept packages to change no behaviour, so that the restructure lands independently of the algorithms.
9. As a maintainer, I want old import paths to keep working until the last caller moves, so that no ticket needs a flag day.
10. As a maintainer, I want Parallax tests to import through the package root with no `sys.path` edits, so that the import checker's baseline entries for Parallax can be deleted.
11. As a test author, I want unit tests for each geometric primitive against closed-form or synthetic ground truth: projection round-trips, the epipolar constraint, PnP recovery, triangulation and Umeyama alignment.
12. As a test author, I want RANSAC-based estimators tested under a stated outlier ratio with a fixed seed, so that tests are deterministic.
13. As a researcher, I want bundle adjustment to report the initial and final reprojection RMSE and to recover poses to a stated tolerance after Sim(3) alignment.
14. As a researcher, I want plane-sweep depth maps scored against ground-truth depth: absolute relative error and the fraction of pixels within a threshold.
15. As a researcher, I want fused meshes scored by Chamfer distance, accuracy, completeness and F-score at τ against ground-truth surface samples.
16. As a researcher, I want an end-to-end run that goes from images to poses to depth to a mesh, using only our own code, so that the classical chain is proven to compose.
17. As a researcher, I want a real-data tier on Middlebury, so that results are not limited to synthetic scenes.
18. As an operator, I want every real module runnable through `parallax/run.sh run --module NN` inside the Parallax Insula, as today.
19. As an operator, I want the Parallax rootfs to carry exactly the pinned scientific dependencies the algorithms need, locked like every other rootfs.
20. As a curriculum author, I want each module's teaching observations to stay, attached to measured results once the module is real.

## Implementation Decisions

- **Dependencies.**
  - Classical modules use numpy and scipy (sparse linear algebra, `scipy.spatial`, `least_squares` where it fits). We write the algorithms ourselves: normalised 8-point and essential decomposition, PnP, triangulation, LM bundle adjustment with a Schur complement, plane sweep, TSDF, marching cubes. OpenCV may be used only for image I/O if it is needed at all. pycolmap and OpenCV geometry functions are not used in our implementations; they belong only in `baselines/`.
  - Neural modules (later) use PyTorch in the GPU rootfs.
  - C++ is introduced only for hot loops shown slow by profiling.
- **Rootfs.** scipy enters through a new Parallax rootfs, built from the existing recipe with an updated lock, which yields a new rootfs name and lock. The existing `rootfs-v2` is not modified.
- **Migration contract.**
  - `curriculum/labs.run_lab(module_id, artifacts, profile)` and the report schema stay stable.
  - A module switches from synthetic to real in its own ticket by routing to real code and computing its metrics from `evaluation/`.
  - `curriculum.json` gains a per-module `implementation` status. Reports carry the status per module and per metric.
- **Shims.** Moved modules leave a re-export shim at the old path. Shims are deleted when no caller remains, and the ticket that removes the last caller deletes the shim.
- **Data.**
  - The deterministic generated scenes are the hermetic tier. `scene/orbit.py` adds rotating cameras.
  - Middlebury is the real tier, refetched from `assets.lock.json` and verified by its digest.
  - The Blender controlled suite is regenerated later, when rendering modules need photoreal images.
- **Determinism.** All randomness is seeded. Tests use fixed seeds and stated tolerances.
- **Acceptance gate.**
  - Error thresholds against ground truth on the generated scenes are the gate.
  - The COLMAP comparison is recorded evidence and is not required to win.
  - Live runs come first: each ticket runs its module for real inside the Parallax Insula and records the metrics before backfilling cheap unit tests.

## Testing Decisions

- Test external behaviour through each concept's public functions, not private helpers. Good tests state the geometry they check, such as "points satisfy x2ᵀ F x1 ≈ 0" or "recovered poses match ground truth to 1e-6 without noise and to 0.5° with noise".
- Each concept has `*_test.py` files beside its code, wired as `py_test` in `parallax/BUILD.bazel` (or per-package BUILD files), and run by `//parallax/...`.
- Prior art:
  - `parallax/tests/test_classical.py`, which exercises `math3d`;
  - `test_colmap_reference.py` and `test_colmap_mvs_reference.py`, the baseline contracts;
  - Autonomy's co-located `*_test.py` pattern.
- Container-backed baseline tests keep their existing opt-in environment gates.
- **Gates per ticket:** `//:repo_gate`, `//parallax/...`, and `//autonomy/...` when shared code changes.

## Out of Scope

- Modules 07–15 going real: SLAM, learned depth, NeRF, Gaussian splatting, foundation geometry, generative models, 4D and Surflo. Each gets its own spec later. The layout reserves `slam/`, `rendering/` and `learned/`.
- Beating COLMAP.
- Regenerating the Blender controlled suite.
- Changes to the autonomy tree.

## Further Notes

The restructure (ticket 01) is mechanical and should land first, so that the algorithm tickets work in the final layout. The honesty labels (ticket 02) are cheap and should follow straight after. The scipy rootfs (ticket 03) needs a container build, which runs under the coordinator because worker sandboxes forbid container builds.
