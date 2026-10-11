# 03: Python engineering guide

**What to build:** A contributor writing Sureal Python follows `docs/guides/python-engineering.md`. It holds the
rules Milano keeps in its AGENTS.md and ADRs (import root, colocated tests, test tiers, policy in Python),
alongside Sureal's existing Google-style deltas.

**Blocked by:** None (can start immediately)

**Status:** done

Source:
- `~/workspace/milano/AGENTS.md`: the test tiers, Python imports and engineering-rules sections;
- `~/workspace/milano/docs/adr/0002-tests-beside-their-source.md`;
- Sureal's `docs/guides/python-style.md`, `docs/adr/0004-test-tiers-and-gpu-masking.md`, and the Python
  import rule section of `AGENTS.md`.

- [x] **Rename.** `docs/guides/python-style.md` becomes `docs/guides/python-engineering.md` (`git mv`). It gains:
  - functions are small, about 40 lines as a target, matching the C++ guide;
  - prefer return values over mutation, and accept dependencies rather than constructing them;
  - one owner per policy;
  - tests sit beside their source as `foo_test.py` with a Bazel `py_test`, and test external behaviour;
  - test tiers and tags (`requires_gpu`, `requires_live_gate`, `known_failure`), linked to ADR 0004;
  - what a live command is, versus library code;
  - numeric code: units in names, explicit tolerances, and ground truth used only for scoring, never in
    estimation;
  - receipts and evidence are data with recorded field names.
- [x] **Accuracy.** Every tool claim matches the tree today: Ruff version and rules, format batch directories,
  the import checker, and the pinned-source exclusions.
- [x] **Deltas.** The guide records Milano rules that Sureal does not adopt, with the reason: uv as the dependency
  authority, and pytest `conftest.py` tier gating instead of Bazel tags.
- [x] **References.** `AGENTS.md` and any active reference name the new path. No `python-style.md` remains
  outside `.scratch/` history.
- [x] **Gates.** `//:repo_gate` passes through `./bazelw`.

## Comments

### 2026-10-10

- Renamed `docs/guides/python-style.md` to `docs/guides/python-engineering.md`
  with `git mv`, expanded it into the Python engineering guide, and updated
  `AGENTS.md` to name the new path.
- Post-WIP verification ran at commit `400c783`.
- Accuracy checked against the current tree: `MODULE.bazel` pins Ruff 0.6.9;
  `pyproject.toml` sets `target-version = "py310"`, line length 120 and
  `select = ["E9", "F821"]`; `scripts/ruff_repo.py` checks active unpinned
  Python under `autonomy/**/*.py`, `parallax/**/*.py`, `scripts/**/*.py` and
  `scripts/*.py`, with the format batch limited to `autonomy/association/` and
  `autonomy/blob_store/`; `scripts/check_imports.py` checks `autonomy/` and
  `parallax/` import roots and skips frozen/source-pinned files; and
  `scripts/pinned_sources.py` excludes retained receipt pins, digest pins,
  current-candidate source declarations and frozen evidence paths.
- Active reference check: `rg --hidden -n "python-style\\.md" . -g '!/.git/**'
  -g '!.scratch/**'` found no matches.
- Live check: `./bazelw test --noexperimental_collect_system_network_usage
  --nocache_test_results --test_output=errors //:repo_gate` passed. Count:
  23/23 tests. Log:
  `~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/engi03-python-engineering-gu-r2-20261011T214456Z/tmp/python-guide-final.AuZQMJ/repo_gate.log`.
  SHA-256: `56615a7c9ef4b0340a4ec31e7051d00d47572be0ea1f119891ab0bbdd88df237`.
- Source-pin check: `./bazelw test --noexperimental_collect_system_network_usage
  --nocache_test_results --test_output=errors //:pinned_sources_test` passed.
  Count: 1/1 tests. Log:
  `~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/engi03-python-engineering-gu-r2-20261011T214456Z/tmp/python-guide-final.AuZQMJ/pinned_sources_test.log`.
  SHA-256: `7ecda0d8f62aac5bd5f6c3f8b412a2219de387776d7d864c48fa7c695a99f980`.
- Final gate: `./bazelw test --noexperimental_collect_system_network_usage
  --nocache_test_results --test_output=errors //autonomy/...` passed. Count:
  191/191 tests. Log:
  `~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/engi03-python-engineering-gu-r2-20261011T214456Z/tmp/python-guide-final.AuZQMJ/autonomy.log`.
  SHA-256: `0a58d49ff76b65be7f9624a46b8c90924f8791f633934da91b610957c578a9e5`.
- Final gate: `./bazelw test --noexperimental_collect_system_network_usage
  --nocache_test_results --test_output=errors //parallax/...` passed. Count:
  32/32 tests. Log:
  `~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/engi03-python-engineering-gu-r2-20261011T214456Z/tmp/python-guide-final.AuZQMJ/parallax.log`.
  SHA-256: `241177f172db0e4621206a551ec380f0ff1f4a9f38558934936b0e2bbb964383`.
- CUDA gate intentionally skipped per task instruction: this sandbox has no GPU
  devices and the coordinator runs CUDA.
