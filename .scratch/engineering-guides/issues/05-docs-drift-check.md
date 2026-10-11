# 05: Docs drift check in the repo gate

**What to build:** `//:repo_gate` fails when a front-door doc names a repo path or module that no longer exists,
or when the README project map misses a top-level source directory. Moves and renames can then no longer leave
the guides stale.

**Blocked by:** 01, 02, 03, 04, 06, 08, 09, 14, 16 (the check must pass on the new guides and the `harness/` layout)

**Status:** ready-for-agent

Source: `~/workspace/milano/harness/workflow/lint/check_docs.py` and `check_docs_test.py`. See also Milano commits
`f7b4907` ("The README is the repo map and AGENTS.md is the rules") and `ed9a7fd`.

- [ ] **Lint.** `harness/lint/check_docs.py` plus `harness/lint/check_docs_test.py` scan:
  - `README.md` and `AGENTS.md`;
  - `CONTEXT-MAP.md` and each `CONTEXT.md`;
  - `docs/guides/*.md`, `docs/adr/*.md`, `autonomy/docs/adr/*.md`;
  - each concept `README.md` under `autonomy/` and `parallax/`.

  They check that repo-relative path references (backticked and markdown links) exist. Exemptions live in one
  commented place:
  - URLs and anchors;
  - placeholders, globs and shell variables;
  - `~`/cache/Insula-internal paths;
  - historical directories such as `docs/ticket*/`, `docs/research/` and `.scratch/`.
- [ ] **Repo map.** The README "Project map" names every top-level source directory: `autonomy/`, `parallax/`, `harness/`,
  `scripts/`, `docs/` and the others the check discovers. Generated and tool-owned directories (`outputs/`,
  `.bazel-cache/`, `bazel-*`, `submodules/` if vendored) are skipped in one explicit list. The discovery uses
  `Path.iterdir()`, so it works inside Insula.
- [ ] **Fix real drift.** Fix every stale reference the first live run finds in the scanned docs, in the same
  change. Never edit retained evidence or receipts.
- [ ] **Tests.** Synthetic cases cover:
  - a missing path fails;
  - an exempt form passes;
  - a missing top-level directory in the map fails.

  The real tree passes.
- [ ] **Gate.** The check is wired into `//:repo_gate` and the membership test. `AGENTS.md` names the check
  under Commands.
- [ ] **Gates.** `//:repo_gate`, `//autonomy/...` and `//parallax/...` pass through `./bazelw`.
