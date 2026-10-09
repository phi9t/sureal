# 06: Research-journal publication spec

**What to build:** Publishing the research journal, registry, dashboard and evidence snapshots is a direct-files publication spec, so it gains the blob store's deadlines, retries and failure kinds. The evidence concept keeps the journal itself (append, verify) and no longer publishes it.

**Blocked by:** 04

**Status:** done

- [x] The journal publication is a spec in direct mode (files stored as blobs, no archive, no release) under the `runs/` area
- [x] Its receipt replaces the journal's HDFS verification record and verifies by readback; the previous record's bytes are preserved before the first publish under the new spec
- [x] The evidence concept no longer calls the Waystone tool or the publication module; dependencies point downward
- [x] Journal verification still passes on the current journal
- [x] Default CPU suite, `--config=cuda` suite and `//parallax/...` pass with counts recorded

## Comments

Done 2026-10-09:

- Added `retention.publication.research_journal_spec`, a direct-files publication spec under `runs/perception-research-journal/<run-id>/snapshot/`. It stores the registry, dashboard, JSONL journal, rendered journal and immutable `journal-evidence/` snapshots as individual blobs plus one manifest blob; no archive and no release path are used.
- Extended `publish(spec)` and `audit(receipt)` additively for direct mode. Direct receipts keep the existing small publication receipt contract (`store_descriptor`, normalized `tool_sha256`, `verified_by_readback`, blob records only) and audit verifies each direct file through blob-store readback with digest and byte count checks.
- Added `write_research_journal_receipt()` so the first replacement of `autonomy/research/research-journal-hdfs-verified.json` preserves the old HDFS verification record bytes before writing a new blob-store-backed publication receipt. No live journal publish was run and the active HDFS verification record was not edited.
- Preserved the existing HDFS verification record byte-for-byte as `autonomy/research/research-journal-hdfs-legacy-verified.json`. Both active and legacy files have SHA-256 `48ad366dcabf69bd2d9ce5ad8cc891e6afaac659400455cc2fa2169e6de81333`.
- Retired the old `evidence.publish` Waystone wrapper to a compatibility stub and removed it from `autonomy/evidence/README.md`; evidence keeps journal append/verify only. `verify-journal` now reads the active and legacy journal publication record shapes without depending on the retention publication module.
- Red checks before implementation:
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/retention:publication_test //autonomy/evidence:publish_test` failed because `research_journal_spec`/`write_research_journal_receipt` were missing and `evidence.publish` still attempted the old Waystone publication path.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/evidence:tracker_test` failed because `evidence.tracker.verify_journal()` did not exist.
- Focused verification:
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/evidence:tracker_test //autonomy/retention:publication_test //autonomy/evidence:publish_test` passed: 3 out of 3 tests.
  - `PYTHONPATH=autonomy python3 -m evidence.tracker verify-journal` passed: `VERIFIED journal entries 134`.
  - `git diff --check` passed.
- Required gates:
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed: 181 out of 181 tests.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed: 17 out of 17 tests.
  - GPU 1 was free (`4 MiB` used, `0%` utilization, no `pmon` compute process), so `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed: 29 out of 29 tests.
