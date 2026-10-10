# 07: One import rule, checked

**What to build:** An AST checker, adapted from milano's `scripts/check_imports.py`, that enforces three rules in active code:
- absolute imports from each Bazel import root (`autonomy/`, `parallax/`);
- no relative imports;
- no `sys.path` edits.

It runs as a boundary test in the repo gate.
- Unlike milano, `PYTHONPATH=autonomy` in documented commands and receipts stays allowed. Sureal's live runs use it.
- Frozen code (`research/`, `studies/*/procedure_records/`, `studies/architecture/harness/`) and pinned sources are exempt.

**Blocked by:** 02

**Status:** done

- [x] **Live first.** The scan runs over the tree, and the hits are recorded by kind and by directory. The live runs touched by any fix are re-run: the motion verifiers, and a resource stage if one is touched.
- [x] **Hits in active, unpinned code are fixed.** Any others are put in a baseline that may only shrink, with a reason for each.
- [x] **Self-tests:** positive, negative, and the real repo scanning clean.
- [x] **The rule is written** in the Python style guide (ticket 05), or in AGENTS.md if 05 hasn't landed yet.
- [x] **Gates pass**, with counts recorded.

## Comments

2026-10-10 Done:
- Implemented `scripts/check_imports.py` as an AST import-root checker for `autonomy/` and `parallax/`, with frozen-path and retained-source-pin exemptions derived from `autonomy/retained_receipt_sweep.py` plus receipts.
- First live scan found active unpinned hits in `autonomy/inspection`, `parallax/pipeline`, `parallax/insulas/surflo-foundation`, and Parallax test harnesses. Active code was fixed to use import-root-anchored imports; remaining legacy test-harness `sys.path` edits are in `scripts/import_rule_baseline.json` with shrink-only reasons.
- Final live scan: `python3 scripts/check_imports.py --root . --summary-json` passed with `problem_count=78`, `baseline_count=78`, `unexpected_count=0`, `stale_baseline_count=0`, `pinned_source_count=267`; by kind: `sys-path-edit=78`; by directory: `autonomy/training_execution=2`, `parallax/tests=76`.
- Self-tests: `python3 -m unittest scripts.import_rule_behavior_test scripts.repo_gate_import_rule_test scripts.publication_audit_behavior_test` ran 10 tests, OK.
- Repo gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate` passed 9/9 tests.
- CPU autonomy gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed 189/189 tests. The recorded base evidence was 188/188; this ticket did not add an `autonomy/...` test target, so the one-test count increase is from the current checkout state rather than a new import-rule autonomy target.
- Parallax gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed 17/17 tests.
- CUDA eligibility: GPU 1 was UUID `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619`, `memory.used=4 MiB`, and no compute process was listed for that UUID. CUDA gate: `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed 30/30 tests.
- Shared-file overlaps: `AGENTS.md` documents the import rule because ticket 05 has not landed; root `BUILD.bazel` adds the import-rule tests to `REPO_GATE_TESTS`.
