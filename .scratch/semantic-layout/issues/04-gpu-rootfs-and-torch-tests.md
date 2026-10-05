# 04: Torch tests run under Bazel in the GPU rootfs

**What to build:** A contributor opts in to the GPU configuration and the 26 torch-dependent test modules run under Bazel inside a new version of the GPU rootfs, without staging a live gate. The default run still works on the CPU rootfs alone.

**Blocked by:** 03 (Every perception CPU test runs under Bazel, in place)

**Status:** ready-for-agent

- [x] A new version of the GPU rootfs carries Bazel 9.2 with the same packages as the current GPU image; the current image is untouched
- [x] The wrapper selects the GPU rootfs when the GPU configuration is requested, and projects the host driver libraries as the existing GPU gates do
- [x] The 26 torch modules run under the GPU configuration and their results are recorded
- [x] The default configuration excludes every GPU-tagged target
- [x] CUDA use is opt-in; torch tests that need only the CPU run without a visible GPU
