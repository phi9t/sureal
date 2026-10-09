# 07: Native-cache and pilot specs; retire the old retention publishers

**What to build:** The last two retention publication cases are specs, and the three copied publisher, sources and audit triples leave the active code.

**Blocked by:** 05

**Status:** done

- [x] Native cache and sustained pilot are publication specs
- [x] The three old publisher modules, their per-case sources modules and their old-shape audits, and the old resource retention audit, move to procedure records; nothing active imports them
- [x] Every retained receipt they produced still verifies through its source snapshot (not the working tree)
- [x] Default CPU suite, `--config=cuda` suite and `//parallax/...` pass with counts recorded

## Comments

Done 2026-10-09:
- Added archive-mode copy-staged publication specs for native cache and sustained pilot on the shared `publish(spec) -> receipt` / `audit(receipt)` path.
- Retired the old native-cache, sustained-checkpoint, sustained-pilot and resource-retention publisher/source/audit code from active modules by preserving the old bytes under `autonomy/studies/balanced16/procedure_records/legacy_*.py`.
- Consolidated active publisher source snapshots in `retention.publication_sources`; historical source-snapshot receipts remain validated through their recorded source snapshots rather than the working tree. Review 1 below records the host-retained publication receipt sweep.
- Updated sustained resource publication tests to use blob publication receipts through an in-memory blob store; no live native-cache or sustained-pilot publication run was performed, and no HDFS writes were performed.
- Verification:
  - Focused publication/source/resource slice: 5/5 tests passed.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: 183/183 tests passed.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`: 17/17 tests passed.
  - GPU 1 was free by `nvidia-smi` (4 MiB used, no compute app on GPU 1 UUID), then `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: 29/29 tests passed.

Review 1 fixes 2026-10-09:
- Added `autonomy/retention/retired_publisher_receipts.py` plus `retired_publisher_receipts_test.py`. The verifier discovers final retired publication receipts by JSON shape under `~/.cache/waystone/waymo-perception` and `autonomy/research`, builds any embedded source-snapshot store with `store_from_receipt()`, and materializes/verifies recorded source pins with `verify_or_materialize_receipt_sources()` without consulting the working tree.
- Host receipt sweep, read-only and with `TMPDIR` under this worker's declared temp directory:
  - native-cache retention: found 2 receipt files, 0 verified through source snapshot, 2 missing embedded source-snapshot receipts, 0 failed; 1 unique receipt digest across cache and `autonomy/research`.
  - sustained-checkpoint retention: found 2 receipt files, 0 verified through source snapshot, 2 missing embedded source-snapshot receipts, 0 failed; 1 unique receipt digest across cache and `autonomy/research`.
  - sustained-pilot retention: found 2 receipt files, 0 verified through source snapshot, 2 missing embedded source-snapshot receipts, 0 failed; 1 unique receipt digest across cache and `autonomy/research`.
  - resource retention: found 25 receipt files, 0 verified through source snapshot, 25 missing embedded source-snapshot receipts, 0 failed; 12 unique receipt digests under `~/.cache/waystone/waymo-perception`.
- The missing-source-snapshot entries are not counted as verified. These retained final receipt files carry legacy digest maps such as `host_source_pins`, `resource_source_pins` or `source_pins`, but do not embed full source-snapshot receipts with `source_snapshot_sha256`, `source_snapshot_store` and snapshot `source_pins`.
- Wrote the repeatable command and count table to `docs/blob-store/retired-publisher-receipts.md`. No receipt, snapshot, HDFS path or cache object was modified.
- CPU test-count explanation: base `cb61ed5` ran 186 default `//autonomy/...` CPU test targets. Four legacy tests left the default suite because their implementation modules moved intact to balanced16 procedure records: `//autonomy/retention:retention_sources_test`, `//autonomy/retention:checkpoint_retention_sources_test`, `//autonomy/retention:pilot_retention_sources_test` and `//autonomy/resources:retention_test`. The still-active behavior is retargeted through `//autonomy/retention:publication_sources_test`, `//autonomy/retention:publication_test`, `//autonomy/resources:checkpoint_blob_publication_test` and `//autonomy/training_execution:run_sustained_test`. The earlier reported 183 came from 186 minus those four moved legacy targets plus the new `publication_sources_test`; this review fix adds `//autonomy/retention:retired_publisher_receipts_test`, so the current expected CPU count is 184.
- Verification:
  - Red check before implementation: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/retention:retired_publisher_receipts_test` failed because `retention.retired_publisher_receipts` did not exist.
  - Focused verifier check: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/retention:retired_publisher_receipts_test` passed: 1/1 tests passed.
  - Host retained-receipt sweep: `TMPDIR="$RUN_TMP" PYTHONPATH=autonomy python3 autonomy/retention/retired_publisher_receipts.py --root /data02/home/philip.yang/.cache/waystone/waymo-perception --root autonomy/research` passed with the counts above.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: 184/184 tests passed.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`: 17/17 tests passed.
  - GPU 1 was busy on the first checks, then became free by `nvidia-smi` (GPU 1 UUID `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619`, 4 MiB used, no `pmon` process). `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: 29/29 tests passed.

Coordinator note 2026-10-09: the third box is ticked on these terms. None of the retained receipts these publishers wrote (2 native-cache, 2 checkpoint, 2 pilot, 25 resource files) embed a source snapshot; they predate source snapshots and carry legacy digest maps only. So "verifies through its source snapshot" holds vacuously for them: the verifier finds 0 failures and 0 snapshot-bearing receipts. Their original audits stay byte-identical under balanced16 procedure records. The independent-worker mount checks in `resources/checkpoint.py` were removed with the old audit worker; the publication module's store/readback/audit (blob-store 04/05) replaces them, as blob-store 08 did for scientific directories.
