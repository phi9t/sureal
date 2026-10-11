# 02: Shell engineering guide

**What to build:** A contributor writing a Sureal shell wrapper follows `docs/guides/shell-engineering.md`, which
states the function contract, scoping and diagnostics rules Milano uses. The existing shell-style lint
points at the new guide.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

Source: `~/workspace/milano/docs/guides/shell-engineering.md` and
`~/workspace/milano/docs/adr/0001-python-over-shell-for-policy.md`. Sureal's
`docs/guides/shell-style.md` and `docs/adr/0003-python-over-shell-for-policy.md` are the starting point.

- [ ] **Rename.** `docs/guides/shell-style.md` becomes `docs/guides/shell-engineering.md` (`git mv`). It is expanded with:
  - "use shell only for glue", linking Sureal ADR 0003;
  - the file shape;
  - function comments, including the structured `Globals:` / `Arguments:` / `Outputs:` / `Returns:` block for
    non-obvious or cross-script functions;
  - `local` for function variables;
  - `${var}` braces in new and rewritten scripts;
  - arrays for argv;
  - `case` for option parsing;
  - diagnostics with `printf ... >&2`;
  - the ShellCheck disable policy;
  - a closing checklist.
- [ ] **Sureal deltas recorded explicitly.** These stay:
  - the `#!/usr/bin/env bash` shebang;
  - the 150-line limit and the shrinking `scripts/shell_style_baseline.json`;
  - the Bazel-pinned ShellCheck and shfmt;
  - receipt-pinned scripts are exempt.
- [ ] **References.** `AGENTS.md`, `scripts/check_shell_style.py` and its tests, and any other active reference
  name the new path. A grep over active files, excluding `.scratch/` history, finds no `shell-style.md`.
- [ ] **No weakening.** The mechanical lint keeps every rule it enforces today. Add a mechanical rule only if
  the real tree already passes it, or the same change fixes the violations in unpinned files.
- [ ] **Gates.** `//:repo_gate` passes through `./bazelw`.
