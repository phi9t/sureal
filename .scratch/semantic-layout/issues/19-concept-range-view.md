# 19: Concept batch: `range_view`

**What to build:** Range-image models live under `range_view`.

**Blocked by:** 16 (Concept batch: `detection` core)

**Status:** ready-for-agent

- [ ] Scope: the range frontend, the range-pillar hybrid, sparse windows and sparse window attention, and range fusion
- [ ] Every module in scope lives in its concept directory and is imported by package path; no `sys.path` manipulation remains in the moved code
- [ ] Each moved test sits beside its module as `foo_test.py` and is a Bazel test target
- [ ] Bazel visibility lets only the concepts above this one depend on it
- [ ] File digests and regular-file checks in the moved code come from the evidence module, not local copies
- [ ] The same test modules pass through the wrapper as before the batch, and the pin report for the batch is attached to the ticket
- [ ] Files under `research/` are unchanged
