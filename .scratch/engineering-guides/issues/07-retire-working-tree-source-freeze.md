# 07: Retire the working-tree source freeze

**What to build:** Contributors can edit, reformat and move any active source file. Old receipts that mention the
file no longer block the change. The repo gate stops treating files named by receipts or by current-candidate
source declarations as byte-frozen. This completes `autonomy/docs/adr/0001-source-pins-refer-to-snapshots.md`, which
already says "the working tree is free to change" while the lint tooling still enforced the old model.

**Blocked by:** 01, 02 (they touch the lint wrappers that consume the freeze)

**Status:** done

Decision (user, 2026-10-11): the freeze is not needed. Receipts are historical records. Their bytes are
recoverable from git history and source snapshots. The deferred research reruns will be re-admitted on the
current tree when they are run again.

- [x] The repo-gate lints no longer exclude receipt-pinned, digest-pinned or current-candidate files:
  - Ruff;
  - ShellCheck;
  - shfmt;
  - the shell-style check;
  - clang-format;
  - the C++ lint;
  - the import checker.

  Only these remain excluded:
  - the archive directories `autonomy/research/`, `parallax/research/`, `*/studies/*/procedure_records/` and
    `*/studies/architecture/harness/`, which are historical records and are kept as written;
  - `submodules/`.
- [x] `scripts/pinned_sources.py` shrinks to what is still needed, the archive-directory rule. Remove the
  receipt-scanning and candidate-declaration machinery, and any explicit pinned-file lists in BUILD files or
  tests. The baselines (`import_rule_baseline.json`, `shell_style_baseline.json`) keep only entries that still
  apply.
- [x] Files that newly enter lint scope are handled honestly:
  - fix them;
  - or add them to an existing shrink-only baseline with a count;
  - or, for the Ruff format batch and clang-format, leave them outside the batch directory list.

  Never weaken a rule to get green.
- [x] Receipts and retained evidence JSON are still never edited. Only the sources they mention are freed.
- [x] Docs updated:
  - `AGENTS.md` drops "files protected by retained/current-candidate source pins" from the style and cache rules;
  - the guides drop the pinned-file exemptions;
  - `autonomy/docs/adr/0001` gains a consequence note that the lint-side freeze is retired, with today's date.
- [x] Live first: `./bazelw test //:repo_gate`. Then `//autonomy/...`, `//parallax/...`, and CUDA on GPU 1 if it is
  free. Report how many files each lint now covers, before and after.

## Comments

- 2026-10-11 Landed by the coordinator. The worker retired the receipt, digest and current-candidate freeze
  from every repo-gate lint (`scripts/pinned_sources.py` now names only archives and `submodules/`). It fixed
  newly in-scope files (relative imports become concept-root imports, Ruff format, a shell header). It recorded
  the 89 remaining findings in the 15 formerly pinned C++ files in `scripts/cxx_lint_baseline.json`, where
  stale entries fail the gate. Those files stay outside the clang-format batch. At landing the coordinator moved
  the worker's `python-style.md` edits into `python-engineering.md` (ticket 03 renamed it) and set this Status
  line, which the worker left unset.
