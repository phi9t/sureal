# 18: Concept batch: `segmentation`

**What to build:** Semantic and instance segmentation code lives under `segmentation`, including the native segmentation scoring contract.

**Blocked by:** 14 (Concept batch: `dataset`), 15 (Concept batch: `geometry`)

**Status:** ready-for-agent

- [ ] Scope: semantic mapping and support, archive support, the point semantic encoder, point-mask relations and mask point support, foreground support, label coverage, supervision alignment, no-label-zone overlap, segmentation export, semantic recovery jobs, receipts and accounting, and the segmentation contract verifiers
- [ ] Every module in scope lives in its concept directory and is imported by package path; no `sys.path` manipulation remains in the moved code
- [ ] Each moved test sits beside its module as `foo_test.py` and is a Bazel test target
- [ ] Bazel visibility lets only the concepts above this one depend on it
- [ ] File digests and regular-file checks in the moved code come from the evidence module, not local copies
- [ ] The same test modules pass through the wrapper as before the batch, and the pin report for the batch is attached to the ticket
- [ ] Files under `research/` are unchanged
