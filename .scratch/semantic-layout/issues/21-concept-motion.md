# 21: Concept batch: `motion`

**What to build:** Motion ingestion and evaluation live together under `motion`, Python and C++ side by side.

**Blocked by:** 14 (Concept batch: `dataset`), 15 (Concept batch: `geometry`), 28 (The perception rootfs carries the tools its tests need)

**Status:** ready-for-agent

- [ ] Scope: motion ingestion, the causal projection, and the native, pooled and joint motion metric tools with their Python drivers and verifiers
- [ ] C++ that needs the upstream Waymo sources keeps its existing build inside its dedicated rootfs; C++ that builds from this repository gets Bazel targets
- [ ] Every module in scope lives in its concept directory and is imported by package path; no `sys.path` manipulation remains in the moved code
- [ ] Each moved test sits beside its module as `foo_test.py` and is a Bazel test target
- [ ] Bazel visibility lets only the concepts above this one depend on it
- [ ] File digests and regular-file checks in the moved code come from the evidence module, not local copies
- [ ] The same test modules pass through the wrapper as before the batch, and the pin report for the batch is attached to the ticket
- [ ] Files under `research/` are unchanged
