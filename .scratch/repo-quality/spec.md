# Repo quality: adapt milano's maintenance practices to sureal

Status: ready-for-agent

Source: a 2026-10-09 comparison with `~/workspace/milano`:
- `scripts/check_repo.sh` and the `run_pipeline.sh repo` gate;
- `scripts/check_identifiers.py`;
- `.githooks/`;
- `milano/cache_gc.py`;
- its AGENTS.md;
- its rule that every checker ships with its own tests.

Governing decisions: `docs/adr/0001-directories-express-concepts.md`, `docs/adr/0002-bazel-runs-inside-insula.md`, and `autonomy/docs/adr/0001`-`0003`. Retained receipts are byte-exact evidence: never edit them.

## Problem Statement

**The working cache has no management tool.**
- `scientific-processing` has filled up with retained runs.
- The working-area cap in `resources/scientific_budget.py` blocks new work, including the launch-plans 03 live cohort run.
- There is no tool that says what can be safely reclaimed.
- The cohort driver's `total()` counts a hard-linked file once per link, so it reports 17.1 GB where inode-unique accounting reports about 13 GiB.

**There is no single repo gate.**
- Quality checks are scattered boundary `py_test`s.
- `scripts/publication_audit.py` runs only in GitHub CI.
- There is no git hook.

**There is no identifier check.** Nothing stops host names, `/dataNN/` paths, home directories or e-mail addresses from reaching the published repo. Only gitleaks runs, and it looks for secrets.

**AGENTS.md is only skill pointers.** It doesn't give agents the commands, the Insula boundary or the cache rules.

## Solution

1. **A scientific retention planner.** For each direct child of `scientific-processing`, it classifies the child and reports its inode-unique size:
   - protected;
   - referenced by live state;
   - released, with leftover local bytes;
   - published but not released;
   - unpublished;
   - a stray log.

   It also projects the effect on the working cap.
   - It runs as a dry run by default.
   - `--apply` may only delete stray logs and the leftovers of runs already released, after re-verifying their digests.
   - Published-but-unreleased runs are handed to the existing `retention/publish_scientific_directory.py --release` path and are never unlinked by the planner.
   - The cohort driver's working total switches to inode-unique accounting.
2. **One repo gate:** a single Bazel target that runs every static quality check.
3. **A machine-identifier boundary test** with a baseline allowlist that only shrinks.
4. **Versioned git hooks and a full AGENTS.md.**
5. **Written style guides:** Python, adapted from the Google Python Style Guide, and shell, adapted from the Google Shell Style Guide as milano did. Each is enforced by a tool: ruff lint and format for Python, ShellCheck for shell, and an AST import checker.
   - Every checker ships with its own tests.
   - Sources whose hash a retained receipt checks are never reformatted. The exclusion list is derived from receipts.

## Decisions (coordinator, under the user's delegation, 2026-10-09)

- **The planner reuses rather than restates.** It never restates the protected lists; it imports `PROTECTED_NAMES` and `PROTECTED_PATTERNS` from `publish_scientific_directory`.
- **References come from:**
  - `insula/**/state.json`;
  - `*-admitted.json`;
  - `insula/hdfs-retention-*/{verified-publication,release-completed}.json`;
  - any receipt that cites a path under the child.

  A child with any reference is kept.
- **No age-based deletion.** Unlike milano, outputs are scientific results, not things that can be rebuilt.
- **Applying needs the person's say-so.** Applying deletes local data, so `--apply` is run only on an explicit decision by the user. Tickets verify the planner live in dry-run mode only.
- **Every checker ships with:**
  - a positive test;
  - a negative test;
  - a "the real repo scans clean" test, with a baseline where one is needed.
- **Hooks are static and standalone.** They import no repo code (ADR 0002). Insula gates remain the real verification.
- **Live runs drive validation; tests come after.** Each tool is first run for real on this host's real tree and cache, and its output is reviewed. Then the tests pin that behaviour.

## Out of Scope

- Deleting anything in the cache without an explicit decision by the user.
- Reformatting pinned sources, meaning any file whose hash a retained receipt or current-candidate audit checks.
- C++ formatting: sureal has almost no C++.
