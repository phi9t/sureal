# 12: The sustained-run guard verifies a snapshot

**What to build:** A researcher starts or resumes a sustained run and the guard validates the run's source snapshot. It no longer requires an exact inventory of four directories or that recorded path strings match the current checkout, so adding a file or working from another checkout does not block a run.

**Blocked by:** 09 (Evidence module: snapshot, fetch and verify)

**Status:** done

- [x] The guard and the resource-source validator accept a run whose snapshot verifies, and reject one whose snapshot is altered or missing
- [x] Adding an unrelated source file to the tree does not change the outcome
- [x] The same run is accepted from two different checkout paths
- [x] The runtime-lock comparison and the anchor-template check keep their current behaviour
- [x] The host-source freezing helpers used by the controller and the retention publishers are replaced by the evidence module
- [x] Existing guard tests are rewritten against the new behaviour, not deleted

## Comments

Built snapshot-receipt validation into the sustained-run guard, the resource-source validator, the sustained controller host freezer, and the three retention host-source freezers. New runs materialize source snapshots with `autonomy/evidence/source_snapshot.py`, store content-addressed snapshot objects under run-owned snapshot stores, and validate receipts against the stored snapshot plus the materialized execution package instead of exact live checkout inventories or recorded checkout paths.

Resource checkpoint and resource retention archival paths now read the new snapshot receipt shape. Resource checkpoint inventories archive the snapshot object and materialized source files for the resource layer, native package, and native host closure; they no longer archive `native-current/...` live checkout files or old per-file `original`/`snapshot` paths.

The runtime-lock equality check and sustained anchor-template check are preserved. The controller stage guard also requires the source snapshot store mount and `SUREAL_SOURCE_SNAPSHOT_STORE=/tmp/source-snapshots` for in-sandbox verification.

Verification:
- `./bazelw test //autonomy:resources__test_resource_checkpoint --test_output=errors --cache_test_results=no` -> `Executed 1 out of 1 test: 1 test passes.`
- `./bazelw test //autonomy:evidence__source_snapshot_test //autonomy:cohort__test_sustained_sources //autonomy:cohort__test_sustained_controller_guards //autonomy:resources__test_resource_sources //autonomy:resources__test_resource_stage //autonomy:resources__test_resource_backend //autonomy:resources__test_resource_retention //autonomy:resources__test_resource_checkpoint //autonomy:cohort__test_sustained_retention_sources //autonomy:cohort__test_sustained_checkpoint_retention_sources //autonomy:cohort__test_sustained_pilot_retention_sources --test_output=errors --cache_test_results=no` -> `Executed 11 out of 11 tests: 11 tests pass.`
- `python3 autonomy/tools/pins.py check --base work/semantic-layout/integration` -> `FAIL: 23 changed file(s) cited by retained receipts`.

Pinned files changed, intentionally for this ticket's snapshot guard/source-freezer integration:
- `cohort/admit_sustained.py`: legacy sustained admission now snapshots execution sources and mounts the snapshot store.
- `cohort/checkpoint_retention_sources.py`: checkpoint retention host freezer now uses the evidence snapshot module.
- `cohort/pilot_retention_sources.py`: pilot retention host freezer now uses the evidence snapshot module.
- `cohort/publish_native_cache.py`: native-cache publisher copies audit code from the materialized host snapshot.
- `cohort/publish_sustained_checkpoint.py`: checkpoint publisher copies audit code from the materialized host snapshot.
- `cohort/publish_sustained_pilot.py`: pilot publisher copies audit code from the materialized host snapshot.
- `cohort/retention_sources.py`: native-cache retention host freezer now uses the evidence snapshot module.
- `cohort/sustained_controller_backend.py`: controller guards package and host source snapshots instead of live checkout inventories.
- `cohort/sustained_controller_sources.py`: controller host freezer now uses the evidence snapshot module.
- `cohort/sustained_sources.py`: sustained execution source validation verifies stored source snapshots and keeps runtime-lock equality.
- `cohort/test_sustained_checkpoint_retention_sources.py`: test rewritten for snapshot receipt behavior.
- `cohort/test_sustained_controller_guards.py`: guard tests rewritten for altered/missing snapshots, moved checkouts, unrelated files, runtime, anchors, and stage mounts.
- `cohort/test_sustained_pilot_retention_sources.py`: test rewritten for snapshot receipt behavior.
- `cohort/test_sustained_retention_sources.py`: test rewritten for snapshot receipt behavior.
- `cohort/test_sustained_sources.py`: sustained source tests rewritten for snapshot receipt behavior.
- `resources/backend.py`: resource identity guard validates snapshot-style resource source pins instead of a live path string.
- `resources/checkpoint.py`: checkpoint inventory archives snapshot objects and materialized source files.
- `resources/retention.py`: retention publisher reads archive helpers and resource source pins from snapshot receipts.
- `resources/retention_audit.py`: retention audit validates executed resource helper files against snapshot receipt pins.
- `resources/sources.py`: resource source freezer and validator now use evidence snapshots.
- `resources/test_resource_backend.py`: fixture reads resource code from the materialized source snapshot.
- `resources/test_resource_checkpoint.py`: checkpoint inventory fixture and assertions use snapshot receipts.
- `resources/test_resource_sources.py`: resource source tests rewritten for snapshot receipt behavior.

Reviewer notes:
- The requested legacy pin command under `experiments/waymo-perception/tools/pins.py` is unavailable after the rename, so the renamed `autonomy/tools/pins.py` guard was used.
- `autonomy/evidence/source_snapshot.py` was changed to add materialized-source helpers used by this ticket. It is not listed by the pin guard output because it was introduced by ticket 09 and is not cited by retained receipts on `work/semantic-layout/integration`.
- Ticket 10 owns HDFS snapshot storage; this ticket uses the evidence module's local snapshot store in run-owned paths.
