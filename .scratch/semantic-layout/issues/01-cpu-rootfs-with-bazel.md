# 01: A new version of the CPU rootfs carries Bazel 9.2

**What to build:** A contributor can build a new version of the perception CPU rootfs that contains Bazel 9.2 alongside the same Python packages as the current image. The current image stays on disk untouched, so past receipts still find the digest they recorded.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The new rootfs is built from the existing image definition and the existing hash-pinned requirement lock, plus a checksum-verified Bazel 9.2 binary
- [ ] The rootfs lock records the new image identity and the Bazel version and checksum
- [ ] Inside the new rootfs, `bazel --version` reports 9.2 and the installed Python packages match the current image's package list exactly
- [ ] The previous rootfs directory and its lock are byte-identical before and after the build
- [ ] Every check that compares a runtime lock with the previous rootfs digest is listed in the ticket's comments, for re-admission later
