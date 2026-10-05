# 27: Re-admit the balanced16 sweep

**What to build:** The preregistered four-recipe balanced16 sweep is bound to the new paths, sources and rootfs, so it can resume. Running the sweep is separate work.

**Blocked by:** 04 (Torch tests run under Bazel in the GPU rootfs), 10 (Source snapshots are stored in HDFS), 26 (Remove the old structure)

**Status:** ready-for-human

- [ ] The sweep's recipes, frames and anchor templates are unchanged from the preregistration
- [ ] Each recipe's admission pins a source snapshot stored in HDFS and the new rootfs digest
- [ ] Every runtime-lock check listed in ticket 01 is re-admitted on the new images
- [ ] A live gate executes the admitted candidate in the new rootfs and its receipt verifies against the snapshot
- [ ] The journal records the re-admission and what changed since the original admission
- [ ] The task index states the sweep's new status
