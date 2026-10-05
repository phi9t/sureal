# 24: Studies batch: the fixed-batch suites and the experiment catalog

**What to build:** The two fixed-batch architecture suites and the architecture experiment catalog are dissolved: their reusable code lives in the concept it implements, and each study's procedure records live under a directory named for that study.

**Blocked by:** 17 (Concept batch: `detection` variants and GPU workers), 18 (Concept batch: `segmentation`), 19 (Concept batch: `range_view`)

**Status:** ready-for-agent

- [ ] Scope: the fixed-batch overfit suite, the expanded suite, and the architecture catalog, runner and harness
- [ ] Reusable models, catalogs, packing, contracts and losses move to their concept; the experiment runner stays a runnable, tested tool
- [ ] Procedure records of closed gates are exported from the build graph as files and are not test targets
- [ ] Each module name that existed in more than one directory now has one home, or two clearly different names
- [ ] Every module in scope lives in its concept directory and is imported by package path; no `sys.path` manipulation remains in the moved code
- [ ] Each moved test sits beside its module as `foo_test.py` and is a Bazel test target
- [ ] Bazel visibility lets only the concepts above this one depend on it
- [ ] File digests and regular-file checks in the moved code come from the evidence module, not local copies
- [ ] The same test modules pass through the wrapper as before the batch, and the pin report for the batch is attached to the ticket
- [ ] Files under `research/` are unchanged
