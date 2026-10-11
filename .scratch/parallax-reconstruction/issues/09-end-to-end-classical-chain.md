# 09: End-to-end images to mesh; module 06 goes real

**What to build:** Images to SfM poses to plane-sweep depth to TSDF mesh, using only our code. Curriculum modules 06 and 04 (fusion) report measured results, with the COLMAP MVS baseline compared in the same report.

**Blocked by:** 06, 08

**Status:** ready-for-agent

- [ ] **Pipeline.** One entry composes `sfm/`, `stereo/` and `fusion/`. Its output is aligned to ground truth by Sim(3) before scoring.
- [ ] **Module status.** Module 06 becomes `real+baseline`. Module 04's fusion metrics become real, and so does its registration part via `geometry/align.py`. The synthetic leftovers in those labs are removed.
- [ ] **Live check.** `run.sh run --module 06` with smoke and full profiles, and `run.sh all --profile smoke`. Record the surface metrics for ours and for COLMAP MVS, if the container gate is available.
- [ ] **Fusion follow-ups from ticket 08.** Either rename `fusion/marching_cubes.py` to marching tetrahedra or implement case-table marching cubes. Weld vertices into an indexed mesh, and use it for export and Chamfer sampling.
- [ ] Shims left by ticket 01 that no longer have callers are deleted.
- [ ] **Gates:** `//:repo_gate` and `//parallax/...`.
