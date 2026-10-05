# 28: The perception rootfs carries the tools its tests need

**What to build:** A contributor runs the default perception test set and the tests that were excluded only because the rootfs lacks a tool now run and pass. A new version of the perception CPU rootfs carries git, curl, pytest and a C++ compiler, and the wrapper keeps its Bazel caches out of the directory that tests treat as their output mount. This closes follow-ups recorded while reviewing tickets 02, 03, 04 and 07.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] A new version of the perception CPU rootfs is built with git, curl, pytest (hash-pinned through a requirement lock) and a C++ compiler with binutils; Bazel 9.2 and every Python package of the current version are unchanged; the current and earlier rootfs versions and their locks are untouched on disk
- [ ] The wrapper selects the new version for perception targets, and its unit tests cover the selection
- [ ] The placeholder C++ toolchain is removed and Bazel resolves the rootfs compiler; a trivial C++ test target builds and passes to prove it
- [ ] The modules tagged `requires_host_tools` only for git or curl, and the two tagged `requires_pytest`, lose those tags and pass in the default run; the pytest modules run under real pytest, not an emulation; any module that still cannot run keeps a tag with its actual error recorded
- [ ] The wrapper mounts its Bazel caches at a dedicated path that is not `/outputs`, so a test that inspects `/outputs` never sees Bazel writing there; `cohort/test_sustained_worker_guard` passes ten consecutive runs under `--config=cuda`
- [ ] The default run, the `--config=cuda` run and `//parallax/...` all pass, with counts recorded against the previous counts (139 default, 24 GPU, 17 curriculum)
- [ ] The GPU rootfs is left as it is unless a GPU-tagged test needs one of these tools; if so, say which and stop with needs-info
