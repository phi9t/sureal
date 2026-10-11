# 13: `parallax/pipeline/` splits by concept

**What to build:** `parallax/` has no generic `pipeline/` directory, the kind ADR 0001 dissolved in `autonomy/`.
The classical reconstruction chain lives under a concept name. The lab-running harness lives under another.

**Blocked by:** 07

**Status:** ready-for-agent

Decisions (coordinator, 2026-10-11):
- `classical_chain*` and `two_view_orbit*` move to `parallax/reconstruction/`. They are the end-to-end chain from
  images to camera poses to sparse to dense to mesh, composing `features`, `geometry`, `sfm`, `stereo` and `fusion`.
- The lab harness moves to `parallax/labs/`: `runner`, `cli`, `contracts`, `audit`, `reporting`, `fetch`, and
  the e2e, foundation and review-fix tests. `parallax/run.sh` keeps working.
- The worker may fold `curriculum/` into `labs/` if they are the same concept. Record the reasoning in the
  commit.
- Imports follow the `parallax/` import root, and no shims are left behind.

- [ ] `git mv`, then references are fixed: BUILD, `run.sh`, docs, `parallax/README.md` and the CONTEXT files.
- [ ] Live first: `./bazelw test //:repo_gate` and `//parallax/...`, including `classical_chain_full`. The metrics
  in `.scratch/parallax-reconstruction/issues/09-*.md` must be unchanged: F ≥ 0.85, Chamfer ≤ 0.08 m.
