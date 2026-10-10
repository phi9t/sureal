# 02: One repo gate

**What to build:** A single Bazel target, run inside Insula, that runs every static quality check:
- every `*_boundary_test`;
- `storage_boundary_test`;
- the launch-plan boundary test;
- `scripts/publication_audit.py`, which today runs only in GitHub CI;
- whitespace checking (`git diff --check` style) over tracked files.

AGENTS.md names it as the command to run before landing.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] **Live first.** The gate runs for real on mainline. Its output, duration and any findings are recorded. Real findings are fixed or listed, never hidden.
- [x] **One target** (for example `//:repo_gate` or `//autonomy:repo_gate`) aggregates the static checks. Live-gate and GPU checks are excluded.
- [x] **`publication_audit.py` runs under Bazel inside the gate.** The CI workflow calls the same target or the same script.
- [x] **Self-tests:** a test proves the gate's membership. A new `*_boundary_test` that isn't in the gate fails it.
- [x] **AGENTS.md** gains a "Commands" section: the gate, the CPU, CUDA and parallax suites, and the Insula boundary.
- [x] **Gates pass:** CPU, parallax, and CUDA on GPU 1 when it is free. Counts recorded.

## Comments

### 2026-10-10 Done

Implemented `//:repo_gate` as the static repository gate. It aggregates:
`//autonomy/blob_store:storage_boundary_test`,
`//autonomy/insula:launch_plan_boundary_test`,
`//autonomy/resources:concept_boundary_test`,
`//:repo_gate_publication_audit_test`, `//:repo_gate_whitespace_test`,
`//:repo_gate_membership_test`, and
`//:publication_audit_behavior_test`.

Live-first findings and fixes:
- First live gate attempts exposed that Bazel tests could not run Git-index
  checks from the Insula-mounted worktree: `/experiment/.git` pointed at an
  absolute worktree gitdir, then that gitdir used an alternate object store
  outside the sandbox. Fixed in `autonomy/insula/bazel_launcher.py` by mounting
  the worktree gitdir read-only and exposing sandbox-local, read-only Git
  object views only to repo-gate tests.
- Once the audit could run, it reported tracked fixture logs:
  `autonomy/segmentation/testdata/semantic_receipts/*/source/live.log`. Those
  are retained testdata fixtures, so `scripts/publication_audit.py` now exempts
  paths under `testdata` from generated-file rejection and the behavior is
  pinned by `//:publication_audit_behavior_test`.
- The publication audit's portable Parallax subprocess failed under Bazel's
  Python safe-path environment with `ModuleNotFoundError: No module named
  'contracts'`. Fixed by clearing `PYTHONSAFEPATH` for publication-audit
  portable subprocesses, matching the repo wrapper's launcher behavior.
- A Parallax rerun initially failed
  `//parallax:test_foundation_geometry_reference` because global Git object
  environment leaked into temporary fixture repositories. Fixed by passing
  sandbox Git object paths through `SUREAL_REPO_GATE_*` variables and applying
  them only in repo-gate tests.

Final verification on the finished tree:
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate`
  passed: 7/7 tests, elapsed 12.966s.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate //autonomy/insula:bazel_wrapper_test`
  passed: 8/8 tests, elapsed 29.867s.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`
  passed: 188/188 tests, elapsed 92.903s. Count remains the expected 188.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`
  passed: 17/17 tests, elapsed 388.713s.
- GPU 1 availability was checked before CUDA. Initial check after the Parallax
  pass showed UUID `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619` busy with PID
  686065 and 640 MiB used. After the required 10-minute wait, GPU 1 was free:
  4 MiB used and no compute process.
- `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`
  passed: 30/30 tests, elapsed 120.808s.

Shared-file overlaps: this ticket touched `AGENTS.md`, `BUILD.bazel`, and
`autonomy/insula/bazel_launcher.py`. No retained receipts, root filesystems,
locks, or evidence bytes were edited.

### 2026-10-10 Linked-worktree follow-up

Landing validation in a linked worktree exposed that the first wrapper fix
mounted only the per-worktree gitdir and not the linked worktree's common Git
dir. Fixed `autonomy/insula/bazel_launcher.py` to mount linked-worktree common
metadata read-only, make `/experiment/.git` resolve to the per-worktree gitdir
inside that common mount, and pass explicit repo-gate Git variables for
`GIT_DIR`, `GIT_WORK_TREE`, `GIT_COMMON_DIR`, `GIT_OBJECT_DIRECTORY`, and
`GIT_ALTERNATE_OBJECT_DIRECTORIES`.

Backfilled `//autonomy/insula:bazel_wrapper_test` with plain, alternate-object
clone, and linked-worktree-with-`commondir` fixtures. The test materializes the
wrapper's mount/env plan in a temp sandbox and runs the gate Git commands:
`git ls-files --stage -z`, boundary-test `git ls-files`, and
`git diff --check HEAD --`.

Verification:
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/insula:bazel_wrapper_test`
  first failed on the missing common-dir projection, then passed after the fix:
  1/1 target, elapsed 19.245s.
- `./bazelw test //:repo_gate` from this worker worktree passed: 7/7 tests,
  elapsed 12.852s.
- Created a fresh linked worktree under `$TMPDIR` with
  `git worktree add --force <tmp>/worktree worker/rq02-repo-gate`, seeded its
  local `.bazel-cache`, ran `./bazelw test //:repo_gate`, and removed it with
  `git worktree remove --force`: 7/7 tests passed, elapsed 12.342s.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`
  passed: 188/188 tests, elapsed 94.181s. Count remains 188; the new
  regression is an added case inside the existing wrapper test target.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`
  passed: 17/17 tests, elapsed 391.673s.
- GPU 1 availability was checked before CUDA. Required UUID
  `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619` had 4 MiB used and no compute
  process in `nvidia-smi --query-compute-apps`.
- `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`
  passed: 30/30 tests, elapsed 119.794s.

Shared-file overlaps in this follow-up: `autonomy/insula/bazel_launcher.py`.
No retained receipts, root filesystems, locks, or shared caches were edited.

### 2026-10-10 Linked-wrapper-test follow-up

Mainline landing validation at `6271417` in the linked worktree
`/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/land-mainline`
passed `//:repo_gate` but failed four
`//autonomy/insula:bazel_wrapper_test` subtests. The failure was in the
external-cwd wrapper assertion: it expected `/experiment/.git` to be a direct
read-only bind of the host gitdir, while linked worktrees intentionally expose
`/experiment/.git` as a read-only symlink to the per-worktree gitdir inside the
read-only common-dir mount.

Fixed `autonomy/insula/bazel_wrapper_test.py` so the assertion derives the
expected gitdir/common-dir layout through the same launcher resolution rules
used by the nested `--emit-plan` process. The test still proves the exact Git
metadata shape: plain repositories and alternate-object clones require a direct
read-only `.git` bind, while linked worktrees require the read-only
`/tmp/sureal-git-common` bind plus a read-only `/experiment/.git` symlink to
the matching sandbox gitdir under that common mount.

Verification from a fresh linked worktree under `$TMPDIR`, created with
`git worktree add --force <tmp>/worktree worker/rq02-repo-gate`, with local
`.bazel-cache` seeded, and removed afterwards with `git worktree remove --force`:
- `./bazelw test //:repo_gate` passed: 7/7 tests, elapsed 11.646s.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`
  passed: 188/188 tests, elapsed 95.276s.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`
  passed: 17/17 tests, elapsed 386.629s.

Verification from this worker worktree:
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/insula:bazel_wrapper_test`
  passed: 1/1 target, elapsed 19.203s.
- `./bazelw test //:repo_gate` passed: 7/7 tests from cache, elapsed 2.204s;
  reran live with no-cache flags:
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate`
  passed: 7/7 tests, elapsed 11.603s.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`
  passed: 188/188 tests, elapsed 88.356s.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`
  passed: 17/17 tests, elapsed 396.585s.
- GPU 1 availability was checked before CUDA. Required UUID
  `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619` had 4 MiB used and no compute
  process in `nvidia-smi --query-compute-apps`.
- `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`
  passed: 30/30 tests, elapsed 118.032s.

Shared-file overlaps in this follow-up: `autonomy/insula/bazel_wrapper_test.py`.
No retained receipts, root filesystems, locks, or shared caches were edited.
