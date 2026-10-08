# 01: Strict readers for every report kind, proven by replaying retained metric reports

**What to build:** A researcher can run every retained metric report on this host through its strict reader and get a report of what would be rejected and why, before any producer changes. This ticket makes each strict reader complete:
- **Detection:** extend `parse_result` with the committed breakdown-set constant and the known-diagnostics rule.
- **Segmentation:** add a new strict reader.
- **Motion:** add a new strict reader with explicit proto3 zero-omission.

It also adds a read-only replay tool and runs it. See `.scratch/strict-metrics/spec.md`.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] The detection reader requires the committed 32-name breakdown set. It accepts only the listed glog diagnostics on stderr and returns their counts; any other stderr rejects. A live-tagged test checks the constant against the evaluator source's documented set.
- [x] A strict segmentation reader exists: known preamble lines, each expected class exactly once, the mIoU line exactly once, `nan`/`inf` rejected
- [x] A strict motion reader exists: one bundle per `objectFilter`, unknown or duplicate filters rejected, zero-omitted fields read as 0.0 only from a declared list, measurement step and counts checked
- [x] Each reader is tested through its interface on real retained reports copied as small fixtures, plus a malformed variant for every rejection rule
- [x] A read-only replay runs every retained metric report under `~/.cache/waystone/waymo-perception/` and `autonomy/research/` through the matching reader. Nothing retained is modified.
- [x] The replay report (`docs/strict-metrics/replay-report.md` plus JSON) lists counts per kind, every rejection with its path and reason, and how many retained `check.json` files hold mis-keyed range entries in `metrics`
- [x] If any retained report is rejected, the ticket stops with the rejections flagged for the coordinator; no reader is loosened to make it pass
- [x] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded

## Comments

Done: added strict detection, segmentation and motion metric readers plus read-only retained replay. Replay wrote `docs/strict-metrics/replay-report.md` and `docs/strict-metrics/replay-report.json`; it read `~/.cache/waystone/waymo-perception/` and `autonomy/research/`, found 379 detection reports, 1 segmentation report, 16 motion reports, 0 rejections, and 407 retained `check.json` files with mis-keyed range entries. Detection diagnostics accepted and counted in retained reports: `glog_preinit` 49, `iou.cc:172 Tiny box dim seen` 530, `iou.cc:216 Huge box dim seen` 55.

Verification:
- Red tests first: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/detection:native_detection_adapter_test //autonomy/segmentation:strict_metric_reader_test //autonomy/motion:ingestion__strict_metric_reader_test //autonomy/evaluation:strict_metric_replay_test` failed before the implementation.
- Focused reader/replay tests after implementation: same command passed, 4/4 tests.
- Live-tagged detection breakdown source check: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors --test_tag_filters=requires_live_gate //autonomy/detection:native_detection_breakdowns_live_test` passed, 1/1 test.
- CPU gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed, 158/158 tests.
- Parallax gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed, 17/17 tests.
- CUDA gate: GPU 1 was free (`nvidia-smi`: GPU 1 at 4 MiB used, 0% util, no compute app on GPU 1); `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed, 28/28 tests.
