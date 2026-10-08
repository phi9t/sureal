# 01: Oriented-box module in geometry, with a parity harness

**What to build:** Any concept can ask the geometry concept which points lie inside an oriented box, wrap a heading into [-π, π), get a box's BEV corners, and compute nearest or enclosing BEV rectangles and their axis-aligned IoU, through one small numpy-only module. A test-only parity harness lets later tickets prove a copy and the module agree exactly before the copy is removed. See `.scratch/box-geometry/spec.md`.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The module is its own Bazel library in the geometry concept, depends only on numpy, and is visible to detection, segmentation, evaluation and inspection; the existing geometry library and its dependencies are unchanged
- [ ] Membership is inclusive on all faces with no tolerance and uses the same cos/sin projection and operation order as the existing copies; non-finite values and non-positive dimensions are rejected
- [ ] Heading wrap uses the producers' exact expression and has documented results at ±π; BEV corners have a documented order; IoU returns zero for an empty union
- [ ] Module tests cover faces, edges, corners, degenerate input, wrap at ±π and large multiples of 2π, corner order and IoU symmetry and identity, and check membership against an independently written inverse-homogeneous-transform reference away from exact boundaries
- [ ] A test-only parity harness runs an old implementation and the module over a fixed random seed plus a fixed edge-case set and asserts exact equality of outputs and identical rejection of invalid inputs; it is demonstrated on one existing copy (for example the viewer's point count) without migrating it
- [ ] Default CPU suite, `--config=cuda` suite (GPU 1 only) and `//parallax/...` pass with counts recorded
