# 04: Orbit scene with exact ground truth, plus evaluation metrics

**What to build:**
- A deterministic textured scene seen by cameras orbiting with real rotation, exporting ground-truth poses, per-view depth and surface samples.
- The pose and surface metrics that every real module will score against.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] **Scene.** `scene/orbit.py` renders N views (smoke and full profiles) of the textured planes scene, with rotation and translation varying across views. `scene/ground_truth.py` exports K, R and t per view, depth maps, and dense surface samples with normals.
- [ ] **Pose metrics.** `evaluation/pose_metrics.py` provides rotation and translation error, ATE after Sim(3) Umeyama alignment, and reprojection RMSE.
- [ ] **Surface metrics.** `evaluation/surface_metrics.py` provides Chamfer distance, accuracy, completeness and F-score at τ, plus depth-map AbsRel and δ<1.25.
- [ ] **Tests.**
  - Projecting the ground-truth surface into each view agrees with the rendered depth.
  - Each metric is zero, or perfect, on ground truth against itself.
  - Known perturbations give the expected values.
- [ ] **Live check.** Generate both profiles inside the Parallax Insula and record the digests.
- [ ] **Gates:** `//:repo_gate` and `//parallax/...`.
