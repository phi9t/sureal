# 04: Versioned git hooks and a full AGENTS.md

**What to build:**
- A `.githooks/pre-commit` that runs `git diff --cached --check` and the identifier and storage scans as standalone static scripts. It imports no repo code, per ADR 0002.
- A one-line enable command.
- AGENTS.md gains milano-style sections: execution boundary, commands, cache rules ("run the retention planner's dry run and review it before any apply"), and engineering rules.

**Blocked by:** 01, 03

**Status:** done

- [x] **Live first.** The hook runs for real on a commit that is clean and on one with a planted violation, in a scratch clone. It blocks the violation and allows the clean commit. Recorded.
- [x] **The hooks are versioned under `.githooks/`.** `git config core.hooksPath .githooks` is documented, and a test checks that the hooks are executable and start with `#!/bin/bash`.
- [x] **AGENTS.md** has these sections: execution boundary, commands, cache rules, engineering rules (pointing at the ADRs), and the issue tracker.
- [x] **Gates pass**, with counts recorded.

## Comments

### Done 2026-10-10

Implemented `.githooks/pre-commit`, documented `git config core.hooksPath
.githooks`, added `scripts/check_storage_boundary.py`, and joined
`//:repo_gate` with `//:githooks_test` and
`//:check_storage_boundary_test`. `AGENTS.md` now has execution boundary,
commands, cache rules, engineering rules with ADR pointers, and issue-tracker
sections. Shared-file overlaps: `AGENTS.md` and `BUILD.bazel`.

Live-first hook proof:
- Real-tree host checks before tests: `git diff --cached --check`;
  `python3 scripts/check_identifiers.py --root "$PWD"` passed with
  `scanned_text_files=2050`, `skipped_binary_files=22`,
  `skipped_retained_files=3134`; `python3 scripts/check_storage_boundary.py
  --root "$PWD/autonomy"` passed with `scanned_files=463`.
- Scratch clone `hook-live-final.l5hWHI`, with the final staged patch applied
  and `core.hooksPath=.githooks`: clean commit status `0`, hook output
  included identifier pass over `2050` text files and storage-boundary pass over
  `463` files; planted active-code violation commit status `1`, storage-boundary
  output reported `dataset/planted_hook_violation.py:1` for `Waystone command
  constant` and `direct Waystone CLI path`.

Gates:
- `python3 -m unittest scripts.check_storage_boundary_test
  scripts.githooks_test -v`: 6 tests passed.
- `./bazelw test --noexperimental_collect_system_network_usage
  --nocache_test_results --test_output=errors //:repo_gate`: 12 of 12 tests
  passed. Count increased from 10 to 12 because this ticket added
  `//:check_storage_boundary_test` and `//:githooks_test`.
- `./bazelw test --noexperimental_collect_system_network_usage
  --nocache_test_results --test_output=errors //autonomy/...`: 189 of 189 tests
  passed. This matches the base count at `3a2c681`.
- `./bazelw test --noexperimental_collect_system_network_usage
  --nocache_test_results --test_output=errors //parallax/...`: 17 of 17 tests
  passed.
- GPU 1 initial check: UUID `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619`,
  `memory.used=40 MiB`, compute process `pid=1788670`, so CUDA waited. First
  10-minute recheck: GPU 1 `memory.used=4 MiB` and no compute process on that
  UUID.
- `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda
  --noexperimental_collect_system_network_usage --nocache_test_results
  --test_output=errors //autonomy/...`: 30 of 30 tests passed.
