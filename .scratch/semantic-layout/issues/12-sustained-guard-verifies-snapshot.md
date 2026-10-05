# 12: The sustained-run guard verifies a snapshot

**What to build:** A researcher starts or resumes a sustained run and the guard validates the run's source snapshot. It no longer requires an exact inventory of four directories or that recorded path strings match the current checkout, so adding a file or working from another checkout does not block a run.

**Blocked by:** 09 (Evidence module: snapshot, fetch and verify)

**Status:** ready-for-agent

- [ ] The guard and the resource-source validator accept a run whose snapshot verifies, and reject one whose snapshot is altered or missing
- [ ] Adding an unrelated source file to the tree does not change the outcome
- [ ] The same run is accepted from two different checkout paths
- [ ] The runtime-lock comparison and the anchor-template check keep their current behaviour
- [ ] The host-source freezing helpers used by the controller and the retention publishers are replaced by the evidence module
- [ ] Existing guard tests are rewritten against the new behaviour, not deleted
