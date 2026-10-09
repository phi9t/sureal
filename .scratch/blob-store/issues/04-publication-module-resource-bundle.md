# 04: Publication module, starting with the resource bundle

**What to build:** A publication is described by a publication spec and published by one module that stages, archives, stores, reads back, writes one manifest blob and audits. The resource bundle that the sustained run publishes in-process is the first spec, end to end.

**Blocked by:** 02

**Status:** done

- [x] The publication module lives in the retention concept; its interface is publish(spec) -> receipt and audit(receipt)
- [x] A publication spec declares payload, inventory, area, child, kind, staging style (hardlink or copy), archive or direct mode, and release flag
- [x] A publication is chunk archives plus one manifest blob listing every chunk's `{key, sha256, bytes}` and the file inventory; blob keys follow `<area>/<child>/<run-id>/<kind>/<name>` with no UUID or digest segment
- [x] The module computes its own disk reservation from what it stages; a repeat publication of the same run and kind with different bytes is refused
- [x] Receipts record only the store descriptor, the pinned tool digest, a readback flag and per-blob `{key, sha256, bytes}`: no command lines, local paths or log paths
- [x] The resource bundle is a spec (hardlink staging, no release); the sustained run publishes through the module and the checkpoint reader reads the new shape
- [x] One audit reads the new shape and rejects a tampered key, digest, size or a missing chunk; tests drive publish and audit with an in-memory blob store
- [x] Default CPU suite, `--config=cuda` suite and `//parallax/...` pass with counts recorded

## Comments

Done 2026-10-09:

- Added `autonomy/retention/publication.py` with a small publication interface: `publish(spec) -> receipt` and `audit(receipt)`. `PublicationSpec` declares payload, inventory, area, child, run id, kind, staging style, archive/direct mode, release flag, store descriptor, pinned tool digest, blob store, staging root and reservation callback.
- Added the resource-bundle spec as hardlink staging, archive mode and no release. The sustained runner now imports the blob-store-backed resource publication wrapper from the retention concept.
- Publications now store chunk archives plus one manifest blob. Blob keys are deterministic: `<area>/<child>/<run-id>/<kind>/<name>`, for example `runs/perception-resource-closures/<run-id>/checkpoint/archive-000.tar.gz`; there is no UUID or digest segment.
- Receipts record only the store descriptor, pinned tool digest, `verified_by_readback` and per-blob `{key, sha256, bytes}` records. Local paths, command lines and log paths stay out of the new receipt.
- Added in-memory blob-store tests for publish/audit, disk reservation, deterministic chunk keys, conflicting repeat publication with changed bytes, and audit rejection for tampered key, digest, size and missing chunk.
- Updated the checkpoint publication reader so new resource publication receipts validate through blob-store readback while old resource publication receipts still validate through the legacy path.
- No live sustained run was executed. No live HDFS writes were performed.
- Verification:
  - Red check before implementation: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/retention:publication_test //autonomy/resources:checkpoint_blob_publication_test` failed because `retention.publication` did not exist and the checkpoint reader expected the legacy `kind/source_inventory/hdfs_prefix` receipt shape.
  - Focused compatibility: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/retention:all_tests //autonomy/resources:all_tests //autonomy/training_execution:run_sustained_test` passed: 37 out of 37 tests.
  - Post-refactor focused check: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/retention:publication_test //autonomy/resources:checkpoint_blob_publication_test //autonomy:source_snapshot_targets_test //autonomy/training_execution:run_sustained_test` passed: 4 out of 4 tests.
  - Default CPU gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed: 178 out of 178 tests.
  - Parallax gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed: 17 out of 17 tests.
  - GPU 1 check before CUDA: attempts 1-4 showed GPU 1 busy; attempt 5 at 2026-10-09T04:40:10Z showed GPU 1 at 4 MiB used, 0% utilization and no `pmon` process.
  - CUDA gate: `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed: 29 out of 29 tests.

Review 1 fixes 2026-10-09:

- Receipt tool pins now normalize absolute Waystone tool paths into stable role names (`waystone-cli`, `waystone-binary`, `libhdfs-client`, `hdfs-bin`) before writing `tool_sha256`; receipt normalization rejects path-like tool keys while keeping role-to-digest pairs auditable.
- Added receipt sanitation coverage asserting no receipt key or string value contains a path separator except blob key values.
- `_write_archive` now streams staged files into tar members with `archive.addfile(info, fileobj)` instead of reading each member into memory.
- `_archive_inventory` now hashes extracted tar members with fixed-size reads and checks the streamed byte count against the tar member size.
- Blob-store typed failures from audit readback (`Missing`, `Corrupt`, `Unauthenticated`, `Unavailable`, `Conflict`) now propagate unchanged; `ValueError` remains for malformed receipt, manifest, digest and byte-count shapes.
- Verification:
  - Review red check: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/retention:publication_test` failed for path-keyed `tool_sha256`, whole-file archive member reads, unbounded archive audit reads and flattened `Unauthenticated`.
  - Focused review check: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/retention:publication_test //autonomy/resources:checkpoint_blob_publication_test //autonomy:source_snapshot_targets_test //autonomy/training_execution:run_sustained_test` passed: 4 out of 4 tests.
  - Default CPU gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed: 178 out of 178 tests.
  - Parallax gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed: 17 out of 17 tests.
  - GPU 1 check before CUDA: `nvidia-smi` showed GPU 1 UUID `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619`, 4 MiB used, 0% utilization and no `pmon` compute process.
  - CUDA gate: `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed: 29 out of 29 tests.
