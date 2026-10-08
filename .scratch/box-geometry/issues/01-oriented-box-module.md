# 01: Oriented-box module in geometry, with a parity harness

**What to build:** Any concept can ask the geometry concept which points lie inside an oriented box, wrap a heading into [-π, π), get a box's BEV corners, and compute nearest or enclosing BEV rectangles and their axis-aligned IoU, through one small numpy-only module. A test-only parity harness lets later tickets prove a copy and the module agree exactly before the copy is removed. See `.scratch/box-geometry/spec.md`.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] The module is its own Bazel library in the geometry concept, depends only on numpy, and is visible to detection, segmentation, evaluation and inspection; the existing geometry library and its dependencies are unchanged
- [x] Membership is inclusive on all faces with no tolerance and uses the same cos/sin projection and operation order as the existing copies; non-finite values and non-positive dimensions are rejected
- [x] Heading wrap uses the producers' exact expression and has documented results at ±π; BEV corners have a documented order; IoU returns zero for an empty union
- [x] Module tests cover faces, edges, corners, degenerate input, wrap at ±π and large multiples of 2π, corner order and IoU symmetry and identity, and check membership against an independently written inverse-homogeneous-transform reference away from exact boundaries
- [x] A test-only parity harness runs an old implementation and the module over a fixed random seed plus a fixed edge-case set and asserts exact equality of outputs and identical rejection of invalid inputs; it is demonstrated on one existing copy (for example the viewer's point count) without migrating it
- [x] Default CPU suite, `--config=cuda` suite (GPU 1 only) and `//parallax/...` pass with counts recorded

## Comments

Done: added `//autonomy/geometry:oriented_box` as a numpy-only geometry library plus module tests for inclusive membership, validation, heading wrap, BEV corners, BEV rectangles and IoU. Added `//autonomy/geometry:oriented_box_parity_harness` and demonstrated it against the existing `segmentation.foreground_support` copy without migrating that copy. Gates: `//autonomy/...` CPU 157/157 pass; `//parallax/...` 17/17 pass; GPU 1 was free and `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda //autonomy/...` passed 28/28.

Review fix: strengthened `oriented_box_parity_harness` with shared near-surface parity cases for faces, edges and corners, including exact local-boundary points, one-ulp inward/outward nudges, exact headings `-pi`, `pi`, `+/-pi/2` and large `2pi` multiples. Added `assert_membership_parity` using the same cases and demonstrated it on `segmentation.foreground_support` without migrating the copy. Fresh gates: focused harness/module/parity targets 3/3 pass; `//autonomy/...` CPU 158/158 pass; `//parallax/...` 17/17 pass; GPU 1 was free and `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda //autonomy/...` passed 28/28.
