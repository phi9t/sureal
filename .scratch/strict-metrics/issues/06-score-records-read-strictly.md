# 06: Per-class score records in check.json are read through one strict reader

**What to build:** These all read the per-class score record in `check.json` through one strict reader (class key set, finite values in [0, 1]):
- the sustained admission;
- the sustained contract;
- the evidence projection;
- the fixed-batch verifier.

The projection still shows a run with no score yet as running, but a malformed record now raises.

**Blocked by:** 02, 03

The sustained admission is on the balanced16 live path, so this ticket changes balanced16's source snapshot. Blob-store ticket 12's re-admission covers it.

**Status:** done

- [x] One score-record reader exists. The sustained admission's existing strict check becomes it, with no behaviour change on valid records.
- [x] The evidence projection distinguishes "no score yet" from "malformed score", and the latter raises
- [x] The sustained contract and the fixed-batch verifier use the reader instead of key-set-only checks
- [x] Tests cover each rejection rule through the reader's interface
- [x] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded

## Comments

Done 2026-10-09:
- Added `evidence.score_records.read_level2_per_class(record, *, classes)` as the single strict reader for `LEVEL2_per_class`: the record must contain exactly the caller-supplied native class set, exactly `AP` and `APH` per row, and numeric finite values in `[0, 1]`.
- Added `evidence.score_records.populated_level2_classes` so populated-class consumers can derive their expected class set from retained `groundtruth_by_class` records instead of treating all four classes as implicit.
- Sustained admission and the sustained contract pass all four native LEVEL_2 classes (`1`, `2`, `3`, `4`) because their retained/live inputs are all-class gates. The sustained contract still wraps reduced `APH` samples as `AP=APH` before using the same strict reader.
- Evidence projection keeps absent `LEVEL2_per_class` as not scored yet (`running_or_verifying`, empty terminal score, no worst APH), accepts populated-class score records when `groundtruth_by_class` names that populated set, and otherwise requires all four classes.
- Fixed-batch verification now reads score receipts, curve points, inherited baseline scores and terminal output through the shared reader with the all-four class rule instead of checking only the class key set.
- Retained score-record replay wrote `docs/strict-metrics/score-record-replay.md`: 1433 JSON files mention `LEVEL2_per_class`, 1371 parsed JSON files contain 6404 actual records, 4672 are legitimate three-class populated records, 1727 are four-class AP/APH records, and the five odd records are unconsumed by migrated readers.
- Consumer replay counts: sustained admission 4/4 accepted, sustained contract 4/4 accepted, evidence projection 214/214 accepted, fixed-batch verifier 435/435 accepted, populated-class producer compatibility 4672/4672 accepted, and no consumed rejections.
- The four APH-only records were written by research tracker live fixtures and the one class-name-keyed record was written by association oracle coverage control; no migrated reader consumes them, so the reader was not loosened for those shapes.
- Old mis-keyed range entries under `metrics` are tolerated here only because these migrated readers read `LEVEL2_per_class`, not the historical range rows.
- No balanced16 run happened here; blob-store ticket 12's single re-admission covers the balanced16 source-snapshot change.

Verification:
- Red checks: `//autonomy/evidence:score_records_test` first failed before `classes` was accepted; the consumer-focused suite first exposed naked reader call sites missing the required keyword; `//autonomy/evaluation:strict_metric_replay_test` first failed before score-record replay APIs and then before fixed-batch replay was narrowed to actual fixed/expanded result files.
- Focused green: `./bazelw test --test_tag_filters= --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/evidence:score_records_test //autonomy/evidence:projection_test //autonomy/detection:sustained_contract_test //autonomy/training_execution:sustained_admission_test //autonomy/evaluation:metrics_sustained_v3_test //autonomy/evaluation:strict_metric_replay_test //autonomy/studies:fixed_batch__fixed_batch_verifier_test` passed, 7/7 tests.
- Replay: `PYTHONPATH=autonomy PYTHONDONTWRITEBYTECODE=1 python3 autonomy/evaluation/strict_metric_replay.py --score-records` exited 0 and refreshed `docs/strict-metrics/score-record-replay.md`.
- Default CPU gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed, 170/170 tests (ticket baseline was 168; current checkout reports 170).
- Parallax gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed, 17/17 tests.
- GPU availability: `nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader,nounits` showed GPU 1 at `4 MiB` and `0%`; `nvidia-smi pmon -c 1` showed no GPU 1 process.
- CUDA gate: `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed, 28/28 tests.

Review 2 follow-up 2026-10-09:
- Removed the projection self-keyed fallback. A projection point can narrow the reader class set only through `groundtruth_by_class` on the point or its `preparation`; otherwise the expected class set is all four `LEVEL2_CLASS_KEYS`.
- Preserved the acceptance rule in `quality()`: populated-class records can fill `terminal_LEVEL2_per_class` and `worst_terminal_APH`, but only all four native LEVEL_2 classes with `APH >= 0.80` can satisfy overfit quality.
- Added regression coverage for a three-class populated record that parses for display but does not pass quality, plus a three-class score record with no class-set source that is rejected.
- Replay after this change: `PYTHONPATH=autonomy PYTHONDONTWRITEBYTECODE=1 python3 autonomy/evaluation/strict_metric_replay.py --score-records` exited 0 and refreshed `docs/strict-metrics/score-record-replay.md`; sustained admission 4/4 accepted, sustained contract 4/4 accepted, evidence projection 214/214 accepted, fixed-batch verifier 435/435 accepted, populated-class producer compatibility 4672/4672 accepted, and no consumed rejections.
- Re-run gates: focused projection/replay tests passed 2/2; default CPU `//autonomy/...` passed 170/170; `//parallax/...` passed 17/17; GPU 1 was free (`4 MiB`, `0%`, no `pmon` process) and CUDA `//autonomy/...` passed 28/28.
