# 03: Motion verifiers and the scientific cohort run again

**What to build:** The motion verifiers and the scientific cohort, which today fail before launching because they mount the same directory as code and source, run on launch plans and pass for real. Image-form runtime locks are loaded through the module, and nothing creates a lock on the spot.

**Blocked by:** 01

**Status:** ready-for-human

- [x] `motion/verify_motion_cli.py`, `motion/verify_motion_cli_expanded.py`, `motion/verify_motion_native.py`, `motion/replay_motion_foundation.py`, `studies/scientific_cohort.py` and `studies/architecture/experiment_runner.py` build launch plans; no command-line splicing remains in them. If `experiment_runner` only drives frozen harness scripts, record why it stays as it is
- [x] The motion verifiers load their image-form locks through the module and no longer create a lock when one is missing
- [x] `studies/scientific_cohort_test.py` no longer replaces `launch_plan` with a fake. It asserts on the plan built against a fixture lock
- [ ] Acceptance: each motion verifier and the scientific cohort is run for real under `requires_live_gate` and passes. Commands, receipts and durations are recorded in the ticket. A failure unrelated to launching is reported as found, not hidden
- [x] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded

## Comments

### 2026-10-09 worker evidence

Implemented the launch-plan migration for the ticket-owned active callers:

- `motion/verify_motion_cli.py`, `motion/verify_motion_cli_expanded.py` and `motion/verify_motion_native.py` now call `load_runtime_lock` for their image-form locks, build `LaunchPlan` objects with `build_plan`, render only at execution, and record `launch_plan` receipt data. The old missing-lock Docker export/create fallback is removed, so a missing lock is an error from the module.
- `motion/replay_motion_foundation.py` is import-safe, builds plans through the module, records plan receipts, and has `--output-root` so this worker could keep outputs under the required `lp03-runs` tree.
- `studies/scientific_cohort.py` now loads the current CPU runtime lock through `load_runtime_lock` before building eviction plans, declares `/opt` and `/srv` as plan inputs, and does not splice `--bind` / `--ro-bind` into a rendered command.
- `studies/architecture/experiment_runner.py` was left unchanged because it does not launch Insula directly in active code. It verifies receipts and dispatches copied frozen harness drivers from `studies/architecture/harness/`, which this ticket explicitly keeps frozen; its remaining `--ro-bind` reads are retained-receipt parsing for pinned manifest/worker verification.
- `studies/scientific_cohort_test.py` no longer replaces `launch_plan` with a fake. It uses a fixture runtime lock and asserts on `plan_data` for the built eviction plan.

TDD red evidence:

- `PYTHONPATH=autonomy python3 -m unittest autonomy.motion.verify_launch_plan_test autonomy.studies.scientific_cohort_test` failed first because the motion modules had no checked plan helpers, `replay_motion_foundation.py` executed at import time, `scientific_cohort.py` had no `build_eviction_plan`, and the old cohort path raised `code and source: host path mounted twice`.
- After the migration, the same focused unittest command passed 4/4 tests.

Focused and full gates:

- Focused Bazel: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/motion:verify_launch_plan_test //autonomy/studies:scientific_cohort_test` passed, 2/2 tests. Log: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/lp03-broken-verifiers-20261009T010152Z/tmp/logs/focused-bazel-r2.log`.
- Default autonomy gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed, 169/169 tests. Ticket baseline was 168; new count is 169. Log: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/lp03-broken-verifiers-20261009T010152Z/tmp/logs/autonomy-default.log`.
- Parallax gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed, 17/17 tests. Log: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/lp03-broken-verifiers-20261009T010152Z/tmp/logs/parallax.log`.
- CUDA autonomy gate: GPU 1 was free before the run (`index=1, utilization=0%, memory=4/183359 MiB`). `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed, 28/28 tests. GPU 1 was idle after the run (`index=1, utilization=0%, memory=4/183359 MiB`). Log: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/lp03-broken-verifiers-20261009T010152Z/tmp/logs/autonomy-cuda.log`.

Real motion verifier runs under the launch-plan path wrote outputs under `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/lp03-runs/lp03-acceptance.VxmijC`:

- `PYTHONPATH=autonomy python3 autonomy/motion/verify_motion_cli.py /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/lp03-runs/lp03-acceptance.VxmijC/verify-motion-cli` passed in 4s. Receipt: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/lp03-runs/lp03-acceptance.VxmijC/verify-motion-cli/receipt.json`, sha256 `5479fe4edb087b5fb471d776e7c7164fca45dd4e28992a09fd8ddab27ac5eb9f`.
- `PYTHONPATH=autonomy python3 autonomy/motion/verify_motion_cli_expanded.py /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/lp03-runs/lp03-acceptance.VxmijC/verify-motion-cli-expanded` passed in 4s. Receipt: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/lp03-runs/lp03-acceptance.VxmijC/verify-motion-cli-expanded/receipt.json`, sha256 `d72bb46ceb9c4ebf6c308f1ab10f86ea1f5363556ca3f88796827af9ad032617`.
- `PYTHONPATH=autonomy python3 autonomy/motion/verify_motion_native.py /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/lp03-runs/lp03-acceptance.VxmijC/verify-motion-native` passed in 5s. Receipt: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/lp03-runs/lp03-acceptance.VxmijC/verify-motion-native/receipt.json`, sha256 `db96875820612aaa217e11f9190c5c08229e4368110875405ae1977f91250451`.
- First `motion/replay_motion_foundation.py` run launched successfully but failed inside the native CLI fixture because the staged source closure omitted `motion/ingestion/strict_metric_reader.py`. That was a real non-launching failure and was fixed by staging that source file.
- `PYTHONPATH=autonomy python3 autonomy/motion/replay_motion_foundation.py --run-id replay-motion-foundation-r2 --output-root /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/lp03-runs/lp03-acceptance.VxmijC` passed in 14s. Receipt: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/lp03-runs/lp03-acceptance.VxmijC/replay-motion-foundation-r2/receipt.json`, sha256 `bfa112478d134bfdc75385203c94c18370a37de167ee5bd3c8acaf22d37cb1e0`.

Blocked acceptance item:

- I did not run a fresh `studies/scientific_cohort.py` lifecycle. Its publication stages invoke Waystone `put` to HDFS, and this worker was explicitly forbidden from HDFS writes. The script also requires output under the accounted scientific working root, while this run allows outside-repo writes only under `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/lp03-runs`.
- I checked for a no-write resume path through existing `cohort-v1` checkpoints and a trusted checkpoint registry. Existing checkpoint receipts use an older runtime lock, and `dataset.cohort_checkpoint.verify_checkpoint` compares `cp['runtime_lock']` exactly against the current `load_runtime_lock` result, so those retained checkpoints cannot satisfy this ticket's current-lock acceptance without a separate re-admission decision.
- The blocker is also recorded in the worker issue channel at `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/lp03-broken-verifiers-20261009T010152Z/tmp/claude-issues.jsonl`.
