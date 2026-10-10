# 08: TSDF fusion and marching cubes

**What to build:** Depth maps fused into a voxel TSDF by our code, and a mesh extracted by our marching cubes, scored against the ground-truth surface.

**Blocked by:** 07

**Status:** ready-for-agent

- [ ] **Code.** `fusion/tsdf.py`, a volumetric integrator with truncation and weights, and `fusion/marching_cubes.py`.
- [ ] **Tests.**
  - Fusing the ground-truth depth of the orbit scene gives a mesh within a stated Chamfer distance and F-score at τ.
  - A sphere SDF meshes to the analytic radius within the voxel tolerance.
- [ ] **Live check.** Fuse the ground-truth depth and the depth from ticket 07, and record Chamfer distance, accuracy, completeness, F-score at τ and runtime.
- [ ] **Gates:** `//:repo_gate` and `//parallax/...`.
