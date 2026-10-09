# 06: Evaluation verifiers and the training box replay on launch plans

**What to build:** The evaluation verifiers and audits, and the hand-written sandbox in the training box replay, run on launch plans. The replay gains the overlap check and `PYTHONPATH` its hand-written sandbox lacks.

**Blocked by:** 01

**Status:** done

- [x] `evaluation/audit-perception-gate.py`, `verify-detection-adapter.py`, `verify-detection-contract.py`, `verify-native-metrics.py` and `verify-real-detection-export.py` build launch plans and load locks (including the metrics image-form lock) through the module. None creates a lock when it is missing
- [x] `detection/training_box_replay.py` builds a launch plan instead of a hand-written `bwrap` command. Its whole-lock comparison against the pinned lock still happens
- [x] Tests assert on plans built against fixture locks
- [x] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded

## Comments

### 2026-10-09 worker evidence

Implemented launch-plan builders for the evaluation/detection verifier scripts and the training box replay. The metrics verifier now loads the metrics image-form runtime lock through `load_runtime_lock` and fails on a missing lock instead of materializing one. The replay now builds a checked launch plan for each worker phase, passes the rendered plan only at the measurement-process boundary, records the plan, and keeps the whole-lock comparison against the pinned execution candidate lock.

Tests added/updated assert plan data against fixture runtime locks:

- `autonomy/evaluation/launches_test.py`: missing metrics locks are not materialized; metrics verifier plans expose the checked image runtime, mounts and `PYTHONPATH` as data.
- `autonomy/detection/training_box_replay_test.py`: replay worker plans use a checked runtime, named inputs and `PYTHONPATH`; the central overlap rule rejects a code/source-audit collision.

Verification logs are under `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/lp06-evaluation-launches-20261009T010152Z/tmp/logs`:

- `PYTHONPATH=autonomy python3 autonomy/evaluation/launches_test.py`: passed, 2/2 tests.
- `PYTHONPATH=autonomy python3 autonomy/detection/training_box_replay_test.py`: passed, 5/5 tests.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/evaluation:launches_test //autonomy/detection:training_box_replay_test`: passed, 2/2 targets.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: passed, 169/169 tests. Ticket baseline was 168; new count is 169.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`: passed, 17/17 tests.
- `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: passed on GPU 1, 28/28 tests. GPU 1 was checked before the run at `0%`, `4 MiB / 183359 MiB`, and after the run again at `0%`, `4 MiB / 183359 MiB`.
