# 06: Per-class score records in check.json are read through one strict reader

**What to build:** These all read the per-class score record in `check.json` through one strict reader (class key set, finite values in [0, 1]):
- the sustained admission;
- the sustained contract;
- the evidence projection;
- the fixed-batch verifier.

The projection still shows a run with no score yet as running, but a malformed record now raises.

**Blocked by:** 02, 03

The sustained admission is on the balanced16 live path, so this ticket changes balanced16's source snapshot. Blob-store ticket 12's re-admission covers it.

**Status:** ready-for-agent

- [ ] One score-record reader exists. The sustained admission's existing strict check becomes it, with no behaviour change on valid records.
- [ ] The evidence projection distinguishes "no score yet" from "malformed score", and the latter raises
- [ ] The sustained contract and the fixed-batch verifier use the reader instead of key-set-only checks
- [ ] Tests cover each rejection rule through the reader's interface
- [ ] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded
