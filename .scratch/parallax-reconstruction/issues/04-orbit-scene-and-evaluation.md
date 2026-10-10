# 04: Orbit scene with exact ground truth, plus evaluation metrics

**What to build:**
- A deterministic textured scene seen by cameras orbiting with real rotation, exporting ground-truth poses, per-view depth and surface samples.
- The pose and surface metrics that every real module will score against.

**Blocked by:** 01

**Status:** done

- [x] **Scene.** `scene/orbit.py` renders N views (smoke and full profiles) of the textured planes scene, with rotation and translation varying across views. `scene/ground_truth.py` exports K, R and t per view, depth maps, and dense surface samples with normals.
- [x] **Pose metrics.** `evaluation/pose_metrics.py` provides rotation and translation error, ATE after Sim(3) Umeyama alignment, and reprojection RMSE.
- [x] **Surface metrics.** `evaluation/surface_metrics.py` provides Chamfer distance, accuracy, completeness and F-score at τ, plus depth-map AbsRel and δ<1.25.
- [x] **Tests.**
  - Projecting the ground-truth surface into each view agrees with the rendered depth.
  - Each metric is zero, or perfect, on ground truth against itself.
  - Known perturbations give the expected values.
- [x] **Live check.** Generate both profiles inside the Parallax Insula and record the digests.
- [x] **Gates:** `//:repo_gate` and `//parallax/...`.

## Comments

### 2026-10-10

Live check ran first through `./bazelw` in the Parallax Insula. The intended
target did not exist before implementation:

- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:pinned_sources_test`: passed, 1/1 test.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax:generate_orbit_scene`: failed before implementation because target `//parallax:generate_orbit_scene` was not declared.

After implementation, both orbit-scene profiles were generated through
`./bazelw run` inside the Parallax Insula, writing to fresh `.bazel-cache`
directories mounted under `/experiment`:

- `./bazelw run --noexperimental_collect_system_network_usage --nocache_test_results //parallax:generate_orbit_scene -- --profile smoke --output /experiment/.bazel-cache/orbit-smoke-live.XNS66c`: returned 0, frame count 3, artifact count 18, surface sample count 9216, `manifest_sha256` `818a329131d85be0ffe2ba8b19b3c7a334e53982055991d6eb70980d8f7c2345`, `artifact_tree_sha256` `24fb108eaeedee3e3081c72eb4871605cc73ef757d6dfc0999da27b1c37316b4`.
- `./bazelw run --noexperimental_collect_system_network_usage --nocache_test_results //parallax:generate_orbit_scene -- --profile full --output /experiment/.bazel-cache/orbit-full-live.f6B6MM`: returned 0, frame count 7, artifact count 38, surface sample count 21504, `manifest_sha256` `e1b6a44204887e914cf107d16a170d37468fcd1f451c6e66483c7c670083ea19`, `artifact_tree_sha256` `98e40034e563541eb2e6aa05637c38ce50ddecc00175ec8b96767349ec1ef3e7`.

Focused and gate evidence:

- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax:test_orbit_scene //parallax:test_pose_metrics //parallax:test_surface_metrics`: red before implementation with missing `scene.orbit`, `evaluation.pose_metrics` and `evaluation.surface_metrics`; passed after implementation, 3/3 tests.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`: passed, 20/20 tests.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate`: passed, 19/19 tests, including `//:pinned_sources_test`.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: passed, 189/189 tests.
- CUDA gate intentionally not run in this worker sandbox because it has no GPU devices; the coordinator runs CUDA.

### 2026-10-10 coordinator review

Accepted. Follow-up for ticket 06: the orbit varies only azimuth, about a single axis. Add elevation variation, or a second orbit ring, before incremental SfM claims general rotation.
