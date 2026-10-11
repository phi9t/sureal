# 06: `harness/` holds repo tooling, starting with the repo-gate lints

**What to build:** A reader looking for "what checks the repo and how" finds it in one concept directory,
`harness/`, not mixed into `scripts/` with Surflo's inherited user entry points. This ticket creates
`harness/` and moves the repo-gate lint tooling into `harness/lint/`. `//:repo_gate` behaves exactly as before.

**Blocked by:** 01, 02, 03, 04 (they add or name files under `scripts/`; moving after they land avoids conflicts)

**Status:** ready-for-agent

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
  - `githooks_test`.
- **Stays, and is listed in `harness/README.md` with the reason:**
  - Surflo's user entry points in `scripts/` (`infer.py`, `evaluate.py`, `preprocess.py`,
    `repack_checkpoint.py`, `download_dl3dv_10k_meshed.py`) keep the upstream compatibility boundary.
  - `scripts/_collab/` and `collab*.py` stay because `_collab/admission.py` is source-pinned.
  - The `autonomy/insula/` and `autonomy/evidence/` cores stay because they are source-pinned and owned by
    autonomy ADRs.

  These are named as future `harness/` candidates once re-pinning is possible.
- No file protected by a source pin or retained receipt moves or changes bytes. Verify with
  `pinned_sources.protected_source_paths` before and after.

- [ ] `git mv` the files above. History follows the renames: one commit of pure moves, then one commit of
  reference fixes. If the import-root change cannot stay green on its own, squash the two at landing.
- [ ] Bazel targets move to `harness/lint/BUILD.bazel` (or `harness/BUILD.bazel`). `//:repo_gate` keeps the same
  test set, and the membership test proves it. Target labels change only where the move forces it.
- [ ] `.githooks/pre-commit` and `AGENTS.md` (Commands, "Keep hooks and shell wrappers thin") name the new
  paths. The hook still imports no repo runtime code.
- [ ] Every active reference is updated: guides, ADRs (append a consequence note, never rewrite history),
  `CONTRIBUTING.md` and `docs/repo-structure.md`. `.scratch/` history and retained evidence are left alone.
- [ ] `harness/README.md` (what harness owns, the map, what stays elsewhere and why) and
  `harness/lint/README.md` (owns, boundaries, entry points), in Milano's subpackage README shape.
- [ ] A new ADR, `docs/adr/0005-harness-holds-repo-tooling.md`, records the decision, the import root, and the
  pinned-code exception.
- [ ] Live first: `./bazelw test //:repo_gate` is green after the move and shows the same test count plus any
  moved tests. Then `//autonomy/...` and `//parallax/...` pass.
