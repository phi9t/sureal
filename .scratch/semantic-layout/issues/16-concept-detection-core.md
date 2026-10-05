# 16: Concept batch: `detection` core

**What to build:** The detector and everything it needs lives under `detection`: anchors, box coding, the pillar encoder, the detector, its loss and decoder, and the export and adapter for native scoring.

**Blocked by:** 14 (Concept batch: `dataset`), 15 (Concept batch: `geometry`)

**Status:** ready-for-agent

- [ ] Scope: anchor grid and assignment, box coding, pillar packing and encoder, packed point features, the pillar detector, detector geometry, loss and decoding, prediction records, detection export, the native detection adapter, and the training-box pipeline
- [ ] Every module in scope lives in its concept directory and is imported by package path; no `sys.path` manipulation remains in the moved code
- [ ] Each moved test sits beside its module as `foo_test.py` and is a Bazel test target
- [ ] Bazel visibility lets only the concepts above this one depend on it
- [ ] File digests and regular-file checks in the moved code come from the evidence module, not local copies
- [ ] The same test modules pass through the wrapper as before the batch, and the pin report for the batch is attached to the ticket
- [ ] Files under `research/` are unchanged
