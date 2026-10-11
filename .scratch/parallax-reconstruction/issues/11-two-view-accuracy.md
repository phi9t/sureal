# 11: Dense, accurate two-view geometry on the orbit scene

**What to build:** Two-view reconstruction good enough to bootstrap incremental SfM. Ticket 05 landed working geometry, but its live run on the orbit scene found only 12 matches, with a 15.4° rotation error and an 11.4° translation-direction error. That is too few correspondences and too much error to initialise SfM.

**Blocked by:** 05

**Status:** done

- [x] **Diagnose before tuning.** Find out why so few matches survive, and record the counts at each stage: detected corners, descriptors, matches before and after the ratio test, after the mutual check, and RANSAC inliers. Likely causes to check:
  - Harris response and non-maximum suppression thresholds;
  - patch size compared with texture scale;
  - ratio-test strictness;
  - border handling.
- [x] **Density.** At least 200 RANSAC inliers on adjacent smoke orbit views. On both profiles, at least 95% of matches are inliers to the ground-truth F.
- [x] **Accuracy.** Rotation error below 1° and translation-direction error below 2° on adjacent views, with no noise added. Report the same numbers for the widest baseline pair in the full profile.
- [x] **Refinement.** Relative-pose refinement (non-linear, on the essential-matrix manifold or via reprojection) follows RANSAC if it is needed to meet the thresholds.
- [x] **Tests.** The thresholds above become regression tests on the smoke profile, with fixed seeds.
- [x] **Live check.** Run `//parallax:two_view_orbit` on smoke and full. Record per-stage counts, errors and runtime.
- [x] **Gates:** `//:repo_gate` and `//parallax/...`.

## Comments

### 2026-10-10

Live checks were run first through `./bazelw` in the Parallax Insula, with
`SUREAL_BAZEL_CACHE=$PWD/.bazel-cache` and fresh `TMPDIR` directories under
`~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/para11-two-view-accuracy-20261011T004914Z/tmp`.

Pre-tuning baseline:

- `./bazelw run --noexperimental_collect_system_network_usage --nocache_test_results //parallax:two_view_orbit -- --profile smoke --artifacts /experiment/.bazel-cache/t11-live-before-smoke.HVtRw4 --output /experiment/.bazel-cache/t11-live-before-smoke.HVtRw4/summary.json`: returned 0, elapsed 16 seconds.
  - Pair `frame-000` to `frame-001`.
  - Detected corners: view1 155, view2 156; descriptors: view1 155, view2 156.
  - Matches after the pre-existing ratio+mutual matcher: 12.
  - Ground-truth-F inliers: 11/12, ratio 0.9166666666666666.
  - RANSAC inliers: 11/12, ratio 0.9166666666666666.
  - Rotation error 15.376075248818927 degrees; translation-direction error 11.411616989215457 degrees.
  - Triangulated point RMSE after scale alignment 0.5158132976004797 m.
  - Manifest SHA-256 `818a329131d85be0ffe2ba8b19b3c7a334e53982055991d6eb70980d8f7c2345`; artifact count 20; artifact tree SHA-256 `8840d7012008f15ba234581f2c5093f9453ef4528bfd1fc0931c0148676e6a74`.
- `./bazelw run --noexperimental_collect_system_network_usage --nocache_test_results //parallax:two_view_orbit -- --profile full --artifacts /experiment/.bazel-cache/t11-live-before-full.LZazNy --output /experiment/.bazel-cache/t11-live-before-full.LZazNy/summary.json`: returned 0, elapsed 14 seconds.
  - Pair `frame-000` to `frame-001`.
  - Detected corners: view1 453, view2 478; descriptors: view1 453, view2 478.
  - Matches after the pre-existing ratio+mutual matcher: 73.
  - Ground-truth-F inliers: 49/73, ratio 0.6712328767123288.
  - RANSAC inliers: 39/73, ratio 0.5342465753424658.
  - Rotation error 8.196139475638347 degrees; translation-direction error 172.26126851142692 degrees.
  - Triangulated point RMSE after scale alignment 1.2526746933162238 m.
  - Manifest SHA-256 `e1b6a44204887e914cf107d16a170d37468fcd1f451c6e66483c7c670083ea19`; artifact count 40; artifact tree SHA-256 `ec4e698113d94d346290508d9c1fc56386cd605040073f050c6283ff6c8ff064`.

Diagnosis:

- The original Harris local-maximum and spacing settings produced too few
  candidate features for the orbit texture: 155/156 smoke corners and 453/478
  full corners. Dense high-response Harris candidates with descriptor border
  handling preserved raised both profiles to the configured budgets.
- The original global patch matching plus ratio and mutual-nearest filters left
  only 12 smoke matches and 73 full matches. The repeated planar textures need
  a local, motion-plausible search window before descriptor ratio testing; a
  broad local window admitted epipolar-line impostors, while directional orbit
  bounds preserved dense matches with ground-truth-F purity.
- Patch radius 3 gave enough local texture while keeping border loss low.
  Subpixel right-view patch refinement and robust nonlinear essential-manifold
  pose refinement were needed to bring the no-noise rotation and translation
  errors below the ticket thresholds.

Implemented:

- Dense Harris candidate mode for the orbit runner while keeping the existing
  local-maximum default for other callers.
- Descriptor diagnostics and local ratio+mutual matching with directional
  displacement bounds.
- Calibrated essential-matrix RANSAC, robust cheirality over degenerate
  correspondences, subpixel patch refinement, and robust nonlinear relative-pose
  refinement on the essential manifold.
- `//parallax:test_two_view_orbit`, a fixed-seed smoke regression for stage
  diagnostics, at least 200 RANSAC inliers, at least 95% ground-truth-F accepted
  inliers, rotation below 1 degree, and translation direction below 2 degrees.

Post-implementation live checks:

- `./bazelw run --noexperimental_collect_system_network_usage --nocache_test_results //parallax:two_view_orbit -- --profile smoke --artifacts /experiment/.bazel-cache/t11-smoke-quality.eCgh5h`: returned 0.
  - Pair `frame-000` to `frame-001`.
  - Stage counts: detected corners 2200/2200; descriptors 2200/2200; matches before ratio 2200; after ratio 1165; after mutual check 638; after quality filter 638; RANSAC inliers 613.
  - Accepted ground-truth-F inliers: 612/613, ratio 0.99836867862969.
  - Candidate ground-truth-F inliers: 632/638, ratio 0.9905956112852664.
  - RANSAC inlier ratio 0.9608150470219435 over the filtered matches.
  - Rotation error 0.05421722434599616 degrees; translation-direction error 0.19456833894985817 degrees.
  - Relative-pose refinement `robust_epipolar_least_squares`; RANSAC iterations 696; runner runtime 17.23383759893477 seconds.
  - Triangulated point RMSE after scale alignment 0.7978410080572218 m.
  - Manifest SHA-256 `818a329131d85be0ffe2ba8b19b3c7a334e53982055991d6eb70980d8f7c2345`; artifact count 20; artifact tree SHA-256 `80f02c565eaeee3f87d32432b685810c4d7b781cfe9a6f90b5c30caa48f8a3e5`.
- `./bazelw run --noexperimental_collect_system_network_usage --nocache_test_results //parallax:two_view_orbit -- --profile full --artifacts /experiment/.bazel-cache/t11-full-quality.3XpDbp`: returned 0, elapsed 97 seconds.
  - Adjacent pair `frame-000` to `frame-001`.
  - Stage counts: detected corners 3500/3500; descriptors 3500/3500; matches before ratio 3498; after ratio 2498; after mutual check 1549; after quality filter 700; RANSAC inliers 646.
  - Accepted ground-truth-F inliers: 633/646, ratio 0.9798761609907121.
  - Candidate ground-truth-F inliers: 687/700, ratio 0.9814285714285714.
  - RANSAC inlier ratio 0.9228571428571428 over the filtered matches.
  - Rotation error 0.3022782151566796 degrees; translation-direction error 1.752498737230835 degrees.
  - Relative-pose refinement `robust_epipolar_least_squares`; RANSAC iterations 1600; adjacent-pair runtime 42.4277731559705 seconds.
  - Triangulated point RMSE after scale alignment 0.5892015004139134 m.
  - Manifest SHA-256 `e1b6a44204887e914cf107d16a170d37468fcd1f451c6e66483c7c670083ea19`; artifact count 42; artifact tree SHA-256 `39c99fca0f641c34e7bcc735079fbcb3adc552aa58a8277e9342d01520f22668`.
  - Widest-baseline pair `frame-000` to `frame-006`: detected corners 3500/3500; descriptors 3500/3500; matches before ratio 3490; after ratio 1386; after mutual check 455; after quality filter 455; RANSAC inliers 367.
  - Widest-baseline accepted ground-truth-F inliers: 363/367, ratio 0.989100817438692.
  - Widest-baseline candidate ground-truth-F inliers: 407/455, ratio 0.8945054945054945.
  - Widest-baseline rotation error 0.5478223368417037 degrees; translation-direction error 0.22169271532318993 degrees; runtime 43.130822798004374 seconds.

Focused verification:

- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax:test_two_view_orbit`: failed before implementation with missing `match_stages` and smoke RANSAC inliers 11 < 200; passed after implementation.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:pinned_sources_test //parallax:test_two_view_orbit`: passed, 2/2 tests.

Gate evidence:

- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate`: passed, 23/23 tests, including `//:pinned_sources_test`.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: passed, 189/189 tests.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`: passed, 26/26 tests.
- CUDA gate intentionally skipped because this worker sandbox has no GPU
  devices; the coordinator runs CUDA.
