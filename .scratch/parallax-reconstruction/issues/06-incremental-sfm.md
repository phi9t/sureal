# 06: Incremental SfM with bundle adjustment; module 05 goes real

**What to build:** All orbit views are registered by our incremental SfM and refined by our Levenberg–Marquardt bundle adjustment. Curriculum module 05 reports measured results, compared with the COLMAP SfM baseline on the same images.

**Blocked by:** 05

**Status:** ready-for-agent

- [ ] **Code.**
  - `sfm/tracks.py`: the track graph.
  - `sfm/initialize.py`: picks the best pair.
  - `sfm/incremental.py`: PnP registration, triangulation and periodic bundle adjustment.
  - `sfm/bundle_adjust.py`: LM with a Schur complement on scipy sparse matrices.
  - `sfm/reconstruction.py`: the data model.
- [ ] **Tests.**
  - Bundle adjustment reduces reprojection RMSE from a perturbed start, and recovers poses within tolerance on noise-free data.
  - Incremental SfM registers every view of the smoke orbit scene.
- [ ] **Module 05 goes real.** The module routes to `sfm/`, its metrics come from `evaluation/`, and its status is `real+baseline`. The report includes the `baselines/colmap_sfm` result on the same images when the container gate is available.
- [ ] **Live check.** `run.sh run --module 05 --profile smoke` and `--profile full` run inside the Insula. Record:
  - ATE;
  - rotation error;
  - initial and final reprojection RMSE;
  - the number of registered views;
  - runtime;
  - the COLMAP comparison, if it can run.
- [ ] **Gates:** `//:repo_gate` and `//parallax/...`.
