# 05: The curriculum's tests run under Bazel, in place

**What to build:** A contributor runs one wrapper command and the 3D reconstruction curriculum's CPU numerical contract passes as Bazel targets, with the tree where it is now. This ticket decides whether the curriculum can share the perception CPU rootfs or needs a rootfs of its own.

**Blocked by:** 02 (One wrapper command runs Bazel inside Insula)

**Status:** ready-for-agent

- [x] The curriculum's 17 test modules are Bazel test targets
- [x] The CPU numerical contract passes through the wrapper, or the ticket records exactly which tests fail under Python 3.12 and the newer NumPy
- [x] If it cannot share the perception rootfs, a curriculum rootfs with Bazel 9.2 is built from a hash-pinned lock and the wrapper selects it for curriculum targets
- [x] Tests that require a real container gate stay opt-in and are excluded by default
- [x] The existing CI job for the curriculum still passes unchanged
