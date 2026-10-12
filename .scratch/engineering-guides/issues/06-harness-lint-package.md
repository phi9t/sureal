# 06: `harness/` holds repo tooling, starting with the repo-gate lints

**What to build:** A reader looking for "what checks the repo and how" finds it in one concept directory,
`harness/`, not mixed into `scripts/` with Surflo's inherited user entry points. This ticket creates
`harness/` and moves the repo-gate lint tooling into `harness/lint/`. `//:repo_gate` behaves exactly as before.

**Blocked by:** 01, 02, 03, 04, 07 (they add, name or unfreeze files under `scripts/`; moving after they land avoids conflicts)

**Status:** done

Source: `~/workspace/milano/harness/` and its subpackage READMEs (`harness/workflow/lint/README.md`). See also
Milano commit `bbe03b7` ("Each harness subpackage has a README saying what it owns"). Sureal ADR 0001 says
`scripts/` stays "for now". This ticket is that follow-up.

Decisions (coordinator, 2026-10-11):
- `harness/` is a top-level component and its own Python import root, like `autonomy/` and `parallax/`. Code
  imports `from lint.pinned_sources import ...`, never `from harness...`, `scripts...` or relative imports. Update
  the import checker's roots accordingly.
- **Moves to `harness/lint/`:** every unpinned repo-gate checker in `scripts/`, with its test, baseline JSON and
  `repo_gate_*_test.py`:
  - `check_identifiers`, `check_imports`, `check_shell_style`, `check_storage_boundary`;
  - `check_cxx` (from ticket 01);
  - `clang_format_repo`, `ruff_repo`, `shellcheck_repo`, `shfmt_repo`;
  - `pinned_sources`, `publication_audit`;
  - `githooks_test`;
  - `tests/test_publication_audit.py` (colocated as `publication_audit_test.py`).
- **Stays in `scripts/`:** Surflo's user entry points (`infer.py`, `evaluate.py`, `preprocess.py`,
  `repack_checkpoint.py`, `download_dl3dv_10k_meshed.py`) keep the upstream compatibility boundary. The
  collaboration tooling and the Insula core move in tickets 08 and 09.
- Retained receipts and evidence JSON are not edited. Ticket 07 has already retired the source freeze.

- [x] `git mv` the files above. History follows the renames: one commit of pure moves, then one commit of
  reference fixes. If the import-root change cannot stay green on its own, squash the two at landing.
- [x] Bazel targets move to `harness/lint/BUILD.bazel` (or `harness/BUILD.bazel`). `//:repo_gate` keeps the same
  test set, and the membership test proves it. Target labels change only where the move forces it.
- [x] `.githooks/pre-commit` and `AGENTS.md` (Commands, "Keep hooks and shell wrappers thin") name the new
  paths. The hook still imports no repo runtime code.
- [x] Every active reference is updated: guides, ADRs (append a consequence note, never rewrite history),
  `CONTRIBUTING.md` and `docs/repo-structure.md`. `.scratch/` history and retained evidence are left alone.
- [x] `harness/README.md` (what harness owns and the subpackage map) and
  `harness/lint/README.md` (owns, boundaries, entry points), in Milano's subpackage README shape.
- [x] A new ADR, `docs/adr/0005-harness-holds-repo-tooling.md`, records the decision and the import root.
- [x] Live first: `./bazelw test //:repo_gate` is green after the move and shows the same test count plus any
  moved tests. Then `//autonomy/...` and `//parallax/...` pass.

## Comments

- 2026-10-12 Landed by the coordinator. The 26 repo-gate checkers, their baselines and tests moved from
  `scripts/` and `tests/` to `harness/lint/` as pure renames plus reference fixes. `harness/` is an import root
  (`from lint...`). `//:repo_gate` keeps the same membership via `//harness/lint:*`. ADR 0005, `harness/README.md`
  and `harness/lint/README.md` were added. The hook, CI workflow, guides and AGENTS.md now name the new paths. The
  coordinator set this Status line, which the worker left unset.
