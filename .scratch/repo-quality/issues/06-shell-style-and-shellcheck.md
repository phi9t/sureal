# 06: Shell style guide and ShellCheck

**What to build:**

- **A written shell guide:** `docs/guides/shell-style.md`, adapted from the Google Shell Style Guide in the same way as milano's shell track:
  - bash only, starting with `#!/bin/bash`;
  - `set -euo pipefail`;
  - `[[ ]]` tests;
  - quoted expansions;
  - errors go to stderr;
  - thin wrappers, with Insula plans built in Python.
- **ShellCheck runs as a test in the repo gate.** It covers every tracked `*.sh` and the versioned hooks, at default severity with zero findings. A rule may be disabled only in `.shellcheckrc` or with an inline directive, each with a one-line reason.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] **Live first.** ShellCheck runs over all tracked shell scripts. Findings are recorded by rule. Each script also runs for real (or `--help` / dry-run where running it would launch work) after it is fixed.
- [ ] **ShellCheck comes from the rootfs or a pinned Bazel dependency**, not from host packages.
- [ ] **Scripts pinned by retained receipts are excluded**, using the same receipt-derived list as ticket 05.
- [ ] **The guide is written**, and AGENTS.md points at it.
- [ ] **Gates pass**, with counts recorded.
