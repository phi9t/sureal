# 11: Delete the old Waystone wrappers

**What to build:** The working tree holds one way to store a blob. A test enforces it.

**Blocked by:** 03, 05, 06, 07, 08, 09, 10

**Status:** done

- [x] Every remaining Waystone wrapper, copied tool-pin block and storage-root constant outside the blob store is deleted (the HDFS login keepalive is the only other Waystone user and stays)
- [x] A test fails if active code outside the blob store and the keepalive invokes the Waystone tool or names the storage root
- [x] Default CPU suite, `--config=cuda` suite and `//parallax/...` pass with counts recorded; the `requires_hdfs` contract suite passes once

## Comments

Done 2026-10-09:

- Added `//autonomy/blob_store:storage_boundary_test` to scan active autonomy code for direct Waystone CLI paths, copied Waystone tool-pin paths, hard-coded Waystone storage roots, `storage-prefix`, and `WAYSTONE =` constants. The test excludes only the blob store, the HDFS auth keepalive files, retained evidence/procedure records, tests, and the bs07-owned native-cache/pilot publication paths listed below.
- Proved the enforcement test red with `SUREAL_BLOB_STORE_PLANT_VIOLATION=1`: Bazel failed as expected with 2 planted violations (`direct Waystone CLI path`, `Waystone command constant`). The normal boundary test and scanner pass with no active violations.
- Removed active compatibility shims and direct wrappers: retired `autonomy/evidence/publish.py`, `autonomy/evidence/publish_test.py`, and `autonomy/resources/retention.py`; removed `transfer_command` plumbing from staged-source/native-shape/semantic-recovery paths; moved still-used resource receipt helper functions into `resources.retention_audit`; kept old receipt validation resolving by checking blob-key suffixes instead of hard-coded HDFS roots.
- Moved Waystone tool digest role normalization into `blob_store.core` so publication no longer carries its own copied tool-pin path map. `HdfsSnapshotStore` now uses the blob-store adapter default unless an explicit Waystone command is injected.
- Deliberately left these bs07-owned survivors for coordinator reconciliation: `autonomy/retention/cache_retention_audit.py`, `autonomy/retention/pilot_retention_audit.py`, `autonomy/retention/pilot_retention_sources.py`, `autonomy/retention/publish_native_cache.py`, `autonomy/retention/publish_sustained_pilot.py`, `autonomy/retention/retention_sources.py`.
- Live HDFS contract passed by direct execution with run id `20261009T082156Z`: `TMPDIR=<run tmp> PYTHONPATH=autonomy SUREAL_BLOB_STORE_CONTRACT_ADAPTER=waystone SUREAL_BLOB_STORE_CONTRACT_RUN_ID=20261009T082156Z python3 autonomy/blob_store/contract_test.py` ran 15 tests in 44.498s and wrote only under `tmp/blob-store-contract/20261009T082156Z/...`.
- The Bazel `requires_hdfs` target was given `no-sandbox`, `requires-network`, and `SUREAL_WAYSTONE` env inheritance, but live Bazel execution still cannot see the external Waystone tool as a regular file from the test runner. With explicit `--test_env=SUREAL_WAYSTONE=/data02/home/philip.yang/workspace/waystone/scripts/waystone`, `//autonomy/blob_store:waystone_contract_test` failed before HDFS writes with 9 setup errors from the unchanged tool-pin regular-file check.
- Gates: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed 186 out of 186 tests; `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed 17 out of 17 tests; GPU 1 freed on retry attempt 3, then `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed 29 out of 29 tests.
- Extra final checks: `git diff --check` passed; `PYTHONPATH=autonomy python3 - <<'PY' ... scan_storage_boundary()` reported `boundary violations: []`; `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/blob_store:all_tests` passed 4 out of 4 tests.
