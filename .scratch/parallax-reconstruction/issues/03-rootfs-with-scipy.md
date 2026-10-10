# 03: Parallax rootfs carries pinned scipy

**What to build:** A new Parallax Bazel rootfs whose lock includes a hash-pinned scipy that is compatible with numpy 1.26.4. It is selected by the runtime-roots registry after its lock passes `load_runtime_lock`.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] **Lock.** `parallax/insulas/bazel-requirements.lock` adds scipy (and nothing else) with hashes. The Dockerfile smoke check asserts the scipy version.
- [x] **Build.** The rootfs is built by the existing `parallax/insulas/build-bazel-rootfs.sh` under a new name, such as `rootfs-v3`. `rootfs-v2` and its lock are left untouched.
- [x] `autonomy/insula/runtime_roots.py` points `CURRENT_CURRICULUM_ROOTFS_NAME` at the new rootfs only after `load_runtime_lock` accepts it.
- [x] **Gates:** `//:repo_gate` and `//parallax/...` pass on the new rootfs. Record the lock digests.
- [x] **Note:** container builds run under the coordinator, not a sandboxed worker.

## Comments

### 2026-10-10 coordinator

- **Lock.** `bazel-requirements.in` gained `scipy==1.14.1`. The lock was regenerated with `uv pip compile ... --python-version 3.10 --python-platform x86_64-manylinux_2_28 --generate-hashes`, and the only change is the added scipy.
- **Recipe.** The Dockerfile smoke check and `validate_rootfs` both assert scipy 1.14.1, and the lock records `scipy_version`.
- **Build script fix.** `build-bazel-rootfs.sh` still imported `pipeline.runtime_identity`, a path that no longer exists after the semantic-layout refactor, so it failed before building. It now imports `insula.runtime_identity`. Its defaults now build `rootfs-v3` from previous `rootfs-v2`.
- **Built** by the coordinator with `parallax/insulas/build-bazel-rootfs.sh`:
  - rootfs `~/.cache/waystone/3d-pathway/insula/rootfs-v3`;
  - image `sureal-3d-pathway-cpu:bazel-9.2.0-rootfs-v3`;
  - lock sha256 `8df13a37ef3adadab73175e3652d9fb8bb20d7c9a481d845cdc86e182a0d7e33`, recipe-digest form, accepted by `load_runtime_lock`.

  `rootfs-v2` and its lock are untouched.
- **Checked inside v3:** `import numpy, scipy, scipy.sparse.linalg, scipy.spatial` reports numpy 1.26.4 and scipy 1.14.1.
- **Registry.** `CURRENT_CURRICULUM_ROOTFS_NAME` is now `rootfs-v3`. `bazel_wrapper_test` uses the constant instead of the literal `rootfs-v2`.
- **Gates:** `//:repo_gate` 17/17, `//parallax/...` 17/17 (run on v3), `//autonomy/...` 189/189.
