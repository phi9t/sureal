# 05: Motion metric reports read strictly

**What to build:** These all read motion metric reports through the strict motion reader:
- the motion metric handoff check;
- the pooled handoff check;
- the motion CLI tests (native, joint and pooled).

Duplicate class bundles are rejected, and zero-omitted fields follow the reader's declared rule rather than ad-hoc `.get(…, 0)` defaults.

**Blocked by:** 01

**Status:** done

- [x] The metric handoff check and the pooled handoff check use the strict reader; their own bundle and count parsing is removed, and the existing refusal counts still hold
- [x] The motion CLI tests select class bundles through the reader, so a duplicated `objectFilter` fails the test
- [x] Values are unchanged on every retained report the replay covered
- [x] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded

## Comments

Done: motion handoff checks now call `motion.ingestion.strict_metric_reader.parse_result` for report identity, structural fields, measurement step, counts, duplicate filters and proto3 zero-omitted metric values. Native, joint and pooled motion CLI tests select vehicle metrics through the reader-backed `vehicle_metrics` helper, and `cli__motion_cli_strict_reader_selection_test` proves a duplicated `objectFilter` raises.

Verification:
- Red: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/motion:ingestion__strict_metric_reader_test` failed before the selector existed; `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/motion:cli__motion_cli_strict_reader_selection_test` then failed on the missing CLI selector.
- Focused green: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/motion:cli__motion_cli_strict_reader_selection_test //autonomy/motion:ingestion__strict_metric_reader_test //autonomy/motion/...` passed, 3/3 tests.
- Replay parity: `python3 -m autonomy.evaluation.strict_metric_replay --output /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/sm05-motion-20261009T000632Z/tmp/replay.5OEcgA` passed with 379 detection reports, 1 segmentation report, 16 motion reports, 0 rejections and 407 retained `check.json` files with mis-keyed range entries. The motion reader's parsed value path is unchanged except for the selector wrapper.
- CPU gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed, 165/165 tests.
- Parallax gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed, 17/17 tests.
- CUDA gate: GPU 1 was free (`nvidia-smi`: GPU 1 at 4 MiB used, 0% util, no process on GPU 1); `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed, 28/28 tests.
