# 27: Re-admit the balanced16 sweep

**What to build:** The preregistered four-recipe balanced16 sweep is bound to the new paths, sources and rootfs, so it can resume. Running the sweep is separate work.

**Blocked by:** 04 (Torch tests run under Bazel in the GPU rootfs), 10 (Source snapshots are stored in HDFS), 26 (Remove the old structure)

**Status:** done

- [x] The sweep's recipes, frames and anchor templates are unchanged from the preregistration
- [x] Each recipe's admission pins a source snapshot stored in HDFS and the new rootfs digest
- [x] Every runtime-lock check listed in ticket 01 is re-admitted on the new images, except M0 and the three semantic-recovery rows, which are split to ticket 29
- [x] A live gate executes the admitted candidate in the new rootfs and its receipt verifies against the snapshot
- [x] The journal records the re-admission and what changed since the original admission
- [x] The task index states the sweep's new status

## Comments

Closed on the coordinator's review of `docs/ticket27/execution-report.md`.

- Live admission `t27f20261008T081353Z` passed all 14 stages (exit 0, 3903.9 s); every receipt replayed against its read-back source snapshot and rootfs lock. GPU 1 was shared with another user's process during part of the run (status `passed_with_gpu_sharing`); the user accepted the run with that caveat recorded.
- Seven runtime-lock checks passed live. M0 (rootfs lock digest mismatch, needs a rebuild) and three semantic-recovery rows (contract-only on synthesized receipts) are split to ticket 29.
- Journal entry 130 records the re-admission; published to `hdfs://harunava/user/tiger/waystone/sureal/runs/perception-research-journal/snapshot-research-journal-publication-4b54270c65fd46aab5776824c4a20f98`, manifest sha256 `52516d9f…c654`, read back independently by the coordinator.
- Sweep status: re-admitted for engineering use; running the sweep is separate work.
