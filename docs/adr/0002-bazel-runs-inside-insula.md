---
status: accepted
---

# Bazel runs inside Insula and takes every dependency from the rootfs

Bazel 9.2 is the build and test graph for `autonomy/` and `parallax/`, and it always runs inside an Insula rootfs through one repo-level wrapper script, never on the host. Bazel is baked into the rootfs, built as the next rootfs version; earlier images stay on disk because past receipts record their digests. Every dependency, package and tool, including the Python interpreter, third-party Python packages and torch, comes from the rootfs. The network stays available during builds.

This deliberately departs from the [layout standard](../repo-structure.md), which has Bazel resolve Python packages from a uv lock through `rules_python`. Here uv only authors the hash-pinned locks the rootfs is built from. We chose this so the build and the live gates cannot disagree about a wheel, and because torch has to come from the rootfs in any case, as it does in every sibling repository that runs Bazel under Insula.

## Considered options

- **Bazel on the host, Insula only for live gates.** Rejected: Insula is the top-level environment in this workspace, and a host build would be a second, unpinned runtime.
- **Bind-mount a checksum-verified Bazel into the existing images.** Rejected in favour of baking it in, so that "everything comes from the rootfs" has no exception.
- **A sealed network with a separate dependency-capture step.** Rejected as unnecessary for now.

## Consequences

- A new rootfs version means new image digests. Anything that compares a runtime lock against the old digest must be re-admitted before it runs on the new image.
- Bazel targets that need packages absent from the CPU rootfs (torch, CUDA) run only in the GPU rootfs and are opt-in through `--config=cuda`.
