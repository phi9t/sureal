# 08: The Insula and rootfs tooling moves into `harness/insula/`

**What to build:** The repo-wide execution boundary lives in `harness/insula/`, beside the lints:
- the `./bazelw` launcher;
- launch plans and runtime locks;
- runtime roots and identity;
- rootfs recipes, builds and GHCR persistence;
- GPU visibility and leases.

It is no longer inside `autonomy/`, even though it serves Parallax too.

**Blocked by:** 06, 07

**Status:** ready-for-agent

Decisions (coordinator, 2026-10-11):
- `harness/` is an import root (ADR 0005 from ticket 06), so the package keeps the name `insula`. Every existing
  `from insula.launch_plan import ...` in `autonomy/` keeps working unchanged once autonomy targets depend on the
  harness library. Bazel deps and paths change; import lines do not.
- Repo-wide pieces move:
  - `bazel_launcher`;
  - `launch_plan`, `runtime_roots`, `runtime_identity`, `entry`, `live_gate`;
  - `gpu_visibility`, `gpu_probe`, `staging_lease`;
  - `rootfs_oci`;
  - the CPU and GPU rootfs Dockerfiles, build scripts and requirement locks.

  Parallax's Bazel-rootfs recipe joins them as `harness/insula/parallax-bazel-rootfs/` or similar. Parallax
  method images (`parallax/insulas/<method>/`) stay with Parallax.
- Autonomy-only GPU acceptance procedures (`m0_*`, `verify_m0`, `verify_gpu_*`, `validate_gpu_probe`) stay in
  `autonomy/insula/` only if they are specific to autonomy science. Otherwise they move. Decide per file and
  record the decision in the README.
- `rootfs_oci` stops importing `evidence.source_snapshot` for a sha256 helper. It uses `hashlib` locally, so
  harness does not depend on autonomy.
- **Rootfs identity check.** Moving a Dockerfile or lock must not silently change a rootfs key. If the key
  hashes paths, document the new keys. Confirm the GHCR digests recorded in `.scratch/rootfs-rebuild/` still
  resolve, or record the re-push as a follow-up. Never delete or overwrite a cached rootfs.
- `bazelw` execs the launcher from its new home.

- [ ] Moves are done with `git mv`, then references are fixed: BUILD deps, `bazelw`, docs, AGENTS.md, the
  build-and-verify guide and the ADRs (consequence notes only).
- [ ] `harness/insula/README.md` in the subpackage README shape.
- [ ] Live first: `./bazelw test //:repo_gate`, `//autonomy/...`, `//parallax/...`, and CUDA on GPU 1 when it is
  free (no compute process, memory.used < 1024 MiB). All rootfs selections still resolve to cached images, with
  no rebuild.
