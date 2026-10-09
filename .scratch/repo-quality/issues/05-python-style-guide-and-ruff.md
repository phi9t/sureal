# 05: Python style guide, ruff lint and format, and checker self-tests

**What to build:**

- **A written Python style guide:** `docs/guides/python-style.md`, adapted from the Google Python Style Guide in the way milano adapts its C++ and shell guides. It records sureal's deliberate differences, and it covers:
  - naming;
  - module layout;
  - imports;
  - error types;
  - typing;
  - docstrings and comments;
  - no minified one-liners in new or touched code;
  - tests next to the code they test.
- **Ruff as both linter and formatter**, run as `py_test`s in the repo gate. The rule set is chosen from a live run over the tree.
- **Pinned sources are excluded.** These are files whose exact hash a retained receipt or a current-candidate audit checks:
  - `HOST_SOURCE_REQUIRED`;
  - the source-snapshot targets;
  - every `candidate_hashes` / `source_pins` entry in retained receipts.

  The list is derived by `autonomy/retained_receipt_sweep.py`, not written by hand.
- **Formatting reaches other sources in batches** by concept directory. The receipt sweep's counts must stay unchanged after each batch.
- **Every existing boundary or audit checker has** a positive test, a negative test, and a "the real repo scans clean" test.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] **Live first.** Run `ruff check` and `ruff format --check` over the tree. Record the counts by rule and by directory, and how many files are pinned. Choose the rule set and the line length from that run.
- [ ] **The style guide is written**, and AGENTS.md's engineering rules point at it.
- [ ] **Ruff comes from the rootfs or a pinned Bazel dependency**, not from host pip (ADR 0002). Its config lives in `pyproject.toml` or `ruff.toml`.
- [ ] **The pinned-file exclusion list is generated from receipts.** A test fails if a pinned file is ever formatted, or if its hash changes.
- [ ] **The first batch of unpinned directories is formatted**, with the retained-receipt sweep counts unchanged. The remaining directories are listed for follow-up batches.
- [ ] **The checker self-test gaps are filled.**
- [ ] **Gates pass**, with counts recorded.
