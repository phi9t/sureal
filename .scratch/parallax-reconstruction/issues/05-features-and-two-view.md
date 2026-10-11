# 05: Features, matching and two-view reconstruction

**What to build:** Two views of the orbit scene are reconstructed by our own code: keypoints, descriptors, matches, a robust essential matrix, the relative pose and triangulated points.

**Blocked by:** 03, 04

**Status:** done

- [x] **Features.** `features/detect.py` (Harris or DoG), `features/describe.py` (normalised patch or SIFT-like) and `features/match.py` (mutual nearest neighbour plus ratio test).
- [x] **Geometry.**
  - `geometry/epipolar.py`: normalised 8-point F/E, essential decomposition with cheirality.
  - `geometry/ransac.py`: seeded and generic.
  - `geometry/triangulate.py`: linear triangulation.
  - `geometry/pnp.py`: DLT plus refinement.
- [x] **Tests.**
  - Noise-free synthetic correspondences recover the pose to 1e-6.
  - RANSAC recovers the pose with 30% outliers (fixed seed).
  - Matches on the orbit scene are at least 90% inliers to the ground-truth F.
- [x] **Live check.** A two-view run on the orbit scene inside the Parallax Insula records:
  - match counts;
  - inlier ratio;
  - rotation error and translation-direction error;
  - triangulated point error after scale alignment.
- [x] **Gates:** `//:repo_gate` and `//parallax/...`.

## Comments

### 2026-10-10

Live check was attempted first through `./bazelw` in the Parallax Insula. The
pre-implementation command
`SURFLO_PATHWAY_CACHE_ROOT=~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/para05-features-and-two-view-20261010T233916Z/tmp/live-before ./bazelw run --noexperimental_collect_system_network_usage //parallax:run -- run --module 05 --profile smoke --run-id para05-before-20261010`
returned 1 because `//parallax:run` was not declared yet.

Implemented feature and two-view geometry code:

- `parallax/features/detect.py`: Harris response with deterministic local
  non-maximum suppression.
- `parallax/features/describe.py`: normalized square patch descriptors.
- `parallax/features/match.py`: mutual nearest-neighbour matching with a ratio
  test.
- `parallax/geometry/epipolar.py`: normalized 8-point F/E estimation,
  essential projection, decomposition and cheirality pose selection.
- `parallax/geometry/ransac.py`: seeded generic RANSAC.
- `parallax/geometry/triangulate.py`: vectorized linear triangulation.
- `parallax/geometry/pnp.py`: DLT PnP plus Gauss-Newton reprojection
  refinement.
- `parallax/pipeline/two_view_orbit.py` and `//parallax:two_view_orbit`: an
  Insula-runnable orbit-scene two-view check.

Focused verification:

- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax:test_feature_matching //parallax:test_two_view_geometry`: failed before implementation because the requested `features.*`, `geometry.epipolar`, `geometry.ransac` and `geometry.pnp` modules were missing; passed after implementation, 2/2 tests.

Final live check through the Parallax Insula:

- `./bazelw run --noexperimental_collect_system_network_usage --nocache_test_results //parallax:two_view_orbit -- --profile smoke --artifacts /experiment/.bazel-cache/two-view-live-final.LkSPXo --output /experiment/.bazel-cache/two-view-live-final.LkSPXo/summary.json`: returned 0.
- Profile `smoke`, pair `frame-000` to `frame-001`.
- Keypoints: view1 155, view2 156; described keypoints: view1 155, view2 156.
- Matches: 12.
- Ground-truth-F inliers: 11/12, ratio 0.9166666666666666.
- RANSAC inliers: 11/12, ratio 0.9166666666666666.
- Rotation error: 15.376075248818927 degrees.
- Translation-direction error: 11.411616989215457 degrees.
- Triangulated point RMSE after scale alignment: 0.5158132976004797 m.
- Orbit manifest SHA-256:
  `818a329131d85be0ffe2ba8b19b3c7a334e53982055991d6eb70980d8f7c2345`.
- Live artifact count: 20; artifact tree SHA-256:
  `8840d7012008f15ba234581f2c5093f9453ef4528bfd1fc0931c0148676e6a74`.

Gate evidence:

- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:pinned_sources_test`: passed, 1/1 test.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`: passed, 22/22 tests.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate`: passed, 19/19 tests, including `//:pinned_sources_test`.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: passed, 189/189 tests.
- CUDA gate intentionally not run in this worker sandbox because it has no GPU
  devices; the coordinator runs CUDA.
