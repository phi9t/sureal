# 22: Concept batch: `resources`

**What to build:** Measured, resource-bounded stage execution lives under `resources`, together with the continuation code that resumes and compares bounded replays.

**Blocked by:** 13 (Concept batch: `insula` and `evidence`)

**Status:** ready-for-agent

- [ ] Scope: the stage backend, kernel scope, process lifecycle, stage accounting, commands, workers, checkpoint and retention, and the continuation and continuation-control code
- [ ] The stage backend no longer imports from a study; the four study-specific imports are inverted or passed in
- [ ] Every module in scope lives in its concept directory and is imported by package path; no `sys.path` manipulation remains in the moved code
- [ ] Each moved test sits beside its module as `foo_test.py` and is a Bazel test target
- [ ] Bazel visibility lets only the concepts above this one depend on it
- [ ] File digests and regular-file checks in the moved code come from the evidence module, not local copies
- [ ] The same test modules pass through the wrapper as before the batch, and the pin report for the batch is attached to the ticket
- [ ] Files under `research/` are unchanged
