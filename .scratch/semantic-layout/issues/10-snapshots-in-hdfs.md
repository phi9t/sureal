# 10: Source snapshots are stored in HDFS

**What to build:** A researcher's source snapshots are stored content-addressed in HDFS, so they outlive the local cache and can be fetched on another machine. Upload uses exact readback, as the journal's publication already does.

**Blocked by:** 09 (Evidence module: snapshot, fetch and verify)

**Status:** ready-for-human

- [ ] An HDFS adapter implements the same storage interface as the local-directory adapter
- [ ] Upload reads the object back and compares bytes before reporting success
- [ ] Uploading a digest that already exists verifies the existing bytes and does not overwrite
- [ ] A snapshot uploaded in one session is fetched and verified in a fresh session with an empty local cache; the live check is recorded
- [ ] Authentication failure and a missing object are reported as distinct, explicit errors
