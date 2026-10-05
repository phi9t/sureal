# 14: Concept batch: `dataset`

**What to build:** Everything about reading and storing Waymo data lives under `dataset`: readers, records, the scientific cohort's components and sidecars, archives and eviction.

**Blocked by:** 13 (Concept batch: `insula` and `evidence`)

**Status:** ready-for-agent

- [ ] Scope: the TFRecord reader, sensor records, shard inventory, source integrity, staged sources, scientific dataset, components, sidecars and their readers and validators, scene and component archives, eviction policies, cohort selection, checkpoint and resume, and the cloud-storage setup commands
- [ ] Every module in scope lives in its concept directory and is imported by package path; no `sys.path` manipulation remains in the moved code
- [ ] Each moved test sits beside its module as `foo_test.py` and is a Bazel test target
- [ ] Bazel visibility lets only the concepts above this one depend on it
- [ ] File digests and regular-file checks in the moved code come from the evidence module, not local copies
- [ ] The same test modules pass through the wrapper as before the batch, and the pin report for the batch is attached to the ticket
- [ ] Files under `research/` are unchanged
