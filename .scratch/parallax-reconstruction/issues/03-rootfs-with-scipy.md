# 03: Parallax rootfs carries pinned scipy

**What to build:** A new Parallax Bazel rootfs whose lock includes a hash-pinned scipy that is compatible with numpy 1.26.4. It is selected by the runtime-roots registry after its lock passes `load_runtime_lock`.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] **Lock.** `parallax/insulas/bazel-requirements.lock` adds scipy (and nothing else) with hashes. The Dockerfile smoke check asserts the scipy version.
- [ ] **Build.** The rootfs is built by the existing `parallax/insulas/build-bazel-rootfs.sh` under a new name, such as `rootfs-v3`. `rootfs-v2` and its lock are left untouched.
- [ ] `autonomy/insula/runtime_roots.py` points `CURRENT_CURRICULUM_ROOTFS_NAME` at the new rootfs only after `load_runtime_lock` accepts it.
- [ ] **Gates:** `//:repo_gate` and `//parallax/...` pass on the new rootfs. Record the lock digests.
- [ ] **Note:** container builds run under the coordinator, not a sandboxed worker.
