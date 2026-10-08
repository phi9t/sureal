# 12: Re-admit balanced16 on the blob store

**What to build:** The balanced16 sweep's admission binds the code it will actually run after the migration: a live implementation gate whose receipts cite blob keys and the new store descriptor, recorded in the journal.

**Blocked by:** 11

**Status:** ready-for-human

- [ ] A live admission runs on GPU 1 only, inside its systemd scope, with the storage gate passing; any GPU sharing is recorded
- [ ] Every emitted receipt verifies against its source snapshot, rootfs lock and blobs read back through the blob store
- [ ] A journal entry records the re-admission and what changed since ticket 27's admission, published through the journal spec with readback
- [ ] Default CPU suite, `--config=cuda` suite and `//parallax/...` pass with counts recorded
