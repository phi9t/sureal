# 20: Concept batch: `camera`

**What to build:** Camera data handling and the camera evaluator live together under `camera`, Python and C++ side by side.

**Blocked by:** 14 (Concept batch: `dataset`), 15 (Concept batch: `geometry`)

**Status:** ready-for-agent

- [ ] Scope: the camera dataset, sidecars and their validation, camera eviction, replay checks, camera semantic scoring, and the C++ camera projection tool
- [ ] The C++ projection tool is a Bazel target if it builds from sources in this repository; otherwise its existing build is kept and the reason recorded
- [ ] Every module in scope lives in its concept directory and is imported by package path; no `sys.path` manipulation remains in the moved code
- [ ] Each moved test sits beside its module as `foo_test.py` and is a Bazel test target
- [ ] Bazel visibility lets only the concepts above this one depend on it
- [ ] File digests and regular-file checks in the moved code come from the evidence module, not local copies
- [ ] The same test modules pass through the wrapper as before the batch, and the pin report for the batch is attached to the ticket
- [ ] Files under `research/` are unchanged
