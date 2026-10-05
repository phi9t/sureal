# 15: Concept batch: `geometry`

**What to build:** Coordinate and projection mathematics lives under `geometry`.

**Blocked by:** 13 (Concept batch: `insula` and `evidence`)

**Status:** ready-for-agent

- [ ] Scope: transforms and the geometry foundation, camera coordinates, projection visibility, native range grids, range-shape references, files, workers and transfer
- [ ] Every module in scope lives in its concept directory and is imported by package path; no `sys.path` manipulation remains in the moved code
- [ ] Each moved test sits beside its module as `foo_test.py` and is a Bazel test target
- [ ] Bazel visibility lets only the concepts above this one depend on it
- [ ] File digests and regular-file checks in the moved code come from the evidence module, not local copies
- [ ] The same test modules pass through the wrapper as before the batch, and the pin report for the batch is attached to the ticket
- [ ] Files under `research/` are unchanged
