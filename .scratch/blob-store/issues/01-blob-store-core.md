# 01: Blob store with in-memory and local adapters

**What to build:** A researcher can store a file as a blob under a blob key, fetch it back with its digest checked, and ask whether it exists, through one blob store interface, without knowing what sits underneath. This ticket delivers the interface, its five failure kinds, its deadline and retry behaviour, the in-memory adapter (with injectable faults) and the local-file-system adapter, plus one contract suite that both adapters pass in the default test run. See the spec `.scratch/blob-store/spec.md` and autonomy ADR 0002.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] A new `blob_store` concept exists with `put(key, file) -> {key, sha256, bytes}`, `get(key, dest, sha256)` and `exists(key)`, and nothing else on its interface (no list, delete or overwrite)
- [ ] `put` reads the blob back before returning; identical bytes under an existing key succeed without change; different bytes raise Conflict
- [ ] Failure kinds Missing, Conflict, Corrupt, Unauthenticated (naming the refresh script) and Unavailable are the only failures callers can see
- [ ] Deadlines are computed inside the store from size (base plus bytes over a minimum throughput); every operation is retried up to three attempts with backoff on timeout or transient failure, then raises Unavailable
- [ ] The in-memory adapter supports injected delay, transient failure and authentication failure so deadline and retry behaviour is testable offline
- [ ] The local adapter stores blobs under a root directory, refuses symlinks and keys that escape the root
- [ ] One contract suite, written against the interface only, runs against both adapters in the default Bazel run and covers every behaviour above
- [ ] Default CPU suite, `--config=cuda` suite and `//parallax/...` pass with counts recorded
