# 08: Scientific-directory and symlink-audit publishers on the blob store

**What to build:** Publishing a scientific directory and publishing a symlink audit go through the publication module or the blob store, so existence is never inferred from listing output.

**Blocked by:** 04

**Status:** done

- [x] Both publishers store through the publication module or the blob store; their bespoke Waystone client is gone
- [x] No code parses "Found N items" or any listing output
- [x] Their tests use an in-memory blob store instead of a fake Waystone
- [x] Default CPU suite, `--config=cuda` suite and `//parallax/...` pass with counts recorded

## Comments

Done 2026-10-09:

- Migrated `retention.publish_scientific_directory.publish` to build a `PublicationSpec` and publish/audit through `retention.publication` using blob keys under `runs/<namespace>/<run-id>/scientific-directory/...`.
- Removed the scientific-directory bespoke Waystone client and its `Found N items` listing parser; live defaults now build a `BlobStore` from the Waystone store descriptor, while tests inject `BlobStore(InMemoryBlobAdapter(...))`.
- Migrated `retention.publish_symlink_audit.publish` to store its symlink-preserving archive and manifest directly through the blob store under `runs/<namespace>/<run-id>/symlink-audit/...`, with a small receipt and a new `audit(receipt)` readback path.
- Updated scientific-directory and symlink-audit tests to use the in-memory blob store, assert the compact blob-key receipt shape, preserve symlink archive/readback behavior, and prove changed repeat publication is refused by blob-store conflicts.
- No live scientific-directory publication was run. No live HDFS writes were performed.
- Verification:
  - Red check before implementation: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/retention:publish_scientific_directory_test //autonomy/retention:publish_symlink_audit_test` failed because `publish(..., store=...)` was unsupported and `retention.publish_symlink_audit.audit` did not exist.
  - Focused check: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/retention:publish_scientific_directory_test //autonomy/retention:publish_symlink_audit_test` passed: 2 out of 2 tests.
  - Retention suite: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/retention:all_tests` passed: 12 out of 12 tests.
  - Listing parser scan: `rg -n "Found\\s+[0-9N]+\\s+items|FOUND_ITEMS|_hdfs_ls_indicates|hdfs_ls_indicates|listing output" autonomy --glob '*.py' --glob '!research/**'` returned no matches.
  - Default CPU gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed: 181 out of 181 tests.
  - Parallax gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed: 17 out of 17 tests.
  - GPU 1 check before CUDA: `nvidia-smi` showed GPU 1 at 4 MiB used, 0% utilization and no `pmon` compute process.
  - CUDA gate: `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed: 29 out of 29 tests.
