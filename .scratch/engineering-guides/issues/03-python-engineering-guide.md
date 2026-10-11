# 03: Python engineering guide

**What to build:** A contributor writing Sureal Python follows `docs/guides/python-engineering.md`. It holds the
rules Milano keeps in its AGENTS.md and ADRs (import root, colocated tests, test tiers, policy in Python),
alongside Sureal's existing Google-style deltas.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

Source:
- `~/workspace/milano/AGENTS.md`: the test tiers, Python imports and engineering-rules sections;
- `~/workspace/milano/docs/adr/0002-tests-beside-their-source.md`;
- Sureal's `docs/guides/python-style.md`, `docs/adr/0004-test-tiers-and-gpu-masking.md`, and the Python
  import rule section of `AGENTS.md`.

- [ ] **Rename.** `docs/guides/python-style.md` becomes `docs/guides/python-engineering.md` (`git mv`). It gains:
  - functions are small, about 40 lines as a target, matching the C++ guide;
  - prefer return values over mutation, and accept dependencies rather than constructing them;
  - one owner per policy;
  - tests sit beside their source as `foo_test.py` with a Bazel `py_test`, and test external behaviour;
  - test tiers and tags (`requires_gpu`, `requires_live_gate`, `known_failure`), linked to ADR 0004;
  - what a live command is, versus library code;
  - numeric code: units in names, explicit tolerances, and ground truth used only for scoring, never in
    estimation;
  - receipts and evidence are data with recorded field names.
- [ ] **Accuracy.** Every tool claim matches the tree today: Ruff version and rules, format batch directories,
  the import checker, and the pinned-source exclusions.
- [ ] **Deltas.** The guide records Milano rules that Sureal does not adopt, with the reason: uv as the dependency
  authority, and pytest `conftest.py` tier gating instead of Bazel tags.
- [ ] **References.** `AGENTS.md` and any active reference name the new path. No `python-style.md` remains
  outside `.scratch/` history.
- [ ] **Gates.** `//:repo_gate` passes through `./bazelw`.
