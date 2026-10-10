# 05: Features, matching and two-view reconstruction

**What to build:** Two views of the orbit scene are reconstructed by our own code: keypoints, descriptors, matches, a robust essential matrix, the relative pose and triangulated points.

**Blocked by:** 03, 04

**Status:** ready-for-agent

- [ ] **Features.** `features/detect.py` (Harris or DoG), `features/describe.py` (normalised patch or SIFT-like) and `features/match.py` (mutual nearest neighbour plus ratio test).
- [ ] **Geometry.**
  - `geometry/epipolar.py`: normalised 8-point F/E, essential decomposition with cheirality.
  - `geometry/ransac.py`: seeded and generic.
  - `geometry/triangulate.py`: linear triangulation.
  - `geometry/pnp.py`: DLT plus refinement.
- [ ] **Tests.**
  - Noise-free synthetic correspondences recover the pose to 1e-6.
  - RANSAC recovers the pose with 30% outliers (fixed seed).
  - Matches on the orbit scene are at least 90% inliers to the ground-truth F.
- [ ] **Live check.** A two-view run on the orbit scene inside the Parallax Insula records:
  - match counts;
  - inlier ratio;
  - rotation error and translation-direction error;
  - triangulated point error after scale alignment.
- [ ] **Gates:** `//:repo_gate` and `//parallax/...`.
