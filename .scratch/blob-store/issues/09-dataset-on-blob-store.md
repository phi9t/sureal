# 09: Dataset scripts on the blob store

**What to build:** Cohort acquisition, scene and sidecar publishing, and staged-source fetching in the dataset concept store and fetch through the blob store under the `datasets/` area.

**Blocked by:** 02

**Status:** done

- [x] No dataset module builds a Waystone command line
- [x] New blob keys use the `datasets/` area; fetches of previously published data resolve old URIs through the descriptor factory
- [x] Tests use an in-memory blob store where they previously faked commands
- [x] Default CPU suite, `--config=cuda` suite and `//parallax/...` pass with counts recorded

## Comments

Done 2026-10-09:

- Dataset acquisition, staged-source fetching, scene publication, and sidecar publication now store and fetch new artifacts through a `BlobStore` with `datasets/` blob keys and retained store descriptors.
- Existing HDFS URI receipts remain readable through the descriptor factory/legacy recovery path. Remaining `hdfs_*`, `hdfs-put`, `hdfs-download`, and `transfer_command` references are compatibility or test-only paths for retained evidence.
- Verification: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed 176 out of 176 tests.
- Verification: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed 17 out of 17 tests.
- Verification: `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed 29 out of 29 tests after GPU 1 was observed free.
