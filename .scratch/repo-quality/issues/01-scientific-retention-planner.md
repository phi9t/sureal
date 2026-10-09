# 01: Scientific retention planner, and the cohort counts each file once

**What to build:** A dry-run-first planner that says, for each child of `scientific-processing`:
- which class it is in;
- why;
- its inode-unique size;
- what releasing or cleaning it would project against the working cap.

The cohort driver's working total switches to inode-unique accounting.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] **Live first.** The planner's dry run on this host's real `scientific-processing` is recorded in Comments: per-class counts and bytes, the top entries, and the projected total against the cap. It is reviewed for mistakes: any protected or referenced child shown as reclaimable is a bug, and is fixed before anything else.
- [ ] **Classes:**
  - protected, using the imported lists;
  - live-referenced, by state, admission or retention receipts;
  - released with leftovers;
  - published but not released;
  - unpublished;
  - stray log.

  Each verdict names the evidence file behind it.
- [ ] **`--apply`:**
  - it only deletes stray logs and leftovers of runs already released, after re-verifying their digests;
  - it takes the sustained controller lock;
  - it refuses paths outside `scientific-processing`, and anything under an evidence root;
  - it writes its own receipt outside `scientific-processing`.

  It is not run on the real cache in this ticket.
- [ ] **Published but not released:** these are reported with the exact `publish_scientific_directory --release` command. The planner never unlinks them.
- [ ] **`scientific_cohort.py` counts each file once.** Its working total and the budget checks it shares use inode-unique bytes (like `unique_payload_bytes`), with a test where hard links are counted once. Retained receipts are unchanged.
- [ ] **Tests:**
  - every class, in fixtures;
  - every reference form;
  - an apply that refuses protected or referenced children;
  - dry run as the default.
- [ ] **Gates pass:** CPU, parallax, and CUDA on GPU 1 when it is free. Counts recorded.
