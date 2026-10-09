# 10: Camera, segmentation and geometry scripts on the blob store

**What to build:** The remaining direct Waystone callers in the camera, segmentation and geometry concepts store and fetch through the blob store.

**Blocked by:** 02

**Status:** done

- [x] No camera, segmentation or geometry module builds a Waystone command line or wraps one in an external `timeout`
- [x] Fetches of previously published data resolve old URIs through the descriptor factory
- [x] Default CPU suite, `--config=cuda` suite and `//parallax/...` pass with counts recorded

## Comments

Done 2026-10-09:

- Migrated camera scientific publication archive and manifest transfer to `BlobStore` operations with store descriptors and blob-key receipts. Camera eviction now accepts the new `archive_blob` receipt shape while preserving old `archive_hdfs_uri` receipts by resolving them through a descriptor-backed adapter.
- Migrated segmentation derived-archive staging, including the aligned variant, to `BlobStore.get` with in-memory store injection in offline tests. New transfer evidence records `blob_key`, `store_descriptor` and `verified_by_readback`; legacy `hdfs_uri` is retained only when the input receipt was legacy-shaped.
- Replaced geometry native-shape transfer's direct Waystone subprocess/deadline wrapper with a blob-store fetch helper and CLI that requires an expected SHA-256. Legacy HDFS sources are converted to blob keys before fetching.
- Source audit: `rg` found no remaining production `WAYSTONE` command constants, `subprocess.Popen`, or external `timeout --kill-after` wrappers in `autonomy/camera`, `autonomy/segmentation` or `autonomy/geometry`. Remaining HDFS strings in those concepts are legacy receipt fields, compatibility stage names, or local Waystone cache path references.
- Verification:
  - Focused camera receipt validation passed after the final `verified_by_readback` receipt-shape update: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/camera:blob_publication_test //autonomy/camera:camera_eviction_test` passed: 2 out of 2 tests.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed: 177 out of 177 tests.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed: 17 out of 17 tests.
  - GPU 1 was initially busy at 04:14 UTC and 04:24 UTC, remained busy at retry 2, then cleared at retry 3 (`2026-10-09T04:44:52Z`, `4 MiB`, `0%`, no running processes). `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed: 29 out of 29 tests.
