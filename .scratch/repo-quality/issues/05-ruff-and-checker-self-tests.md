# 05: Ruff as a Bazel test, and every checker ships with its own tests

**What to build:**
- **Ruff runs as a `py_test` in the repo gate.** Its rule set is chosen by first running it over the tree. It excludes pinned sources: those whose hash a receipt records (`HOST_SOURCE_REQUIRED`, the source-snapshot targets) and the minified legacy modules.
- **Every existing boundary or audit checker has** a positive test, a negative test, and a "the real repo scans clean" test.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] **Live first.** Ruff runs over the tree. The counts by rule are recorded, and the rule set is chosen so that the gate is green without rewriting pinned sources.
- [ ] **Ruff is installed from the rootfs or a pinned Bazel dependency**, not from host pip (ADR 0002).
- [ ] **Pinned sources are excluded.** A test proves that no excluded file is formatted, and that no pinned file's hash changes.
- [ ] **The checker self-test gaps are filled.**
- [ ] **Gates pass**, with counts recorded.
