# 10: Live gates and M0 on launch plans

**What to build:** The live-gate support that semantic-layout ticket 29 adds to `insula`, and the M0 verifier and receipt, are built on launch plans, so live gates are one more caller rather than another launch shape.

**Blocked by:** 01, semantic-layout 29

**Status:** ready-for-agent

- [ ] Ticket 29's live-gate support builds launch plans through the module, with no command-line assembly of its own
- [ ] `insula/verify_m0.py` and `insula/m0_receipt.py` load locks through the module. M0's whole-lock comparison still happens
- [ ] Ticket 29's four live gates still pass when re-run through the rebuilt support, recorded with counts
- [ ] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded
