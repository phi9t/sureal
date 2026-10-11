# 11: Dense, accurate two-view geometry on the orbit scene

**What to build:** Two-view reconstruction good enough to bootstrap incremental SfM. Ticket 05 landed working geometry, but its live run on the orbit scene found only 12 matches, with a 15.4° rotation error and an 11.4° translation-direction error. That is too few correspondences and too much error to initialise SfM.

**Blocked by:** 05

**Status:** ready-for-agent

- [ ] **Diagnose before tuning.** Find out why so few matches survive, and record the counts at each stage: detected corners, descriptors, matches before and after the ratio test, after the mutual check, and RANSAC inliers. Likely causes to check:
  - Harris response and non-maximum suppression thresholds;
  - patch size compared with texture scale;
  - ratio-test strictness;
  - border handling.
- [ ] **Density.** At least 200 RANSAC inliers on adjacent smoke orbit views. On both profiles, at least 95% of matches are inliers to the ground-truth F.
- [ ] **Accuracy.** Rotation error below 1° and translation-direction error below 2° on adjacent views, with no noise added. Report the same numbers for the widest baseline pair in the full profile.
- [ ] **Refinement.** Relative-pose refinement (non-linear, on the essential-matrix manifold or via reprojection) follows RANSAC if it is needed to meet the thresholds.
- [ ] **Tests.** The thresholds above become regression tests on the smoke profile, with fixed seeds.
- [ ] **Live check.** Run `//parallax:two_view_orbit` on smoke and full. Record per-stage counts, errors and runtime.
- [ ] **Gates:** `//:repo_gate` and `//parallax/...`.
