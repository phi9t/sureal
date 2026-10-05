# 13: Concept batch: `insula` and `evidence`

**What to build:** Sandbox entry and the evidence tooling live in their concept directories. A contributor finds the Insula launcher, rootfs identity checks and the first-milestone probes under `insula`, and the journal, tracker and snapshot code under `evidence`.

**Blocked by:** 11 (The architecture runner pins a source snapshot), 12 (The sustained-run guard verifies a snapshot)

**Status:** ready-for-agent

- [x] Scope: the Insula entry and launch plan, rootfs identity, the M0 probe and receipt code, staging leases; the research journal, tracker, projection and publication; the pin report tool
- [x] The wrapper and the live-gate launcher share one sandbox-plan implementation
- [x] Every module in scope lives in its concept directory and is imported by package path; no `sys.path` manipulation remains in the moved code
- [x] Each moved test sits beside its module as `foo_test.py` and is a Bazel test target
- [x] Bazel visibility lets only the concepts above this one depend on it
- [x] File digests and regular-file checks in the moved code come from the evidence module, not local copies
- [x] The same test modules pass through the wrapper as before the batch, and the pin report for the batch is attached to the ticket
- [x] Files under `research/` are unchanged
