# 23: Concept batch: `inspection`

**What to build:** Tools for looking at scenes live under `inspection`: the web viewer, the explorer and the inspection views.

**Blocked by:** 14 (Concept batch: `dataset`), 15 (Concept batch: `geometry`)

**Status:** ready-for-agent

- [ ] Scope: the viewer's exporter and its tests, the explorer's preview and render workers, scene inspection and inspection views
- [ ] The viewer's web front end keeps its own npm toolchain and its run script works from the new location
- [ ] Every module in scope lives in its concept directory and is imported by package path; no `sys.path` manipulation remains in the moved code
- [ ] Each moved test sits beside its module as `foo_test.py` and is a Bazel test target
- [ ] Bazel visibility lets only the concepts above this one depend on it
- [ ] File digests and regular-file checks in the moved code come from the evidence module, not local copies
- [ ] The same test modules pass through the wrapper as before the batch, and the pin report for the batch is attached to the ticket
- [ ] Files under `research/` are unchanged
