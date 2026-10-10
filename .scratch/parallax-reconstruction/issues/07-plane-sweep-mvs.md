# 07: Plane-sweep multi-view stereo depth maps

**What to build:** Per-view depth maps are computed by our plane-sweep MVS from ground-truth poses on the orbit scene, and scored against ground-truth depth.

**Blocked by:** 03, 04

**Status:** ready-for-agent

- [ ] **Code.**
  - `stereo/plane_sweep.py`: fronto-parallel sweep over depth hypotheses with neighbour-view selection.
  - `stereo/cost.py`: ZNCC, plus census or an equivalent.
  - `stereo/depth_filter.py`: cross-view geometric consistency.
- [ ] **Tests.** A synthetic fronto-parallel plane recovers its depth exactly up to sampling. Depth on the orbit scene beats a stated AbsRel threshold on textured pixels.
- [ ] **Live check.** Run inside the Insula on the smoke and full profiles. Record:
  - AbsRel;
  - δ<1.25;
  - the fraction of valid pixels;
  - runtime.
- [ ] **Gates:** `//:repo_gate` and `//parallax/...`.
