# 04: Build-and-verify guide

**What to build:** A new contributor can read one guide, `docs/guides/build-and-verify.md`, and understand how
a Sureal change travels from an edit to a passing gate and on to retained evidence. The guide covers where
each digest, lock and receipt comes from.

**Blocked by:** None (can start immediately)

**Status:** done

Source: `~/workspace/milano/docs/guides/build-and-qualify.md` for the shape: flows with mermaid diagrams, the
launch chain, the evidence layout, the digest chain and boundary debugging. Every fact comes from the Sureal
tree:
- `bazelw`, `.bazelrc` and `MODULE.bazel`;
- ADRs 0002 and 0004;
- `autonomy/docs/adr/0001`–`0003`;
- `docs/launch-plans/`, `docs/blob-store/` and `autonomy/retention/`;
- the GHCR rootfs persistence in `.scratch/rootfs-rebuild/`.

- [x] **Flows.** Edit to gate:
  - `./bazelw` picks the CPU, GPU or Parallax rootfs from the target pattern and config;
  - the Insula entry;
  - the repo, autonomy, CUDA and Parallax gates, with their tags and tiers.

  Also cover:
  - rootfs build, lock and GHCR persistence;
  - live run to retained evidence: launch plans checked against runtime locks, source snapshots and pins,
    the blob store, the retention planner (dry run first), and the publisher release path.
- [x] **Diagrams.** At least one mermaid diagram per flow. Each node names a real file or command.
- [x] **Boundary debugging.** A section on common failures and where to look: wrong rootfs selected, GPU
  masked under `--config=cuda`, a stale source pin, a ShellCheck, Ruff or clang-format scope surprise.
- [x] **Accuracy.** No host paths: use `~`-relative or repo-relative paths. Commands match `AGENTS.md`. Each path
  named exists in the tree.
- [x] **Links.** `AGENTS.md` links the guide from its Commands section.
- [x] **Gates.** `//:repo_gate` passes through `./bazelw`.

## Comments

2026-10-10 worker/engi04-build-and-verify-guid:

- Live check before edits:
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate`.
  Result: passed through Insula, 23/23 tests passed. Log:
  `~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/engi04-build-and-verify-guid-20261011T205627Z/tmp/repo-gate-live.b9oh4Q/repo_gate.log`.
  Log sha256: `9c5877514ff819083d86a1e73a0a3527d685abccc4532dabcc9864d8d05540ab`.
- Source-pin check before edits:
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:pinned_sources_test`.
  Result: passed through Insula, 1/1 test passed. Log:
  `~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/engi04-build-and-verify-guid-20261011T205627Z/tmp/pinned-sources.0CLMeQ/pinned_sources_test.log`.
  Log sha256: `0982b9d163b2b75a32fadaa952a7fed1ea10f92cc55b331fd850113df50f901c`.
- Implemented `docs/guides/build-and-verify.md` with edit-to-gate, rootfs build/lock/persistence and
  live-run-to-retained-evidence flows. Each flow has a Mermaid diagram whose nodes name real files or
  commands. The guide covers wrapper/rootfs selection, Insula entry, repo/Autonomy/CUDA/Parallax gates,
  tags and tiers, rootfs lock checks, GHCR persistence, launch plans, source snapshots, blob-store
  receipts, retention dry-run planning and publisher release receipts.
- Added the Commands-section link from `AGENTS.md` to `docs/guides/build-and-verify.md`.
- Accuracy checks: searched the committed guide and `AGENTS.md` for absolute host paths; no non-`~`
  host path was introduced. Verified each repository path named as a file in the guide exists in this
  checkout.
- Post-edit gate:
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate`.
  Result: passed through Insula, 23/23 tests passed. Log:
  `~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/engi04-build-and-verify-guid-20261011T205627Z/tmp/repo-gate-postedit.SPsEXy/repo_gate.log`.
  Log sha256: `99ac0bf30cb94ad36c1b3ff88cddaa43944d2a5fdf71bd5fd7d7a19420242865`.
- Resumed final repo gate after WIP commit `d02097c`:
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate`.
  Result: passed through Insula, 23/23 tests passed. Log:
  `~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/engi04-build-and-verify-guid-20261011T205627Z/tmp/resume-repo-gate.EqUjbW/repo_gate.log`.
  Log sha256: `82aefe5330ace1d4264bb81fb4964085d200e3c44d7bcdd74590b07e2e9e2c94`.
- Resumed final Autonomy CPU gate:
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`.
  Result: passed through Insula, 191/191 tests passed. Log:
  `~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/engi04-build-and-verify-guid-20261011T205627Z/tmp/resume-autonomy.5OI9LP/autonomy.log`.
  Log sha256: `b8cf642359b8d69333ded86d1fae17d1dd46509681ef6b9c59c2fab156b5b107`.
- Resumed final Parallax gate:
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`.
  Result: passed through Insula, 32/32 tests passed. Log:
  `~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/engi04-build-and-verify-guid-20261011T205627Z/tmp/resume-parallax.wNqL4D/parallax.log`.
  Log sha256: `7c4d9246193f2f7ffcc808847a25b70d6ab5ea5aab736df08a65bed4655bcb7f`.
- CUDA gate intentionally skipped per task instruction because this sandbox has no GPU devices; the
  coordinator runs CUDA.
