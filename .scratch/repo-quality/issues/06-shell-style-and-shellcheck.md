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

**Status:** done

- [x] **Live first.** ShellCheck runs over all tracked shell scripts. Findings are recorded by rule. Each script also runs for real (or `--help` / dry-run where running it would launch work) after it is fixed.
- [x] **ShellCheck comes from the rootfs or a pinned Bazel dependency**, not from host packages.
- [x] **Scripts pinned by retained receipts are excluded**, using the same receipt-derived list as ticket 05.
- [x] **The guide is written**, and AGENTS.md points at it.
- [x] **Gates pass**, with counts recorded.

## Comments

- 2026-10-10 Done:
  - Rootfs check: ShellCheck was not present in the CPU, curriculum, or GPU rootfses, so the repo gate uses Bazel-pinned ShellCheck 0.11.0 from `https://github.com/koalaman/shellcheck/releases/download/v0.11.0/shellcheck-v0.11.0.linux.x86_64.tar.xz`, sha256 `8c3be12b05d5c177a04c29e3c78ce89ac86f1595681cab149b65b97c4e227198`.
  - Live ShellCheck first pass over the real tree: `tracked_shell=28`, `receipt_pinned_shell=1`, `shellcheck_scope=27`; output recorded one finding, `SC2034` for unused `RED` in `autonomy/resources/refresh-hdfs-auth.sh`.
  - Fixed `autonomy/resources/refresh-hdfs-auth.sh` without touching retained receipts, then reran ShellCheck: `tracked_shell=28`, `receipt_pinned_shell=1`, `shellcheck_scope=27`, exit 0. The retained-receipt exclusion was `autonomy/tracer.sh`.
  - Script smoke sweep covered 28 tracked shell entries using direct execution, `bash`, `--help`, `--emit-plan`, dry-run/preflight, or expected usage paths. Context-sensitive reruns covered the non-executable wrappers, `parallax/run.sh` inside the Parallax rootfs, and `experiments/insula-scout/run_scout.sh` with the required rootfs bindings.
  - Focused Bazel check passed: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:shellcheck_repo_test //:repo_gate_shellcheck_test //:repo_gate_membership_test` -> 3/3 tests pass.
  - Repo gate passed: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate` -> 9/9 tests pass.
  - CPU autonomy gate passed: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` -> 189/189 tests pass. Count is unchanged by this ticket; no `autonomy` Bazel target files changed.
  - Parallax gate passed: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` -> 17/17 tests pass. Count is unchanged by this ticket; no `parallax` Bazel target files changed.
  - GPU 1 availability check showed UUID `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619` at 4 MiB used with no compute process on that UUID, so the CUDA gate ran and passed: `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` -> 30/30 tests pass.
  - Shared-file overlaps touched by this ticket: `AGENTS.md`, `BUILD.bazel`, `MODULE.bazel`, and `scripts/repo_gate_membership_test.py`.
