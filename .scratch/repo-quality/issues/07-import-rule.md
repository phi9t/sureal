# 07: One import rule, checked

**What to build:** An AST checker, adapted from milano's `scripts/check_imports.py`, that enforces three rules in active code:
- absolute imports from each Bazel import root (`autonomy/`, `parallax/`);
- no relative imports;
- no `sys.path` edits.

It runs as a boundary test in the repo gate.
- Unlike milano, `PYTHONPATH=autonomy` in documented commands and receipts stays allowed. Sureal's live runs use it.
- Frozen code (`research/`, `studies/*/procedure_records/`, `studies/architecture/harness/`) and pinned sources are exempt.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] **Live first.** The scan runs over the tree, and the hits are recorded by kind and by directory. The live runs touched by any fix are re-run: the motion verifiers, and a resource stage if one is touched.
- [ ] **Hits in active, unpinned code are fixed.** Any others are put in a baseline that may only shrink, with a reason for each.
- [ ] **Self-tests:** positive, negative, and the real repo scanning clean.
- [ ] **The rule is written** in the Python style guide (ticket 05), or in AGENTS.md if 05 hasn't landed yet.
- [ ] **Gates pass**, with counts recorded.
