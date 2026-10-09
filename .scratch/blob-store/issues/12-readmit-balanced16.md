# 12: Re-admit balanced16 on the blob store

**What to build:** The balanced16 sweep's admission binds the code it will actually run after the migration: a live implementation gate whose receipts cite blob keys and the new store descriptor, recorded in the journal.

**Blocked by:** 11, semantic-layout ticket 29 (its rootfs rebuild may change the lock this admission binds), and launch-plans 08 (the sustained run moves onto launch plans, so balanced16 is re-admitted once after both migrations); strict-metrics tickets 03 and 06 (they change the sustained scorer, metric audit and admission, so this one re-admission covers them)

**Status:** done

- [x] A live admission runs on GPU 1 only, inside its systemd scope, with the storage gate passing; any GPU sharing is recorded
- [x] Every emitted receipt verifies against its source snapshot, rootfs lock and blobs read back through the blob store
- [x] A journal entry records the re-admission and what changed since ticket 27's admission, published through the journal spec with readback
- [x] Default CPU suite, `--config=cuda` suite and `//parallax/...` pass with counts recorded

## Closeout

Run `bs1220261009T154234Z` completed the admission-only readmission and is
reported in `docs/blob-store/balanced16-readmission.md`. The scoped launch
exited `0` after `5105.171` seconds with `MemoryMax=17179869184` and
`MemorySwapMax=0`; GPU 1 occupancy sampling recorded `170` samples and `6`
foreign-process samples, all owned by `philip.yang`. Receipt verification
passed for source snapshot readback, backend resume records `0` and `1000`,
`14` stage receipts, `4` GPU stages and `36` driver pins.

The research-journal append is entry `135`; journal publication readback audited
`403` direct files under
`runs/perception-research-journal/bs1220261009T154234Z/snapshot/`, with receipt
sha256 `690eb059e39e0938457a59f9823c28d98fd6b815355158011d91c2e4d871db2a`.
The current admission-only entry point retained local checkpoints and did not
emit separate resource/checkpoint publication receipts.

Gate counts:

- `//autonomy/...`: `186` out of `186` tests passed.
- `//parallax/...`: `17` out of `17` tests passed.
- `--config=cuda //autonomy/...` with `CUDA_VISIBLE_DEVICES=1`: `30` out of
  `30` tests passed after a GPU 1 free guard.
