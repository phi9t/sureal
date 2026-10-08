# 01: Blob store with in-memory and local adapters

**What to build:** A researcher can store a file as a blob under a blob key, fetch it back with its digest checked, and ask whether it exists, through one blob store interface, without knowing what sits underneath. This ticket delivers the interface, its five failure kinds, its deadline and retry behaviour, the in-memory adapter (with injectable faults) and the local-file-system adapter, plus one contract suite that both adapters pass in the default test run. See the spec `.scratch/blob-store/spec.md` and autonomy ADR 0002.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] A new `blob_store` concept exists with `put(key, file) -> {key, sha256, bytes}`, `get(key, dest, sha256)` and `exists(key)`, and nothing else on its interface (no list, delete or overwrite)
- [x] `put` reads the blob back before returning; identical bytes under an existing key succeed without change; different bytes raise Conflict
- [x] Failure kinds Missing, Conflict, Corrupt, Unauthenticated (naming the refresh script) and Unavailable are the only failures callers can see
- [x] Deadlines are computed inside the store from size (base plus bytes over a minimum throughput); every operation is retried up to three attempts with backoff on timeout or transient failure, then raises Unavailable
- [x] The in-memory adapter supports injected delay, transient failure and authentication failure so deadline and retry behaviour is testable offline
- [x] The local adapter stores blobs under a root directory, refuses symlinks and keys that escape the root
- [x] One contract suite, written against the interface only, runs against both adapters in the default Bazel run and covers every behaviour above
- [x] Default CPU suite, `--config=cuda` suite and `//parallax/...` pass with counts recorded

## Comments

Done 2026-10-08:

- Added `autonomy/blob_store` with the `BlobStore` facade, in-memory adapter, local-file adapter, shared key validation, write-once conflict handling, readback verification, typed failure mapping, and injectable deadline/backoff clock.
- Added `autonomy/blob_store:contract_test`, a shared interface-only contract suite covering in-memory and local adapters, readback, idempotent same-byte puts, conflicting puts, digest mismatch, missing blobs, exists, key validation, local symlink refusal, retry/deadline behavior and authentication failures naming `autonomy/resources/refresh-hdfs-auth.sh`.
- Added focused `autonomy/blob_store:core_test` coverage for readback-corruption mapping and backend error wrapping that the interface-only adapter contract cannot directly force.
- Verification:
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed: 157 out of 157 tests. New count is 157.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed: 17 out of 17 tests.
  - GPU 1 was free, so `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed: 28 out of 28 tests.
