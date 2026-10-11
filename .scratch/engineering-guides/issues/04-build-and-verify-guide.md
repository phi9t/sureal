# 04: Build-and-verify guide

**What to build:** A new contributor can read one guide, `docs/guides/build-and-verify.md`, and understand how
a Sureal change travels from an edit to a passing gate and on to retained evidence. The guide covers where
each digest, lock and receipt comes from.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

Source: `~/workspace/milano/docs/guides/build-and-qualify.md` for the shape: flows with mermaid diagrams, the
launch chain, the evidence layout, the digest chain and boundary debugging. Every fact comes from the Sureal
tree:
- `bazelw`, `.bazelrc` and `MODULE.bazel`;
- ADRs 0002 and 0004;
- `autonomy/docs/adr/0001`–`0003`;
- `docs/launch-plans/`, `docs/blob-store/` and `autonomy/retention/`;
- the GHCR rootfs persistence in `.scratch/rootfs-rebuild/`.

- [ ] **Flows.** Edit to gate:
  - `./bazelw` picks the CPU, GPU or Parallax rootfs from the target pattern and config;
  - the Insula entry;
  - the repo, autonomy, CUDA and Parallax gates, with their tags and tiers.

  Also cover:
  - rootfs build, lock and GHCR persistence;
  - live run to retained evidence: launch plans checked against runtime locks, source snapshots and pins,
    the blob store, the retention planner (dry run first), and the publisher release path.
- [ ] **Diagrams.** At least one mermaid diagram per flow. Each node names a real file or command.
- [ ] **Boundary debugging.** A section on common failures and where to look: wrong rootfs selected, GPU
  masked under `--config=cuda`, a stale source pin, a ShellCheck, Ruff or clang-format scope surprise.
- [ ] **Accuracy.** No host paths: use `~`-relative or repo-relative paths. Commands match `AGENTS.md`. Each path
  named exists in the tree.
- [ ] **Links.** `AGENTS.md` links the guide from its Commands section.
- [ ] **Gates.** `//:repo_gate` passes through `./bazelw`.
