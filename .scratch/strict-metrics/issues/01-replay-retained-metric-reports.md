# 01: Strict readers for every report kind, proven by replaying retained metric reports

**What to build:** A researcher can run every retained metric report on this host through its strict reader and get a report of what would be rejected and why, before any producer changes. This ticket makes each strict reader complete:
- **Detection:** extend `parse_result` with the committed breakdown-set constant and the known-diagnostics rule.
- **Segmentation:** add a new strict reader.
- **Motion:** add a new strict reader with explicit proto3 zero-omission.

It also adds a read-only replay tool and runs it. See `.scratch/strict-metrics/spec.md`.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The detection reader requires the committed 32-name breakdown set. It accepts only the listed glog diagnostics on stderr and returns their counts; any other stderr rejects. A live-tagged test checks the constant against the evaluator source's documented set.
- [ ] A strict segmentation reader exists: known preamble lines, each expected class exactly once, the mIoU line exactly once, `nan`/`inf` rejected
- [ ] A strict motion reader exists: one bundle per `objectFilter`, unknown or duplicate filters rejected, zero-omitted fields read as 0.0 only from a declared list, measurement step and counts checked
- [ ] Each reader is tested through its interface on real retained reports copied as small fixtures, plus a malformed variant for every rejection rule
- [ ] A read-only replay runs every retained metric report under `~/.cache/waystone/waymo-perception/` and `autonomy/research/` through the matching reader. Nothing retained is modified.
- [ ] The replay report (`docs/strict-metrics/replay-report.md` plus JSON) lists counts per kind, every rejection with its path and reason, and how many retained `check.json` files hold mis-keyed range entries in `metrics`
- [ ] If any retained report is rejected, the ticket stops with the rejections flagged for the coordinator; no reader is loosened to make it pass
- [ ] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded
