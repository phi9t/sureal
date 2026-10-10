# 01: Scientific retention planner, and the cohort counts each file once

**What to build:** A dry-run-first planner that says, for each child of `scientific-processing`:
- which class it is in;
- why;
- its inode-unique size;
- what releasing or cleaning it would project against the working cap.

The cohort driver's working total switches to inode-unique accounting.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] **Live first.** The planner's dry run on this host's real `scientific-processing` is recorded in Comments: per-class counts and bytes, the top entries, and the projected total against the cap. It is reviewed for mistakes: any protected or referenced child shown as reclaimable is a bug, and is fixed before anything else.
- [x] **Classes:**
  - protected, using the imported lists;
  - live-referenced, by state, admission or retention receipts;
  - released with leftovers;
  - published but not released;
  - unpublished;
  - stray log.

  Each verdict names the evidence file behind it.
- [x] **`--apply`:**
  - it only deletes stray logs and leftovers of runs already released, after re-verifying their digests;
  - it takes the sustained controller lock;
  - it refuses paths outside `scientific-processing`, and anything under an evidence root;
  - it writes its own receipt outside `scientific-processing`.

  It is not run on the real cache in this ticket.
- [x] **Published but not released:** these are reported with the exact `publish_scientific_directory --release` command. The planner never unlinks them.
- [x] **`scientific_cohort.py` counts each file once.** Its working total and the budget checks it shares use inode-unique bytes (like `unique_payload_bytes`), with a test where hard links are counted once. Retained receipts are unchanged.
- [x] **Tests:**
  - every class, in fixtures;
  - every reference form;
  - an apply that refuses protected or referenced children;
  - dry run as the default.
- [x] **Gates pass:** CPU, parallax, and CUDA on GPU 1 when it is free. Counts recorded.

## Comments

### 2026-10-10 Done

Implemented `autonomy/retention/scientific_retention_planner.py` and tests, exposed the planner binary in `autonomy/retention/BUILD.bazel`, and switched `autonomy/studies/scientific_cohort.py` to use inode-unique `unique_payload_bytes` for its working total.

Live dry-run on the real host cache was run without `--apply`:

```
PYTHONPATH=autonomy python3 -m retention.scientific_retention_planner --top 40
```

Output was recorded under `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/rq01-retention-planner-20261009T234238Z/tmp/retention-live-final.GCyFu3/`.

Counts and bytes from the final dry-run:

```
working_total_bytes=13032379179 (12.1 GiB)
working_cap_bytes=21474836480 (20.0 GiB)
projected_after_eligible_cleanup_bytes=13032240324 (12.1 GiB)
eligible_reclaimable_bytes=138855 (135.6 KiB)
live-referenced: count=98 bytes=6965920823 (6.5 GiB)
protected: count=15 bytes=9796099232 (9.1 GiB)
stray-log: count=32 bytes=138855 (135.6 KiB)
unpublished: count=45 bytes=31528833 (30.1 MiB)
```

Top entries reviewed from the live dry-run: `cohort-v1` was live-referenced by receipt evidence; `balanced16-sustained-baseline-controller20261003a`, the two `resource-retention-balanced16-sustained-baseline-controller20261003a-shared-*` entries, `cohort16-baseline-balanced20261002a`, `balanced16-native-v2`, `balanced16-labels-v2`, and other `balanced16-sustained-*` entries were protected by the imported publish-scientific-directory policy; all had `reclaimable=0`. The only reclaimable entries were top-level `*.log` stray logs. The real dry-run had no published-but-unreleased or released-with-leftovers children; both classes are covered by fixtures. No `--apply` was run on the real cache.

Focused checks:

```
PYTHONPATH=autonomy python3 -m unittest autonomy.retention.scientific_retention_planner_test autonomy.studies.scientific_cohort_test
Ran 11 tests in 0.053s
OK

./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/retention:scientific_retention_planner_test //autonomy/studies:scientific_cohort_test
Executed 2 out of 2 tests: 2 tests pass.
```

Required gates:

```
./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...
Executed 189 out of 189 tests: 189 tests pass.
```

The autonomy count is 189 rather than the ticket's base 188 because this ticket adds `//autonomy/retention:scientific_retention_planner_test`.

```
./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...
Executed 17 out of 17 tests: 17 tests pass.
```

GPU 1 precheck:

```
nvidia-smi --query-gpu=index,uuid,memory.used --format=csv,noheader,nounits
1, GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619, 4

nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory --format=csv,noheader,nounits
# no compute process on GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619
```

CUDA gate:

```
CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...
Executed 30 out of 30 tests: 30 tests pass.
```

Shared-file overlap: `autonomy/retention/BUILD.bazel` was touched only to add the new planner binary through the existing retention binary list.
