# 09: Shell lint for the guide's rules, and shfmt

**What to build:** `docs/guides/shell-style.md` is enforced in `//:repo_gate`, and the guide matches the scripts (or the scripts match the guide).

**Blocked by:** None (can start immediately)

**Status:** done

Decisions, from the coordinator under user delegation on 2026-10-10:
- The script length limit is **150 lines**, raised from Milano's 100.
- The rootfs build scripts are covered by the limit.
- Scripts that are already longer are grandfathered in a checked-in baseline. Each one moves its policy logic to Python when it is next changed substantially.
- The baseline may only shrink.

Source: `../research/milano-conventions.md`, Bash section.

- [x] **Shebang.** Settle the rule with the scripts. Today 27 of 28 use `#!/usr/bin/env bash` while the guide says `#!/bin/bash`; pick one and make all scripts conform.
- [x] **Lint.** A repo-gate lint checks:
  - the shebang;
  - the header comment;
  - a comment above each function;
  - 120 columns;
  - no backticks;
  - at most 150 lines outside the baseline.
- [x] **shfmt.** shfmt (`-i 2 -ci -bn`) is pinned as a Bazel-fetched release archive, run in `//:repo_gate`, and applied in one whitespace-only batch. Files pinned by retained evidence are excluded.
- [x] **ADR.** "Python over shell for policy": scripts keep orchestration only, and decisions and data handling live in Python.
- [x] **Gates:** `//:repo_gate`, `//autonomy/...` and `//parallax/...`.

## Comments

### 2026-10-10 Done

Live-first check before edits:
- `TMPDIR=~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/repo09-shell-lint-and-shfmt-20261010T232640Z/tmp/live-pre-* ./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate //:pinned_sources_test`
  passed: 19/19 tests, elapsed 83.304s, invocation `86d3e0a3-af6d-4b61-a3a4-d5fa23522d9f`.

Implemented:
- Settled shell shebangs on `#!/usr/bin/env bash`. Final tracked `*.sh` count:
  28/28 use `#!/usr/bin/env bash`. The extensionless `.githooks/pre-commit`
  remains `#!/bin/bash` under the existing hook test and outside this ticket's
  writable path set.
- Added `scripts/check_shell_style.py`, `scripts/check_shell_style_test.py`
  and `//:repo_gate_shell_style_test`. Final live style summary:
  `tracked_shell_style=13`, `protected_shell_style=2`, `frozen_shell_style=0`,
  `shell_style_scope=11`, `grandfathered_long_scripts=4`,
  `finding_count=0`. The protected files are `autonomy/enter.sh` and
  `autonomy/tracer.sh`.
- Added `scripts/shell_style_baseline.json`. The over-150-line baseline records
  only existing long scripts and may only shrink:
  `autonomy/dataset/setup-gcs.sh` at 252 lines,
  `autonomy/insula/build_cpu_rootfs.sh` at 181 lines,
  `autonomy/insula/build_gpu_bazel_rootfs_v6.sh` at 151 lines and
  `autonomy/resources/refresh-hdfs-auth.sh` at 252 lines.
- Pinned shfmt v3.9.0 as Bazel-fetched `@shfmt_linux_x86_64`.
  Download URL:
  `https://github.com/mvdan/sh/releases/download/v3.9.0/shfmt_v3.9.0_linux_amd64`.
  SHA-256 digest:
  `d99b06506aee2ac9113daec3049922e70dc8cffb84658e3ae512c6a6cbe101b6`.
- Added `scripts/shfmt_repo.py`, `scripts/shfmt_repo_test.py` and
  `//:repo_gate_shfmt_test`. Final shfmt scope summary:
  `tracked_shfmt_shell=13`, `protected_shfmt_shell=2`, `frozen_shfmt_shell=0`,
  `shfmt_scope=11`, exit 0.
- Applied the mechanical `shfmt -i 2 -ci -bn` batch to active, unpinned shell
  files under `autonomy/` and `parallax/`. The first formatter check listed
  10 active files; the final `//:repo_gate_shfmt_test` check listed none.
- Added `docs/adr/0003-python-over-shell-for-policy.md` and updated
  `docs/guides/shell-style.md` with the env-bash shebang, function comments,
  120-column rule, 150-line limit, shfmt command and source-pin exclusions.
- Shrunk `scripts/check_identifiers_baseline.json` by removing two stale
  `autonomy/resources/refresh-hdfs-auth.sh` host-path entries after the script
  switched to `~`-relative Waystone paths.

Focused checks:
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:check_identifiers_test //:check_shell_style_test //:repo_gate_shell_style_test //:shfmt_repo_test //:repo_gate_shfmt_test //:shellcheck_repo_test //:repo_gate_shellcheck_test //:repo_gate_membership_test //:pinned_sources_test`
  passed: 9/9 tests, invocation `e1be95e6-b083-4e25-a154-d258a70da541`.

Gates:
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate`
  passed: 23/23 tests, elapsed 94.161s, invocation `67c23dc9-aef6-47d3-8337-c9e0a7bdb5c2`.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`
  passed: 189/189 tests, elapsed 92.066s, invocation `b2dca40c-3e08-4dae-b374-7672bbd2f917`.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`
  passed: 17/17 tests, elapsed 383.375s, invocation `2cba1626-0c98-4c7a-848b-03623dcf1d4b`.
- CUDA was intentionally skipped per the worker assignment: this sandbox has no
  GPU devices, and the coordinator runs CUDA.
