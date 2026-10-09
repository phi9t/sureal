# 03: Source snapshots through the blob store

**What to build:** Every gate and study stage stores and fetches its source snapshot through the blob store, content-addressed under `artifacts/source-snapshots/<sha256>`, so the most critical evidence path gains the store's deadlines, retries and typed failures. Existing receipts keep resolving.

**Blocked by:** 02

**Status:** done

- [x] Snapshot creation stores the archive through the blob store and new receipts carry the new store descriptor and blob key
- [x] The existing local snapshot store is replaced by the blob store's local adapter; offline tests inject an in-memory or local store, never a fake command runner
- [x] Every caller that rebuilt a store from a receipt uses the descriptor factory; receipts written before this change still resolve and verify (proved by a test over at least one retained receipt of each schema)
- [x] The snapshot store no longer calls the Waystone tool directly
- [x] Default CPU suite, `--config=cuda` suite and `//parallax/...` pass with counts recorded; the `requires_hdfs` contract suite passes once

## Comments

Done 2026-10-09:
- Source snapshots now store archives through `BlobStore` under `artifacts/source-snapshots/<sha256>` and new receipts include the blob-store descriptor plus `source_snapshot_blob` `{key, sha256, bytes}`.
- `LocalSnapshotStore` and `HdfsSnapshotStore` remain as compatibility wrappers, but delegate storage to the local-file and Waystone blob adapters. Receipt reconstruction goes through the descriptor factory; legacy string/local/HDFS receipt shapes still resolve.
- Added retained schema-1 and schema-2 receipt fixtures plus archive bytes copied from retained evidence into `autonomy/evidence/testdata/retained_source_snapshots/` for hermetic compatibility coverage.
- Updated source-snapshot callers/tests that inspect local snapshot archives to use the blob-key path, and forwarded `source_snapshot_blob` through architecture experiment receipts.
- Focused tests: 9/9 source snapshot neighbor targets passed.
- Live HDFS contract: `PYTHONPATH=autonomy SUREAL_BLOB_STORE_CONTRACT_ADAPTER=waystone SUREAL_BLOB_STORE_CONTRACT_RUN_ID=20261009T034634Z python3 autonomy/blob_store/contract_test.py` passed 13/13 tests; keys were under `tmp/blob-store-contract/20261009T034634Z/...`. The Bazel wrapper form failed before HDFS writes because the sandboxed test environment could not read the external Waystone tool path for pinning.
- Required gates: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed 176/176 tests; `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed 17/17 tests; `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed 29/29 tests.
