# 09: Shell lint for the guide's rules, and shfmt

**What to build:** `docs/guides/shell-style.md` is enforced in `//:repo_gate`, and the guide matches the scripts (or the scripts match the guide).

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

Decisions, from the coordinator under user delegation on 2026-10-10:
- The script length limit is **150 lines**, raised from Milano's 100.
- The rootfs build scripts are covered by the limit.
- Scripts that are already longer are grandfathered in a checked-in baseline. Each one moves its policy logic to Python when it is next changed substantially.
- The baseline may only shrink.

Source: `../research/milano-conventions.md`, Bash section.

- [ ] **Shebang.** Settle the rule with the scripts. Today 27 of 28 use `#!/usr/bin/env bash` while the guide says `#!/bin/bash`; pick one and make all scripts conform.
- [ ] **Lint.** A repo-gate lint checks:
  - the shebang;
  - the header comment;
  - a comment above each function;
  - 120 columns;
  - no backticks;
  - at most 150 lines outside the baseline.
- [ ] **shfmt.** shfmt (`-i 2 -ci -bn`) is pinned as a Bazel-fetched release archive, run in `//:repo_gate`, and applied in one whitespace-only batch. Files pinned by retained evidence are excluded.
- [ ] **ADR.** "Python over shell for policy": scripts keep orchestration only, and decisions and data handling live in Python.
- [ ] **Gates:** `//:repo_gate`, `//autonomy/...` and `//parallax/...`.
