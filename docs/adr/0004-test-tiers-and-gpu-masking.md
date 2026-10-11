---
status: accepted
---

# Test tiers are explicit Bazel tags, and requested GPU tests require CUDA

Sureal test tiers are selected by Bazel tags and, where helpful, by filename
suffixes. The default `./bazelw test` tier excludes tests tagged
`requires_gpu`, `requires_live_gate`, and `known_failure`. The CUDA tier is
requested with `./bazelw test --config=cuda ...`; the wrapper selects the GPU
rootfs, includes only tests tagged `requires_gpu` while still excluding
`requires_live_gate` and `known_failure`, and sets `SUREAL_REQUIRE_GPU=1` in
the Bazel test environment. A test in the requested GPU tier must fail with a
clear error when no CUDA device is visible.

The standard tags are:

- `requires_gpu`: the test requires the GPU rootfs and exactly one visible CUDA
  device. It is run by the CUDA gate, for example
  `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda ...`, when GPU 1 is free.
- `requires_live_gate`: the test launches nested live Insula work or depends on
  live host state. It is excluded from default and CUDA sweeps unless a command
  explicitly asks for the live tier.
- `known_failure`: the test records unfinished or intentionally failing
  behavior. It is excluded from landing gates until the owning ticket removes
  the tag.

The standard suffixes are:

- `_live_test.py`: a colocated Python test whose body touches a live runtime,
  nested Insula launch, real external asset, or other host state outside pure
  unit fixtures. These tests carry a live tag such as `requires_live_gate` or
  `requires_gpu` when they are not part of the default sweep.
- `_host_test.py`: a colocated Python test for host-facing wrappers or
  repository boundary behavior. It may inspect host metadata or wrapper plans,
  but it must still run through `./bazelw` unless a documented static hook says
  otherwise.

The landing gates are:

- Static repository gate:
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate`.
- CPU autonomy sweep:
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`.
- Parallax sweep:
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`.
- CUDA autonomy sweep, only when GPU 1 is actually free:
  `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`.

## Consequences

- Default CPU runs stay portable: `SUREAL_REQUIRE_GPU` is unset, so tests may
  import GPU-aware libraries without requiring a device unless their own target
  asks for the CUDA tier.
- CUDA runs are fail-not-skip. When `SUREAL_REQUIRE_GPU=1`, GPU tests call the
  shared visibility guard before CUDA work and fail with a message naming the
  missing device count if CUDA has been masked.
- Tags and suffixes are documentation-backed API. New tests should use the
  tag/suffix pair that describes the resources they really require instead of
  skipping silently inside the test body.
