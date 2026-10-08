# 09: Audits read launch plans from receipts, old and new

**What to build:** Stage, retention, checkpoint and semantic-recovery audits read the mounts of a launch from one receipt reader. The reader accepts new plan records and old command-line receipts, so audits stop scanning command lines and old evidence still verifies.

**Blocked by:** 01, blob-store 11 (which rewrites the retention audit)

**Status:** ready-for-agent

- [ ] One reader returns mounts by inside path, mode and digest (when known) for both receipt forms. `resources/command.py`'s command-line parser is kept only behind it and renamed for that job
- [ ] `resources/stage.py`, `resources/checkpoint.py`, `retention/retention_audit.py`, `segmentation/semantic_recovery_receipt.py` and `segmentation/semantic_recovery_receipt_aligned.py` use the reader. No flag-string checks remain
- [ ] Tests feed the reader a retained old receipt and a freshly recorded plan for an equivalent launch, and get the same mounts
- [ ] Retained receipts used by existing tests still verify
- [ ] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded
