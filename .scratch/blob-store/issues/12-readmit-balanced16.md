# 12: Re-admit balanced16 on the blob store

**What to build:** The balanced16 sweep's admission binds the code it will actually run after the migration: a live implementation gate whose receipts cite blob keys and the new store descriptor, recorded in the journal.

**Blocked by:** 11, semantic-layout ticket 29 (its rootfs rebuild may change the lock this admission binds), and launch-plans 08 (the sustained run moves onto launch plans, so balanced16 is re-admitted once after both migrations); strict-metrics tickets 03 and 06 (they change the sustained scorer, metric audit and admission, so this one re-admission covers them)

**Status:** ready-for-human

- [ ] A live admission runs on GPU 1 only, inside its systemd scope, with the storage gate passing; any GPU sharing is recorded
- [ ] Every emitted receipt verifies against its source snapshot, rootfs lock and blobs read back through the blob store
- [ ] A journal entry records the re-admission and what changed since ticket 27's admission, published through the journal spec with readback
- [ ] Default CPU suite, `--config=cuda` suite and `//parallax/...` pass with counts recorded
