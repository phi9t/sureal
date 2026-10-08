# 05: Motion metric reports read strictly

**What to build:** These all read motion metric reports through the strict motion reader:
- the motion metric handoff check;
- the pooled handoff check;
- the motion CLI tests (native, joint and pooled).

Duplicate class bundles are rejected, and zero-omitted fields follow the reader's declared rule rather than ad-hoc `.get(…, 0)` defaults.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] The metric handoff check and the pooled handoff check use the strict reader; their own bundle and count parsing is removed, and the existing refusal counts still hold
- [ ] The motion CLI tests select class bundles through the reader, so a duplicated `objectFilter` fails the test
- [ ] Values are unchanged on every retained report the replay covered
- [ ] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded
