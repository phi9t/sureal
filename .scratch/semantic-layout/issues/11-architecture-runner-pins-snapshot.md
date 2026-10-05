# 11: The architecture runner pins a source snapshot

**What to build:** A researcher runs an architecture experiment and its receipts pin a source snapshot taken by the evidence module. Verifying the run checks the snapshot, not the working tree. This is the first real gate on the new evidence model.

**Blocked by:** 09 (Evidence module: snapshot, fetch and verify)

**Status:** ready-for-agent

- [ ] A new run records the snapshot digest and the build target it was taken from
- [ ] Verifying and resuming a run check the recorded snapshot and succeed after an unrelated source file is edited
- [ ] Verifying fails when the snapshot's bytes differ from the recorded digest
- [ ] Verification without a run identifier, which compared tracked receipts with the working tree, is removed and the user guide says so
- [ ] The runner's own freezing code is replaced by the evidence module
- [ ] Receipts of earlier runs are unchanged
