# 17: Concept batch: `detection` variants and GPU workers

**What to build:** Model variants and their GPU workers live with the detector they vary, not in a directory named after the runtime.

**Blocked by:** 16 (Concept batch: `detection` core)

**Status:** ready-for-agent

- [ ] Scope: normalisation and architecture variants and follow-ups, weight and decoder contracts, scored-proposal code, checkpoint value comparison, and the learning-curve, overfit and probe workers still in use
- [ ] Workers that only a closed gate used are left for the studies batches and listed in the ticket's comments
- [ ] The directory named after the GPU runtime no longer contains library code
- [ ] Every module in scope lives in its concept directory and is imported by package path; no `sys.path` manipulation remains in the moved code
- [ ] Each moved test sits beside its module as `foo_test.py` and is a Bazel test target
- [ ] Bazel visibility lets only the concepts above this one depend on it
- [ ] File digests and regular-file checks in the moved code come from the evidence module, not local copies
- [ ] The same test modules pass through the wrapper as before the batch, and the pin report for the batch is attached to the ticket
- [ ] Files under `research/` are unchanged
