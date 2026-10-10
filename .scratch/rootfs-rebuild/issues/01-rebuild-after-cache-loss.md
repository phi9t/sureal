# 01: Rebuild active rootfs after local Waystone cache loss

**What to build:** Restore the active Sureal root filesystems deleted from
`~/.cache/waystone`, then rerun the CPU, GPU, Parallax, live-set and retained
sweep gates against the rebuilt locks.

**Blocked by:** Current worker access profile forbids container builds, while the active rootfs rebuild recipes are Docker/container build recipes.

**Status:** ready-for-human

- [x] Inventory the active rootfs names, recipes, lock forms and dependents before building.
- [x] Build and lock the CPU rootfs.
- [x] Build and lock the GPU rootfs.
- [x] Build and lock the metrics, motion metrics and motion CLI image-form rootfs.
- [x] Build and lock the Parallax curriculum rootfs.
- [x] Update active rootfs pins only after the rebuilt locks pass `insula.launch_plan.load_runtime_lock`.
- [ ] Run the CPU, GPU, repo, Parallax, live-set and retained-sweep gates. (CPU, GPU, repo and Parallax pass. Live set: 4/5 pass; the foundation replay needs lost run data. Retained sweep: 2101 passed, 0 failed, with the rest skipped for absent host data. See ticket 02.)
- [x] Restore or report missing Parallax data. (Reported in ticket 02.)

## Comments

2026-10-10 worker/rootfs-rebuild: Stopped before phase B. The user approved
rebuilding Sureal's Insula root filesystems, but this worker run also says
"Container builds are not allowed." The active rebuild recipes require Docker:

- CPU `autonomy/insula/build_cpu_rootfs.sh` invokes `docker build`,
  `docker image inspect`, `docker create` and `docker export`.
- GPU `autonomy/insula/build_gpu_bazel_rootfs_v6.sh` verifies the local
  `surflo-insula:cuda13.2.1-locked` image and then invokes `docker build`,
  `docker create` and `docker export`.
- Parallax `parallax/insulas/build-bazel-rootfs.sh` invokes `docker build`,
  `docker create` and `docker export`.
- The image-form metrics/motion roots are defined by Dockerfiles checked by
  `insula.launch_plan.load_runtime_lock`; no non-Docker active builder was
  found for those roots.

Live cache evidence:

- `~/.cache/waystone` is missing.
- `/data02` has 422G free, so the stop is not the 200G disk-floor rule.
- `./bazelw --emit-plan test //:repo_gate` exits before Bazel launch with
  `runtime lock missing:
  ~/.cache/waystone/waymo-perception/insula/rootfs-v5-t29-20261008T230657Z.lock.json`.

Inventory was recorded under
`~/devx/tmp/sureal-refactor-20261007/rootfs-rebuild/rebuild-20261010T080000Z/inventory.md`.
No rootfs, runtime lock, retained receipt, frozen code, active pin, cache or
HDFS state was modified.

Active inventory summary:

| Rootfs | Current name | Lock form | Recipe evidence | Dependents |
| --- | --- | --- | --- | --- |
| CPU Bazel | `rootfs-v5-t29-20261008T230657Z` | recipe-digest | `autonomy/insula/build_cpu_rootfs.sh`, `autonomy/insula/Dockerfile`, `autonomy/requirements-tracer.lock`, `autonomy/insula/cpu-test-tools-requirements.lock`, base `python:3.12-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e` | `./bazelw` default autonomy/repo gates, nested live gates, M0, geometry/camera/dataset/segmentation/inspection/resources/retention, training CPU stages |
| GPU Bazel | `gpu-rootfs-v7` | recipe-digest | `autonomy/insula/build_gpu_bazel_rootfs_v6.sh`, `autonomy/insula/Dockerfile.gpu-bazel-rootfs-v6`, `autonomy/insula/gpu-requirements.lock`, local base `surflo-insula:cuda13.2.1-locked` expected `sha256:eaf68603ced6f9abb5ee401522a07774183a8412ff3d9de61278f09c0738749d` | `./bazelw --config=cuda`, GPU live/isolation, sustained GPU stages |
| Metrics | `metrics-rootfs` | image | `autonomy/evaluation/Dockerfile`, `autonomy/evaluation/CMakeLists.txt`, base `python:3.12-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e` | detection/segmentation metrics verifiers, `audit-perception-gate`, training metrics stages |
| Motion metrics | `motion-metrics-rootfs` | image | `autonomy/motion/ingestion/native_metric.Dockerfile`, `autonomy/motion/CMakeLists.txt`, parent image `sha256:c0018cf57e482c6a9e6623ea32f29c6039f22f5dafb0f3311bad6d411a7bb135` | `autonomy/motion/verify_motion_native.py` |
| Motion CLI | `motion-cli-rootfs-v2` | image | `autonomy/motion/cli/motion_cli.Dockerfile`, `autonomy/motion/cli/CMakeLists.txt`, `autonomy/motion/cli/motion_metrics_main.cc`, parent image `sha256:84fb83dd874d0cfff8e9ee3df0759d89f9ad85e9538c0071c9eb606a13d8c233` | `verify_motion_cli.py`, `verify_motion_cli_expanded.py`, `replay_motion_foundation.py`, motion CLI live gates |
| Parallax curriculum | `rootfs-v2` | recipe-digest | `parallax/insulas/build-bazel-rootfs.sh`, `parallax/insulas/bazel-rootfs.Dockerfile`, `parallax/insulas/bazel-requirements.lock`, base `python:3.10-slim-bookworm@sha256:8264197061a1abf08ccb2421281a072f60a9f18e0d15d618f5a4cb956f1e8c22` | `./bazelw test //parallax/...` |

Decision: do not update `autonomy/insula/runtime_roots.py` in this worker.
There is no rebuilt lock to point at, and changing active pins before
`load_runtime_lock` verifies the rebuilt content would only move the failure.

Next compliant run needs a worker profile that permits the repository's Docker
build recipes, or explicit human direction to add a new non-container rebuild
path. The latter would be a recipe change and should not be treated as "use the
repo's own build scripts and recipes unchanged."

### 2026-10-10 coordinator note

The user authorised container builds and then stopped the rebuild before anything was built. No rootfs, lock or cache file was written, and `runtime_roots.py` is unchanged.

The Docker images behind the lost rootfs still exist locally:
- `sureal-waymo-cpu:bazel-9.2.0-rootfs-v5-t29-20261008T230657Z`;
- `sureal-waymo-gpu:bazel-9.2.0-rootfs-v7`.

Re-exporting from them may restore the CPU and GPU rootfs without a full rebuild. Their content and recipe digests must still be checked against the retained locks before reuse. Left for the user.

### 2026-10-10 coordinator: restored from surviving images

With the user's go-ahead, each active rootfs was re-exported (`docker create` + `docker export`) from its surviving local image. A lock was written only when the exported tree's `rootfs_identity` equalled the `rootfs_sha256` recorded for that rootfs in retained receipts or build logs. All six matched, and each passes `load_runtime_lock`:

| Rootfs | Image | Lock form | Lock sha256 |
| --- | --- | --- | --- |
| CPU `rootfs-v5-t29-20261008T230657Z` | `e5c598e420ba` | recipe-digest | `318e827c…` (matches retained receipts) |
| GPU `gpu-rootfs-v7` | `da548988f6d6` | recipe-digest | `c68df281…` (matches the v7 build record) |
| `metrics-rootfs` | `c0018cf57e48` | image | `bfcf5f5e…` |
| `motion-metrics-rootfs` | `84fb83dd874d` | image | `ede87353…` |
| `motion-cli-rootfs-v2` | `49d07c49427a` (`sureal-waymo-motion-cli:expanded`) | image | `e165e1a1…` |
| Parallax `rootfs-v2` | `69773e28b352` | recipe-digest | `598d5cab…` |

No rebuild was needed and `runtime_roots.py` is unchanged. Gates on `main`: `//autonomy/...` 189/189, `//parallax/...` 17/17, CUDA `//autonomy/...` on GPU 1 30/30, and `//:repo_gate` 17/17 after this ticket's host paths were replaced with `~` paths.

Still open: the live-set and retained-sweep gates, and the Parallax data lost with the cache.
