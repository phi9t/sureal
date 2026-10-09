# 02: Waystone adapter and store descriptors

**What to build:** Production code can store and fetch blobs in HDFS through Waystone by naming only blob keys; Waystone supplies the project root. A receipt's store descriptor rebuilds the right adapter, and receipts written before this change (absolute `hdfs://` URIs, prefix-style descriptors) still resolve to blob keys.

**Blocked by:** 01

**Status:** done

- [x] A Waystone adapter passes the contract suite from ticket 01; that run is tagged `requires_hdfs`, excluded by default, and is run once live against a scratch area with results recorded in the ticket
- [x] The adapter resolves the project root from Waystone's layout profile; no storage root, cluster or user appears in sureal code
- [x] The adapter verifies the pinned Waystone tool digests before each operation, kills the whole process group when a deadline passes, and classifies missing and authentication output into the failure kinds; no exit code or stderr text escapes
- [x] Store descriptors are `{kind, project}` for Waystone and `{kind, root}` for local; one factory builds an adapter from a descriptor
- [x] The factory accepts old prefix-style descriptors, and an old absolute URI is turned into a blob key by stripping Waystone's storage root
- [x] Default CPU suite, `--config=cuda` suite and `//parallax/...` pass with counts recorded

## Comments

Done 2026-10-09:

- Added `WaystoneBlobAdapter` behind the existing `BlobStore` interface. It resolves the project root from `waystone layout-profile --project sureal --json`, invokes `put`, `get` and `ls` with `--auth-source token-file`, verifies Waystone tool pins before each primitive operation, and supplies `autonomy/resources/refresh-hdfs-auth.sh` as the unauthenticated recovery action.
- Added process-group timeout enforcement in the adapter: blocking Waystone subprocesses run in a new session, use the blob-store operation deadline as the `communicate()` timeout, and are killed by process group on expiry.
- Added output classification for missing, conflict and authentication failures without exposing Waystone exit codes or stderr in public blob-store errors. Waystone `ls` JSON with `count: 0` is treated as a missing blob.
- Added descriptor helpers: new descriptors are `{"kind": "waystone", "project": "sureal"}` and `{"kind": "local", "root": ...}`; legacy `{"kind": "hdfs", "prefix": ...}` descriptors are accepted for old receipts; absolute HDFS URIs are converted to blob keys by stripping the resolved Waystone project root or the legacy prefix.
- Added offline adapter tests using a fake Waystone executable invoked by the real subprocess path. The fake covers layout resolution, put/get/ls behavior, descriptor factories, tool-pin changes, typed output classification and process-group timeout killing. No subprocess monkeypatching is used.
- Added `//autonomy/blob_store:waystone_contract_test`, tagged `manual` and `requires_hdfs`, so the live HDFS contract is opt-in and excluded from the default `//autonomy/...` run.
- Live HDFS contract run:
  - Command: `TMPDIR=... PYTHONPATH=autonomy SUREAL_WAYSTONE=$HOME/workspace/waystone/scripts/waystone SUREAL_BLOB_STORE_CONTRACT_ADAPTER=waystone SUREAL_BLOB_STORE_CONTRACT_RUN_ID=20261009T023614Z python3 autonomy/blob_store/contract_test.py`
  - Result: passed, 13 tests in 41.826s.
  - HDFS write prefix: `tmp/blob-store-contract/20261009T023614Z/...`; no delete operation was used.
  - Keys exercised under that prefix included `runs/resource-closures/run-20261008/checkpoint/archive-000.tar.gz`, `artifacts/source-snapshots/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`, `datasets/scientific-cohort/run-20261008/components/scene.tar`, `checkpoints/child/run-20261008/model/checkpoint.pt`, `runs/symlinked-caller/run-20261008/output/blob.bin`, `runs/existence/run-20261008/output/blob.bin`, `runs/deadline/run-20261008/output/blob.bin` and retry/auth contract keys.
- Verification:
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/blob_store:all_tests` passed: 3 out of 3 tests.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed: 174 out of 174 tests. New count is 174. One prior full rerun exposed a transient pre-existing `/proc/<pid>/stat` race in `//autonomy/studies:architecture__experiment_runner_test`; that target passed on immediate focused rerun before the final full-suite pass.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed: 17 out of 17 tests.
  - GPU 1 was free (`4 MiB` used, `0%` utilization, no `pmon` process), so `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed: 29 out of 29 tests.
